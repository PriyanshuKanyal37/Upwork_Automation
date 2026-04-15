from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.connector.contracts import ConnectorHealthResult, PublishRequest, PublishResult
from app.application.connector.service import get_connector_for_user, normalize_connector_name
from app.application.job.service import get_job_for_user
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.integrations.airtable_client import AirtableClient
from app.infrastructure.integrations.google_docs_client import GoogleDocsClient
from app.infrastructure.integrations.google_oauth import resolve_google_access_token

_DEFAULT_PUBLISH_CONNECTORS = ("google_docs", "airtable")
_FLOWCHART_ARTIFACT_TYPE = "doc_flowchart"


def _serialize_publish_result(item: PublishResult) -> dict[str, Any]:
    return {
        "connector_name": item.connector_name,
        "status": item.status,
        "external_id": item.external_id,
        "external_url": item.external_url,
        "reason": item.reason,
        "metadata": item.metadata or {},
    }


def _serialize_health_result(item: ConnectorHealthResult) -> dict[str, Any]:
    return {
        "connector_name": item.connector_name,
        "status": item.status,
        "message": item.message,
        "is_connected": item.is_connected,
        "action_required": item.action_required,
        "checked_live": item.checked_live,
        "details": item.details or {},
    }


async def _get_job_output(*, session: AsyncSession, job_id: UUID) -> JobOutput:
    output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job_id))
    if output is None:
        raise AppException(
            status_code=404,
            code="job_output_not_found",
            message="Job output not found for publishing",
        )
    return output


def _build_publish_markdown(output: JobOutput) -> str:
    if output.google_doc_markdown and output.google_doc_markdown.strip():
        return output.google_doc_markdown.strip()

    sections: list[str] = []
    if output.proposal_text and output.proposal_text.strip():
        sections.append(f"## Proposal\n\n{output.proposal_text.strip()}")
    if output.loom_script and output.loom_script.strip():
        sections.append(f"## Loom Script\n\n{output.loom_script.strip()}")
    if output.workflow_jsons:
        sections.append("## Workflow JSON\n\n```json\n" + str(output.workflow_jsons) + "\n```")
    if sections:
        return "\n\n".join(sections)
    raise AppException(
        status_code=422,
        code="publish_content_missing",
        message="No publishable output content found",
    )


def _strip_flowchart_markdown_section(markdown: str) -> str:
    lines = markdown.splitlines()
    cleaned: list[str] = []
    skipping = False
    for line in lines:
        if re.match(
            r"^\s*##\s+.*(?:flowchart|flow\s+at\s+a\s+glance)\b",
            line,
            flags=re.IGNORECASE,
        ):
            skipping = True
            continue
        if skipping and re.match(r"^\s*##\s+", line):
            skipping = False
        if not skipping:
            cleaned.append(line)
    return "\n".join(cleaned).strip() or markdown.strip()


async def _publish_google_docs(
    *,
    connector_name: str,
    credential_ref: str,
    title: str,
    content_markdown: str,
    output: JobOutput,
) -> PublishResult:
    access_token = await resolve_google_access_token(credential_ref)
    client = GoogleDocsClient()
    selected_flowchart = _extract_selected_doc_flowchart(output)
    quality_status = (
        str(selected_flowchart.get("quality_status")).strip().lower()
        if isinstance(selected_flowchart, dict) and selected_flowchart.get("quality_status") is not None
        else None
    )
    quality_approved = quality_status in {"passed", "fallback_passed"}
    inline_image_url = (
        str(selected_flowchart.get("image_url")).strip()
        if (
            isinstance(selected_flowchart, dict)
            and selected_flowchart.get("status") == "ready"
            and quality_approved
        )
        else None
    )
    publish_metadata: dict[str, Any] = {
        "diagram_included": bool(inline_image_url),
        "diagram_reason": (
            "selected_flowchart_missing"
            if not selected_flowchart
            else "diagram_quality_rejected"
            if not quality_approved
            else "selected_flowchart_not_ready"
            if not inline_image_url
            else "selected_flowchart_ready"
        ),
    }
    if selected_flowchart:
        publish_metadata["selected_flowchart"] = {
            "generated_at": selected_flowchart.get("generated_at"),
            "request_id": selected_flowchart.get("request_id"),
            "words_sent": selected_flowchart.get("words_sent"),
            "estimated_credits_used": selected_flowchart.get("estimated_credits_used"),
            "quality_score": selected_flowchart.get("quality_score"),
            "quality_status": selected_flowchart.get("quality_status"),
        }

    markdown_for_publish = (
        _strip_flowchart_markdown_section(content_markdown) if inline_image_url else content_markdown
    )
    publish_metadata["flowchart_section_removed"] = bool(inline_image_url)

    try:
        created = await client.create_document_from_markdown(
            access_token=access_token,
            title=title,
            markdown=markdown_for_publish,
        )
    except AppException:
        # Fallback to the older batchUpdate renderer if HTML import fails.
        created = await client.create_document(access_token=access_token, title=title)
        try:
            await client.insert_markdown(
                access_token=access_token,
                document_id=created["document_id"],
                markdown=markdown_for_publish,
                inline_image_url=inline_image_url,
            )
        except AppException:
            if inline_image_url:
                publish_metadata["diagram_included"] = False
                publish_metadata["diagram_reason"] = "diagram_embed_failed"
                await client.insert_markdown(
                    access_token=access_token,
                    document_id=created["document_id"],
                    markdown=markdown_for_publish,
                    inline_image_url=None,
                )
            else:
                raise
    else:
        if inline_image_url:
            try:
                await client.append_flow_diagram(
                    access_token=access_token,
                    document_id=created["document_id"],
                    inline_image_url=inline_image_url,
                )
            except AppException:
                publish_metadata["diagram_included"] = False
                publish_metadata["diagram_reason"] = "diagram_embed_failed"

    return PublishResult(
        connector_name=connector_name,
        status="published",
        external_id=created["document_id"],
        external_url=created["document_url"],
        metadata=publish_metadata,
    )


