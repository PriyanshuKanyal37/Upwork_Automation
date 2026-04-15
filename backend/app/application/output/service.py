from __future__ import annotations

import base64
from datetime import UTC, datetime
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.connector.service import get_connector_for_user
from app.application.job.service import get_job_for_user
from app.application.output.diagram_models import DiagramConnection, DiagramSpec
from app.application.output.diagram_quality_validator import validate_diagram_quality
from app.application.output.diagram_renderer import convert_svg_to_png, render_diagram_svg
from app.application.output.diagram_spec_service import build_deterministic_diagram_spec, build_diagram_spec
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.integrations.google_docs_client import GoogleDocsClient
from app.infrastructure.integrations.google_oauth import resolve_google_access_token

_FLOWCHART_ARTIFACT_TYPE = "doc_flowchart"
_FLOWCHART_MAX_ATTEMPTS = 3


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _sanitize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _sanitize_optional_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > 2048:
        raise AppException(
            status_code=422,
            code="invalid_google_doc_url",
            message="Google doc URL exceeds maximum allowed length",
        )
    return stripped


def _normalize_connection_style(connection_style: str | None) -> str:
    lowered = (connection_style or "").strip().lower()
    if lowered in {"clean", "orthogonal", "curved"}:
        return lowered
    return "clean"


def _derive_canvas_size(
    *,
    spec: DiagramSpec,
    max_width: int,
    max_height: int,
) -> tuple[int, int]:
    step_count = max(1, len(spec.steps))
    columns = (step_count + 1) // 2 if step_count >= 6 else step_count

    # Keep diagrams readable in inline UI previews while staying wide enough
    # for Google Docs embedding.
    base_width = 220 + (columns * 250)
    title_bonus = min(220, max(0, len(spec.title) - 44) * 6)
    width = _clamp(base_width + title_bonus, 1200, max_width)

    has_feedback = any(conn.edge_type == "feedback" for conn in spec.connections)
    base_height = 920 if step_count >= 6 else 760
    if has_feedback:
        base_height += 80
    height = _clamp(base_height, 700, max_height)

    return width, height


async def _find_job_output(*, session: AsyncSession, job_id: UUID) -> JobOutput | None:
    output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job_id))
    return output


def _append_edit_log(
    *,
    output: JobOutput,
    action: str,
    target_output: str,
    changed_fields: list[str],
    instruction: str | None = None,
) -> None:
    entries = list(output.edit_log_json or [])
    entries.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "target_output": target_output,
            "changed_fields": changed_fields,
            "instruction": instruction,
        }
    )
    output.edit_log_json = entries


def _upsert_extra_file_entry(*, output: JobOutput, artifact_type: str, payload: dict[str, Any]) -> None:
    entries = [entry for entry in (output.extra_files_json or []) if entry.get("artifact_type") != artifact_type]
    entries.append({"artifact_type": artifact_type, **payload})
    output.extra_files_json = entries


_FLOWCHART_SECTION_HEADING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("flow_at_a_glance", re.compile(r"^\s*##\s+.*the\s+flow\s+at\s+a\s+glance\b", re.IGNORECASE)),
    ("how_ill_solve_it", re.compile(r"^\s*##\s+.*how\s+i(?:'|\u2019)?ll\s+solve\s+it\b", re.IGNORECASE)),
    ("execution_plan", re.compile(r"^\s*##\s+.*execution\s+plan\b", re.IGNORECASE)),
)


def _extract_flowchart_source_section(markdown: str) -> tuple[str, str] | None:
    """Find the highest-signal section to seed diagram generation."""
    lines = markdown.splitlines()
    for kind, pattern in _FLOWCHART_SECTION_HEADING_PATTERNS:
        capture = False
        section_lines: list[str] = []
        for raw in lines:
            line = raw.rstrip()
            if pattern.match(line):
                capture = True
                continue
            if capture and re.match(r"^\s*##\s+", line):
                break
            if capture:
                stripped = line.strip()
                if stripped and stripped != "---":
                    section_lines.append(stripped)
        if section_lines:
            return kind, "\n".join(section_lines).strip()
    return None


def _extract_execution_plan_text(markdown: str) -> str | None:
    result = _extract_flowchart_source_section(markdown)
    return result[1] if result else None


def _word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", text.strip()) if part])


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or "Workflow Diagram"
    return "Workflow Diagram"


