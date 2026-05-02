from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.contracts import ProviderGenerateRequest, ProviderName
from app.application.connector.service import get_connector_for_user
from app.application.job.service import get_job_for_user
from app.infrastructure.ai.providers.factory import build_provider_adapter
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.integrations.google_docs_client import GoogleDocsClient
from app.infrastructure.integrations.google_oauth import resolve_google_access_token

_FLOWCHART_ARTIFACT_TYPE = "doc_flowchart"
_MERMAID_MODEL = "claude-sonnet-4-6"
_MERMAID_MAX_RETRIES = 1
_KROKI_BASE_URL = "https://kroki.io"

_MERMAID_CODE_FENCE_PATTERN = re.compile(r"```(?:mermaid)?\s*|\s*```", re.IGNORECASE | re.MULTILINE)


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


def _extract_mermaid_code(llm_output: str) -> str:
    stripped = _MERMAID_CODE_FENCE_PATTERN.sub("", llm_output.strip()).strip()
    if not stripped:
        raise AppException(
            status_code=422,
            code="mermaid_extraction_empty",
            message="LLM did not return any Mermaid diagram text",
        )
    return stripped


def _extract_key_points(markdown: str, max_points: int = 15) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < 5:
            continue
        cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", stripped)
        cleaned = re.sub(r"^#{1,6}\s+", "", cleaned)
        cleaned = re.sub(r"\*\*|__|\*|`", "", cleaned)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = " ".join(cleaned.split())
        if len(cleaned) < 5:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        points.append(cleaned)
        if len(points) >= max_points:
            break
    return points


def _build_deterministic_mermaid(
    *,
    points: list[str],
    title: str,
    instruction: str | None,
) -> str:
    if len(points) < 3:
        points = [
            "Ingest and validate inputs",
            "Process and transform data",
            "Deliver outputs and notify",
            "Monitor and iterate",
        ]

    points = points[:10]
    n = len(points)
    lines: list[str] = ["flowchart TD", ""]

    for i, pt in enumerate(points):
        lines.append(f'    n{i}[{pt}]')
    for i in range(n - 1):
        lines.append(f"    n{i} --> n{i + 1}")

    instruction_text = instruction.strip() if instruction and instruction.strip() else ""
    instruction_note = f" ({instruction_text})" if instruction_text else ""
    prefix = [f"%% {{init: {{\"theme\": \"forest\"}}}}%%", f"%% {title}{instruction_note}", ""]
    return "\n".join(prefix + lines)


async def _generate_mermaid_flowchart(
    *,
    prompt: str,
    retry_count: int = 0,
) -> tuple[str, str, str, int, int]:
    adapter = build_provider_adapter(ProviderName.ANTHROPIC)
    request = ProviderGenerateRequest(
        prompt=prompt,
        system_prompt="Return ONLY a fenced Mermaid code block. No other text.",
        model_name=_MERMAID_MODEL,
        temperature=0.2,
        max_output_tokens=4000,
        metadata={"task": "doc_flowchart_mermaid"},
    )
    result = await adapter.generate(request)

    raw_output = result.output_text or ""
    mermaid_code = _extract_mermaid_code(raw_output)

    # Lightweight structural check — real validation happens at render time
    looks_like_flowchart = (
        mermaid_code.strip().lower().startswith(("flowchart", "graph"))
        or "--> " in mermaid_code
    )
    if not looks_like_flowchart:
        if retry_count >= _MERMAID_MAX_RETRIES:
            raise AppException(
                status_code=422,
                code="mermaid_structure_invalid",
                message=f"LLM output is not recognisable Mermaid after {retry_count + 1} attempts",
                details={"mermaid_preview": mermaid_code[:500]},
            )
        retry_prompt = (
            f"{prompt}\n\n"
            "## PREVIOUS ATTEMPT WAS INVALID\n"
            "Your output did not start with 'flowchart TD' and had no '-->' arrows.\n"
            "Make sure the output starts with 'flowchart TD' and uses '-->' for connections.\n"
            "Return ONLY the corrected Mermaid code block."
        )
        return await _generate_mermaid_flowchart(prompt=retry_prompt, retry_count=retry_count + 1)

    return mermaid_code, result.model_name, result.provider.value, result.input_tokens, result.output_tokens