def _extract_selected_doc_flowchart(output: JobOutput) -> dict[str, Any] | None:
    for entry in reversed(output.extra_files_json or []):
        if isinstance(entry, dict) and entry.get("artifact_type") == _FLOWCHART_ARTIFACT_TYPE:
            return entry
    return None


async def _publish_airtable_scaffold(*, connector_name: str) -> PublishResult:
    client = AirtableClient()
    try:
        client.assert_publish_enabled()
    except AppException as exc:
        return PublishResult(
            connector_name=connector_name,
            status="skipped",
            reason=exc.code,
            metadata={"message": exc.message},
        )
    return PublishResult(
        connector_name=connector_name,
        status="skipped",
        reason="airtable_future_adapter_pending",
        metadata={"message": "Airtable publish scaffold is ready; data mapping activation pending."},
    )


async def publish_job_outputs(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    title: str | None = None,
    connectors: list[str] | None = None,
) -> dict[str, Any]:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await _get_job_output(session=session, job_id=job_id)
    if not job.plan_approved or not output.approval_snapshot_json:
        raise AppException(
            status_code=409,
            code="approval_required",
            message="Outputs must be approved before publish",
        )

    selected_connectors = connectors or list(_DEFAULT_PUBLISH_CONNECTORS)
    normalized_connectors = [normalize_connector_name(name) for name in selected_connectors]
    publish_title = title or f"Upwork Job Output - {job.id}"
    content_markdown = _build_publish_markdown(output)

    results: list[PublishResult] = []
    for connector_name in normalized_connectors:
        try:
            connector = await get_connector_for_user(
                session=session,
                user_id=user_id,
                connector_name=connector_name,
            )
        except AppException as exc:
            if exc.code == "connector_not_found":
                results.append(
                    PublishResult(
                        connector_name=connector_name,
                        status="skipped",
                        reason="connector_not_found",
                    )
                )
                continue
            raise

        if connector.status != "connected":
            results.append(
                PublishResult(
                    connector_name=connector_name,
                    status="skipped",
                    reason=f"connector_{connector.status}",
                )
            )
            continue

        publish_request = PublishRequest(
            connector_name=connector_name,
            title=publish_title,
            content_markdown=content_markdown,
            metadata={"job_id": str(job_id), "user_id": str(user_id)},
        )
        try:
            if connector_name == "google_docs":
                result = await _publish_google_docs(
                    connector_name=publish_request.connector_name,
                    credential_ref=connector.credential_ref,
                    title=publish_request.title,
                    content_markdown=publish_request.content_markdown,
                    output=output,
                )
                output.google_doc_url = result.external_url
            elif connector_name == "airtable":
                result = await _publish_airtable_scaffold(connector_name=publish_request.connector_name)
            else:
                result = PublishResult(
                    connector_name=connector_name,
                    status="skipped",
                    reason="connector_publish_not_supported",
                )
        except AppException as exc:
            result = PublishResult(
                connector_name=connector_name,
                status="failed",
                reason=exc.code,
                metadata={"message": exc.message, "details": exc.details},
            )
        results.append(result)

    output.edit_log_json = list(output.edit_log_json or []) + [
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": "publish",
            "target_output": "multi",
            "changed_fields": ["google_doc_url"] if output.google_doc_url else [],
            "instruction": None,
        }
    ]
    await session.commit()
    await session.refresh(output)
    await session.refresh(job)

    return {
        "job_id": str(job.id),
        "published_at": datetime.now(UTC).isoformat(),
        "results": [_serialize_publish_result(item) for item in results],
        "google_doc_url": output.google_doc_url,
        "google_doc_open_url": output.google_doc_url,
    }


async def run_live_connector_health_check(
    *,
    connector_name: str,
    credential_ref: str,
    current_status: str,
) -> ConnectorHealthResult:
    if connector_name == "google_docs":
        try:
            access_token = await resolve_google_access_token(credential_ref)
            details = await GoogleDocsClient().probe_token(access_token=access_token)
            return ConnectorHealthResult(
                connector_name=connector_name,
                status=current_status,
                message="Google Docs connector is healthy",
                is_connected=True,
                action_required=False,
                checked_live=True,
                details=details,
            )
        except AppException as exc:
            return ConnectorHealthResult(
                connector_name=connector_name,
                status="error",
                message="Google Docs live probe failed",
                is_connected=False,
                action_required=True,
                checked_live=True,
                details={"code": exc.code, "message": exc.message},
            )
    if connector_name == "airtable":
        try:
            details = await AirtableClient().probe()
            return ConnectorHealthResult(
                connector_name=connector_name,
                status=current_status,
                message="Airtable connector is healthy",
                is_connected=True,
                action_required=False,
                checked_live=True,
                details=details,
            )
        except AppException as exc:
            return ConnectorHealthResult(
                connector_name=connector_name,
                status="error" if exc.code != "airtable_publish_not_enabled" else "disconnected",
                message="Airtable live probe failed",
                is_connected=False,
                action_required=True,
                checked_live=True,
                details={"code": exc.code, "message": exc.message},
            )
    return ConnectorHealthResult(
        connector_name=connector_name,
        status=current_status,
        message="Live health probe not configured for this connector",
        is_connected=current_status == "connected",
        action_required=current_status != "connected",
        checked_live=True,
        details={"reason": "unsupported_connector"},
    )


def serialize_live_health(result: ConnectorHealthResult) -> dict[str, Any]:
    return _serialize_health_result(result)