def _archive_existing_artifact_version(*, output: JobOutput, artifact_type: str) -> None:
    existing: dict[str, Any] | None = None
    for entry in reversed(output.extra_files_json or []):
        if isinstance(entry, dict) and entry.get("artifact_type") == artifact_type:
            existing = dict(entry)
            break
    if not existing:
        return
    versions = list(output.artifact_versions_json or [])
    versions.append(
        {
            "artifact_type": artifact_type,
            "archived_at": datetime.now(UTC).isoformat(),
            "payload": existing,
        }
    )
    output.artifact_versions_json = versions


async def get_job_output_for_user(*, session: AsyncSession, user_id: UUID, job_id: UUID) -> JobOutput:
    await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await _find_job_output(session=session, job_id=job_id)
    if not output:
        raise AppException(status_code=404, code="job_output_not_found", message="Job output not found")
    return output


async def upsert_job_output(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    google_doc_url: str | None = None,
    google_doc_markdown: str | None = None,
    workflow_jsons: list[dict[str, Any]] | None = None,
    workflow_explanation: str | None = None,
    loom_script: str | None = None,
    proposal_text: str | None = None,
) -> JobOutput:
    await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await _find_job_output(session=session, job_id=job_id)
    if output is None:
        output = JobOutput(job_id=job_id)
        session.add(output)

    updates: dict[str, Any] = {}
    if google_doc_url is not None:
        updates["google_doc_url"] = _sanitize_optional_url(google_doc_url)
    if google_doc_markdown is not None:
        updates["google_doc_markdown"] = _sanitize_optional_text(google_doc_markdown)
    if workflow_jsons is not None:
        updates["workflow_jsons"] = workflow_jsons
    if workflow_explanation is not None:
        updates["workflow_explanation"] = _sanitize_optional_text(workflow_explanation)
    if loom_script is not None:
        updates["loom_script"] = _sanitize_optional_text(loom_script)
    if proposal_text is not None:
        updates["proposal_text"] = _sanitize_optional_text(proposal_text)

    if not updates:
        raise AppException(
            status_code=422,
            code="no_output_fields",
            message="At least one output field must be provided",
        )

    for key, value in updates.items():
        setattr(output, key, value)

    _append_edit_log(
        output=output,
        action="save",
        target_output="multi",
        changed_fields=sorted(updates.keys()),
    )

    await session.commit()
    await session.refresh(output)
    return output


async def regenerate_single_output(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    target_output: str,
    generated_text: str | None,
    generated_workflow_jsons: list[dict[str, Any]] | None,
    instruction: str | None,
) -> JobOutput:
    await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await _find_job_output(session=session, job_id=job_id)
    if output is None:
        output = JobOutput(job_id=job_id)
        session.add(output)

    if target_output == "workflow_jsons":
        output.workflow_jsons = generated_workflow_jsons or []
    elif target_output == "google_doc_markdown":
        output.google_doc_markdown = _sanitize_optional_text(generated_text)
    elif target_output == "loom_script":
        output.loom_script = _sanitize_optional_text(generated_text)
    elif target_output == "proposal_text":
        output.proposal_text = _sanitize_optional_text(generated_text)
    else:
        raise AppException(
            status_code=422,
            code="invalid_target_output",
            message="Unsupported target output",
        )

    _append_edit_log(
        output=output,
        action="regenerate",
        target_output=target_output,
        changed_fields=[target_output],
        instruction=_sanitize_optional_text(instruction),
    )

    await session.commit()
    await session.refresh(output)
    return output