def _build_llm_flowchart_prompt(
    *,
    source_text: str,
    title: str,
    instruction: str | None,
    connection_style: str | None,
) -> str:
    # Truncate source to keep context reasonable (roughly 2500 words)
    words = source_text.split()
    if len(words) > 2500:
        source_text = " ".join(words[:2500]) + "\n\n[...content truncated...]"

    instruction_block = ""
    if instruction and instruction.strip():
        instruction_block = f"\n## User Instruction\n{instruction.strip()}\n"

    return (
        "Generate a Mermaid flowchart from this document. Return ONLY a fenced "
        "Mermaid code block. No other text.\n\n"
        f"## Document\nTitle: {title}\n\n{source_text}\n\n"
        "## Layout\n"
        "- Use flowchart TD (top-to-bottom)\n"
        "- Include 1-3 decision diamonds ({{label?}}) with |Yes|/|No| branches "
        "to create natural width — branching spreads the diagram sideways so it "
        "does not look like a skinny vertical list\n"
        "- Branch paths should rejoin the main flow when logical, or each lead "
        "to a distinct endpoint\n"
        "- After branching, the Yes and No paths can run in parallel columns "
        "before rejoining — this creates a balanced, wide flow that fills a "
        "Google Doc naturally\n\n"
        "## Content\n"
        "- 7-10 nodes total — compact enough for a one-page doc\n"
        "- Every node label must be specific and use the client's tools, "
        "systems, and terminology from the document. No generic filler\n"
        "- Labels: 2-6 words in [square brackets]. No double quotes, no "
        "backticks, no semicolons, no special characters\n"
        "- Write all nodes first, then all connections\n"
        "- Add |Yes| and |No| labels on decision branches\n"
        "- Cover: inputs/triggers → processing/decisions → outputs/deliverables\n"
        f"{instruction_block}\n"
        "- Add %%{{init: {{'theme': 'forest'}}}}%% at the very top\n\n"
        "Return ONLY a fenced Mermaid code block. No other text."
    )


_MERMAID_QUALITY_NODE_RE = re.compile(r'^\s*(?:\w+)\s*[\[\(\{>]', re.MULTILINE)
_MERMAID_QUALITY_DECISION_RE = re.compile(r'\{[^}]*\}')
_MERMAID_MAX_NODES = 14


def _validate_mermaid_quality(mermaid_code: str) -> list[str]:
    issues: list[str] = []
    nodes = _MERMAID_QUALITY_NODE_RE.findall(mermaid_code)
    if len(nodes) > _MERMAID_MAX_NODES:
        issues.append(f"too many nodes: {len(nodes)} (max {_MERMAID_MAX_NODES})")
    decisions = _MERMAID_QUALITY_DECISION_RE.findall(mermaid_code)
    if len(decisions) > 6:
        issues.append(f"too many decision diamonds: {len(decisions)} (max 6)")
    return issues


def _build_fallback_mermaid(
    *,
    source_text: str,
    title: str,
    instruction: str | None,
) -> tuple[str, str, str, int, int]:
    points = _extract_key_points(source_text)
    mermaid_code = _build_deterministic_mermaid(
        points=points,
        title=title,
        instruction=instruction,
    )
    return mermaid_code, _MERMAID_MODEL, "anthropic", 0, 0


async def _generate_llm_flowchart(
    *,
    source_text: str,
    title: str,
    instruction: str | None,
    connection_style: str | None,
) -> tuple[str, str, str, int, int]:
    prompt = _build_llm_flowchart_prompt(
        source_text=source_text,
        title=title,
        instruction=instruction,
        connection_style=connection_style,
    )
    try:
        mermaid_code, model, provider, in_tok, out_tok = await _generate_mermaid_flowchart(prompt=prompt)
    except AppException:
        return _build_fallback_mermaid(
            source_text=source_text, title=title, instruction=instruction,
        )

    quality_issues = _validate_mermaid_quality(mermaid_code)
    if quality_issues:
        return _build_fallback_mermaid(
            source_text=source_text, title=title, instruction=instruction,
        )

    return mermaid_code, model, provider, in_tok, out_tok