async def generate_doc_flowchart_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    flowchart_instruction: str | None = None,
    connection_style: str | None = None,
) -> JobOutput:
    await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await _find_job_output(session=session, job_id=job_id)
    if output is None:
        raise AppException(status_code=404, code="job_output_not_found", message="Job output not found")

    markdown = (output.google_doc_markdown or "").strip()
    if not markdown:
        raise AppException(
            status_code=422,
            code="doc_content_missing",
            message="Generate or save doc content before creating flowchart",
        )

    section_match = _extract_flowchart_source_section(markdown)
    section_kind = section_match[0] if section_match else None
    preferred_section_text = section_match[1] if section_match else None

    google_connector = await get_connector_for_user(
        session=session,
        user_id=user_id,
        connector_name="google_docs",
    )
    if google_connector.status != "connected":
        raise AppException(
            status_code=422,
            code="google_docs_not_connected",
            message="Google Docs connector must be connected to stage flowchart image",
        )

    access_token = await resolve_google_access_token(google_connector.credential_ref)
    settings = get_settings()
    max_canvas_width = _clamp(settings.diagram_canvas_width, 1200, 2000)
    max_canvas_height = _clamp(settings.diagram_canvas_height, 700, 1200)
    selected_canvas_width = max_canvas_width
    selected_canvas_height = max_canvas_height
    normalized_connection_style = _normalize_connection_style(connection_style)

    selected_spec_result = None
    selected_quality = None
    selected_render_mode = "ai"
    validation_attempts: list[dict[str, Any]] = []

    for attempt in range(1, _FLOWCHART_MAX_ATTEMPTS + 1):
        attempt_instruction = flowchart_instruction
        if attempt > 1 and flowchart_instruction:
            attempt_instruction = (
                f"{flowchart_instruction.strip()}\n"
                "Variant: keep connectors clean, avoid crossings, and preserve left-to-right readability."
            )
        spec_result = await build_diagram_spec(
            markdown=markdown,
            preferred_section_text=preferred_section_text,
            preferred_section_kind=section_kind,
            instruction=attempt_instruction,
            connection_style=normalized_connection_style,
        )
        attempt_width, attempt_height = _derive_canvas_size(
            spec=spec_result.spec,
            max_width=max_canvas_width,
            max_height=max_canvas_height,
        )
        quality = validate_diagram_quality(spec=spec_result.spec, width=attempt_width, height=attempt_height)
        validation_attempts.append(
            {
                "attempt": attempt,
                "spec_source": spec_result.source,
                "model_name": spec_result.model_name,
                "provider_name": spec_result.provider_name,
                "canvas_width": attempt_width,
                "canvas_height": attempt_height,
                "quality_score": quality.score,
                "quality_status": quality.status,
                "validation_errors": list(quality.errors),
                "validation_warnings": list(quality.warnings),
            }
        )
        if quality.passed:
            selected_spec_result = spec_result
            selected_quality = quality
            selected_render_mode = "ai" if spec_result.source.startswith("llm") else "fallback"
            selected_canvas_width = attempt_width
            selected_canvas_height = attempt_height
            break

    if selected_spec_result is None or selected_quality is None:
        deterministic = build_deterministic_diagram_spec(
            markdown=markdown,
            preferred_section_text=preferred_section_text,
            instruction=flowchart_instruction,
            connection_style=normalized_connection_style,
        )
        deterministic.spec.layout_family = "roadmap_cards"
        deterministic.spec.connection_style = "clean"
        deterministic.spec.connections = [
            DiagramConnection(
                source_id=deterministic.spec.steps[idx].id,
                target_id=deterministic.spec.steps[idx + 1].id,
                edge_type="sequence",
            )
            for idx in range(len(deterministic.spec.steps) - 1)
        ]
        deterministic_width, deterministic_height = _derive_canvas_size(
            spec=deterministic.spec,
            max_width=max_canvas_width,
            max_height=max_canvas_height,
        )
        deterministic_quality = validate_diagram_quality(
            spec=deterministic.spec,
            width=deterministic_width,
            height=deterministic_height,
        )
        validation_attempts.append(
            {
                "attempt": "fallback",
                "spec_source": deterministic.source,
                "model_name": deterministic.model_name,
                "provider_name": deterministic.provider_name,
                "canvas_width": deterministic_width,
                "canvas_height": deterministic_height,
                "quality_score": deterministic_quality.score,
                "quality_status": deterministic_quality.status,
                "validation_errors": list(deterministic_quality.errors),
                "validation_warnings": list(deterministic_quality.warnings),
            }
        )
        if not deterministic_quality.passed:
            deterministic.spec.steps = deterministic.spec.steps[:6]
            deterministic.spec.connections = [
                DiagramConnection(
                    source_id=deterministic.spec.steps[idx].id,
                    target_id=deterministic.spec.steps[idx + 1].id,
                    edge_type="sequence",
                )
                for idx in range(len(deterministic.spec.steps) - 1)
            ]
            deterministic_width, deterministic_height = _derive_canvas_size(
                spec=deterministic.spec,
                max_width=max_canvas_width,
                max_height=max_canvas_height,
            )
            deterministic_quality = validate_diagram_quality(
                spec=deterministic.spec,
                width=deterministic_width,
                height=deterministic_height,
            )
        if not deterministic_quality.passed:
            raise AppException(
                status_code=422,
                code="diagram_quality_failed",
                message="Unable to produce a quality-safe diagram. Please regenerate with different instructions.",
                details={
                    "quality_score": deterministic_quality.score,
                    "validation_errors": list(deterministic_quality.errors),
                    "validation_attempts": validation_attempts,
                },
            )
        selected_spec_result = deterministic
        selected_quality = deterministic_quality
        selected_render_mode = "fallback"
        selected_canvas_width = deterministic_width
        selected_canvas_height = deterministic_height

    svg = render_diagram_svg(
        spec=selected_spec_result.spec,
        width=selected_canvas_width,
        height=selected_canvas_height,
    )
    image_bytes = await convert_svg_to_png(
        svg_content=svg,
        width=selected_canvas_width,
        height=selected_canvas_height,
    )
    if not image_bytes.startswith(b"\x89PNG"):
        raise AppException(
            status_code=503,
            code="diagram_render_invalid_format",
            message="Diagram render did not produce a valid PNG image",
        )
    if len(image_bytes) < 1024:
        raise AppException(
            status_code=503,
            code="diagram_render_too_small",
            message="Diagram render output is unexpectedly small",
        )
    mime_type = "image/png"
    title = _extract_title(markdown)

    image_url = await GoogleDocsClient().upload_public_image(
        access_token=access_token,
        image_bytes=image_bytes,
        mime_type=mime_type,
        filename=f"{title[:80]}-flowchart.png",
    )

    words_sent = _word_count(preferred_section_text or markdown)
    request_id = f"diagram-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
    inline_svg_data_url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")

    _archive_existing_artifact_version(output=output, artifact_type=_FLOWCHART_ARTIFACT_TYPE)
    _upsert_extra_file_entry(
        output=output,
        artifact_type=_FLOWCHART_ARTIFACT_TYPE,
        payload={
            "status": "ready",
            "image_url": image_url,
            "mime_type": mime_type,
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "svg_template",
            "request_id": request_id,
            "flowchart_instruction": _sanitize_optional_text(flowchart_instruction),
            "words_sent": words_sent,
            "estimated_credits_used": 0,
            "estimated_free_weekly_images_at_this_size": None,
            "render_engine": "svg_template",
            "render_mode": selected_render_mode,
            "layout_family": selected_spec_result.spec.layout_family,
            "orientation": selected_spec_result.spec.orientation,
            "creativity_level": selected_spec_result.spec.creativity_level,
            "connection_style": selected_spec_result.spec.connection_style,
            "model_name": selected_spec_result.model_name,
            "provider_name": selected_spec_result.provider_name,
            "spec_source": selected_spec_result.source,
            "input_tokens": selected_spec_result.input_tokens,
            "output_tokens": selected_spec_result.output_tokens,
            "quality_score": selected_quality.score,
            "quality_status": (
                "fallback_passed"
                if selected_render_mode == "fallback" and selected_quality.passed
                else selected_quality.status
            ),
            "validation_errors": list(selected_quality.errors),
            "validation_warnings": list(selected_quality.warnings),
            "validation_attempts": validation_attempts,
            "inline_svg_data_url": inline_svg_data_url,
        },
    )
    _append_edit_log(
        output=output,
        action="generate_flowchart",
        target_output="doc_flowchart",
        changed_fields=["extra_files_json", "artifact_versions_json"],
        instruction=_sanitize_optional_text(flowchart_instruction),
    )

    await session.commit()
    await session.refresh(output)
    return output


def serialize_job_output(output: JobOutput) -> dict[str, Any]:
    doc_flowchart = None
    for entry in reversed(output.extra_files_json or []):
        if entry.get("artifact_type") == _FLOWCHART_ARTIFACT_TYPE:
            doc_flowchart = entry
            break
    return {
        "id": str(output.id),
        "job_id": str(output.job_id),
        "google_doc_url": output.google_doc_url,
        "google_doc_markdown": output.google_doc_markdown,
        "workflow_jsons": output.workflow_jsons,
        "workflow_explanation": output.workflow_explanation,
        "loom_script": output.loom_script,
        "proposal_text": output.proposal_text,
        "doc_flowchart": doc_flowchart,
        "extra_files_json": output.extra_files_json,
        "edit_log_json": output.edit_log_json,
        "artifact_versions_json": output.artifact_versions_json,
        "approval_snapshot_json": output.approval_snapshot_json,
        "ai_usage_summary_json": output.ai_usage_summary_json,
        "updated_at": output.updated_at.isoformat() if output.updated_at else None,
    }