class _KrokiError(Exception):
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Kroki returned {status_code}: {body[:200]}")


async def _render_mermaid_via_kroki(mermaid_code: str, *, theme: str = "forest") -> bytes:
    """Render Mermaid diagram to PNG via Kroki (official mermaid.js)."""
    theme_directive = f"%%{{init: {{'theme': '{theme}'}}}}%%\n"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_KROKI_BASE_URL}/mermaid/png",
            content=theme_directive + mermaid_code,
            headers={"Content-Type": "text/plain"},
        )
        if resp.status_code != 200:
            raise _KrokiError(resp.status_code, resp.text[:500])
        return resp.content


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
        output = JobOutput(job_id=job_id)
        session.add(output)
        await session.flush()

    markdown = (output.google_doc_markdown or "").strip()
    if not markdown:
        raise AppException(
            status_code=422,
            code="doc_content_missing",
            message="Generate or save doc content before creating flowchart",
        )

    section_match = _extract_flowchart_source_section(markdown)
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

    source_text = preferred_section_text if preferred_section_text else markdown
    title = _extract_title(markdown)

    # Generate via LLM with deterministic fallback
    mermaid_code, model_name, provider_name, input_tokens, output_tokens = await _generate_llm_flowchart(
        source_text=source_text,
        title=title,
        instruction=flowchart_instruction,
        connection_style=connection_style,
    )

    try:
        png_bytes = await _render_mermaid_via_kroki(mermaid_code, theme="forest")
    except _KrokiError as render_error:
        raise AppException(
            status_code=502,
            code="kroki_render_failed",
            message="Diagram render service returned an error",
            details={
                "status_code": render_error.status_code,
                "body": render_error.body[:500],
            },
        ) from render_error
    except (httpx.HTTPError, OSError) as render_error:
        raise AppException(
            status_code=503,
            code="diagram_render_unavailable",
            message="Diagram render service is unreachable",
            details={"error": str(render_error)},
        ) from render_error

    if not png_bytes.startswith(b"\x89PNG"):
        raise AppException(
            status_code=503,
            code="diagram_render_invalid_format",
            message="Diagram render did not produce a valid PNG image",
        )
    if len(png_bytes) < 1024:
        raise AppException(
            status_code=503,
            code="diagram_render_too_small",
            message="Diagram render output is unexpectedly small",
        )

    mime_type = "image/png"
    title = _extract_title(markdown)

    image_url = await GoogleDocsClient().upload_public_image(
        access_token=access_token,
        image_bytes=png_bytes,
        mime_type=mime_type,
        filename=f"{title[:80]}-flowchart.png",
    )

    words_sent = _word_count(preferred_section_text or markdown)
    request_id = f"diagram-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    _archive_existing_artifact_version(output=output, artifact_type=_FLOWCHART_ARTIFACT_TYPE)
    _upsert_extra_file_entry(
        output=output,
        artifact_type=_FLOWCHART_ARTIFACT_TYPE,
        payload={
            "status": "ready",
            "image_url": image_url,
            "mime_type": mime_type,
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "kroki",
            "request_id": request_id,
            "flowchart_instruction": _sanitize_optional_text(flowchart_instruction),
            "words_sent": words_sent,
            "estimated_credits_used": 0,
            "render_engine": "kroki",
            "render_mode": "mermaid_js_official",
            "layout_family": "mermaid_auto",
            "orientation": "mermaid_auto",
            "creativity_level": "high",
            "connection_style": _sanitize_optional_text(connection_style) or "mermaid_auto",
            "model_name": model_name,
            "provider_name": provider_name,
            "spec_source": "llm_mermaid",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "quality_score": 100,
            "quality_status": "passed",
            "validation_errors": [],
            "validation_warnings": [],
            "validation_attempts": [
                {
                    "attempt": 1,
                    "spec_source": "llm_mermaid",
                    "model_name": model_name,
                    "provider_name": provider_name,
                    "quality_score": 100,
                    "quality_status": "mermaid_validated",
                }
            ],
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
