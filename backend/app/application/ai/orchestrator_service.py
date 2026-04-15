from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.contracts import (
    ArtifactPayload,
    ArtifactType,
    AutomationPlatform,
    AutomationPlatformPreference,
    GenerationPlan,
    GenerationPlanItem,
    JobClassification,
    JobUnderstandingExecution,
    JobType,
    ProviderGenerateRequest,
    RouteTask,
    RoutingMode,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.costing import estimate_call_cost_usd
from app.application.ai.guardrails import assert_safe_input, assert_safe_output
from app.application.ai.agents.ghl_agent import run_ghl_agent
from app.application.ai.agents.make_agent import run_make_agent
from app.application.ai.agents.n8n_agent import run_n8n_agent
from app.application.ai.job_understanding_service import JobUnderstandingService
from app.application.ai.planner_service import build_generation_plan, resolve_workflow_task
from app.application.ai.policy_service import assert_output_token_budget, enforce_generation_policy
from app.application.ai.prompt_builder import build_prompt
from app.application.ai.skills.n8n.node_catalog import get_node_schema
from app.application.ai.workflow_intent_service import extract_workflow_intent, workflow_intent_to_context
from app.application.ai.run_tracking_service import (
    append_artifact_version,
    create_generation_run,
    mark_generation_run_failed,
    mark_generation_run_success,
)
from app.application.ai.routing import get_route_for_task
from app.application.ai.validators import validate_artifact_payload
from app.application.job.service import get_job_for_user
from app.application.profile.service import get_profile_by_user_id
from app.infrastructure.ai.providers.factory import build_provider_adapter
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_generation_run import JobGenerationRun
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.database.models.user_profile import UserProfile
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.observability.metrics import metrics_state


class GenerationGraphState(TypedDict, total=False):
    session: AsyncSession
    user_id: UUID
    job_id: UUID
    run_type: str
    target_artifact: str | None
    instruction: str | None
    additional_context: dict[str, Any]
    run_id: UUID
    job: Job
    profile: UserProfile | None
    understanding: JobUnderstandingExecution
    classification: JobClassification
    plan: GenerationPlan
    retry_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int
    total_estimated_cost_usd: Decimal


_ARTIFACT_FIELD_MAP: dict[ArtifactType, str] = {
    ArtifactType.PROPOSAL: "proposal_text",
    # Cover letter is currently treated as proposal output.
    ArtifactType.COVER_LETTER: "proposal_text",
    ArtifactType.LOOM_SCRIPT: "loom_script",
    ArtifactType.DOC: "google_doc_markdown",
    ArtifactType.WORKFLOW: "workflow_jsons",
    ArtifactType.MAKE_WORKFLOW: "workflow_jsons",
    ArtifactType.GHL_WORKFLOW: "workflow_jsons",
}


def _coerce_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _state_usage_snapshot(state: GenerationGraphState) -> dict[str, int | Decimal]:
    return {
        "input_tokens": int(state.get("total_input_tokens", 0)),
        "output_tokens": int(state.get("total_output_tokens", 0)),
        "latency_ms": int(state.get("total_latency_ms", 0)),
        "retry_count": int(state.get("retry_count", 0)),
        "estimated_cost_usd": _coerce_decimal(state.get("total_estimated_cost_usd", Decimal("0"))),
    }


def _extract_artifact_usage(metadata: dict[str, Any]) -> tuple[int, int, int, Decimal]:
    usage = metadata.get("usage")
    if not isinstance(usage, dict):
        return 0, 0, 0, Decimal("0")
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    latency_ms = int(usage.get("latency_ms", 0) or 0)
    cost_value = _coerce_decimal(usage.get("estimated_cost_usd", 0))
    return max(0, input_tokens), max(0, output_tokens), max(0, latency_ms), cost_value


def _parse_workflow_json(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Workflow output is not valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Workflow output must be a JSON object",
        )
    return parsed


def _ensure_workflow_defaults(workflow_json: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow_json.get("nodes")
    if isinstance(nodes, list):
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            if not str(node.get("id") or "").strip():
                node["id"] = f"node_{idx + 1}"
            if not str(node.get("name") or "").strip():
                node["name"] = f"Node {idx + 1}"

            if not isinstance(node.get("typeVersion"), (int, float)):
                node_type = str(node.get("type") or "").strip()
                schema = get_node_schema(node_type) if node_type else None
                schema_type_version = schema.get("typeVersion") if isinstance(schema, dict) else None
                node["typeVersion"] = (
                    schema_type_version if isinstance(schema_type_version, (int, float)) else 1
                )

            position = node.get("position")
            if (
                not isinstance(position, list)
                or len(position) != 2
                or not all(isinstance(v, (int, float)) for v in position)
            ):
                node["position"] = [260 + (idx * 220), 300]

    if not isinstance(workflow_json.get("connections"), dict):
        workflow_json["connections"] = {}

    settings = workflow_json.get("settings")
    if not isinstance(settings, dict):
        workflow_json["settings"] = {"executionOrder": "v1"}
    elif not isinstance(settings.get("executionOrder"), str) or not settings.get("executionOrder", "").strip():
        settings["executionOrder"] = "v1"

    return workflow_json


def _summarize_text_for_prompt(text: str | None, *, max_chars: int = 420) -> str | None:
    if not text:
        return None
    collapsed = " ".join(text.strip().split())
    if not collapsed:
        return None
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[:max_chars].rstrip()}..."


def _summarize_workflow_json_for_prompt(workflow_json: dict[str, Any] | None) -> str | None:
    if not isinstance(workflow_json, dict):
        return None
    nodes = workflow_json.get("nodes")
    if isinstance(nodes, list):
        node_names = [
            str(node.get("name")).strip()
            for node in nodes
            if isinstance(node, dict) and str(node.get("name", "")).strip()
        ]
        if node_names:
            preview = ", ".join(node_names[:5])
            if len(node_names) > 5:
                preview = f"{preview}, +{len(node_names) - 5} more"
            return f"Workflow has {len(node_names)} nodes: {preview}"

    flow = workflow_json.get("flow")
    if isinstance(flow, list):
        return f"Workflow blueprint has {len(flow)} top-level flow modules."

    steps = workflow_json.get("steps")
    if isinstance(steps, list):
        return f"Workflow build spec has {len(steps)} ordered steps."

    keys_preview = ", ".join(sorted(workflow_json.keys())[:5])
    return f"Workflow JSON available with keys: {keys_preview or 'none'}."


def _build_existing_artifact_summaries(output: JobOutput | None) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    if output is None:
        return summaries
    if output.google_doc_url:
        summaries["doc_url"] = output.google_doc_url

    doc_summary = _summarize_text_for_prompt(output.google_doc_markdown)
    if doc_summary:
        summaries["doc_summary"] = doc_summary

    loom_summary = _summarize_text_for_prompt(output.loom_script)
    if loom_summary:
        summaries["loom_summary"] = loom_summary

    workflow_entries = output.workflow_jsons or []
    if workflow_entries and isinstance(workflow_entries[0], dict):
        workflow_summary = _summarize_workflow_json_for_prompt(workflow_entries[0].get("workflow_json"))
        if workflow_summary:
            summaries["workflow_summary"] = workflow_summary

    return summaries


def _merge_artifact_summary(
    *,
    summaries: dict[str, Any],
    artifact_type: ArtifactType,
    content_text: str | None,
    content_json: dict[str, Any] | None,
) -> None:
    if artifact_type == ArtifactType.DOC:
        doc_summary = _summarize_text_for_prompt(content_text)
        if doc_summary:
            summaries["doc_summary"] = doc_summary
    elif artifact_type == ArtifactType.LOOM_SCRIPT:
        loom_summary = _summarize_text_for_prompt(content_text)
        if loom_summary:
            summaries["loom_summary"] = loom_summary
    elif artifact_type == ArtifactType.WORKFLOW:
        workflow_summary = _summarize_workflow_json_for_prompt(content_json)
        if workflow_summary:
            summaries["workflow_summary"] = workflow_summary


def _artifact_execution_priority(item: GenerationPlanItem) -> int:
    # Generate supporting artifacts first so proposal/cover letter can reference
    # concrete doc/loom/workflow summaries.
    by_artifact: dict[ArtifactType, int] = {
        ArtifactType.WORKFLOW: 10,
        ArtifactType.DOC: 20,
        ArtifactType.LOOM_SCRIPT: 30,
        ArtifactType.COVER_LETTER: 40,
        ArtifactType.PROPOSAL: 40,
    }
    return by_artifact.get(item.artifact_type, 100)


async def _load_job_context(state: GenerationGraphState) -> GenerationGraphState:
    session = state["session"]
    job = await get_job_for_user(session=session, user_id=state["user_id"], job_id=state["job_id"])
    profile = await get_profile_by_user_id(session=session, user_id=state["user_id"])
    if not job.job_markdown:
        raise AppException(
            status_code=422,
            code="job_markdown_missing",
            message="Job markdown is required before generation",
        )
    return {"job": job, "profile": profile}


async def _run_understanding(state: GenerationGraphState) -> GenerationGraphState:
    job = state["job"]
    profile = state.get("profile")
    understanding_service = JobUnderstandingService()
    assert_safe_input(content=job.job_markdown or "", context="job_markdown")
    if job.notes_markdown:
        assert_safe_input(content=job.notes_markdown, context="notes_markdown")
    profile_context = profile.upwork_profile_markdown if profile else None
    if profile_context:
        assert_safe_input(content=profile_context, context="profile_context")
    understanding = await understanding_service.understand_job(
        job_markdown=job.job_markdown or "",
        notes_markdown=job.notes_markdown,
        profile_context=profile_context,
    )
    understanding_cost = estimate_call_cost_usd(
        provider=understanding.provider,
        input_tokens=understanding.input_tokens,
        output_tokens=understanding.output_tokens,
    )
    return {
        "understanding": understanding,
        "total_input_tokens": int(state.get("total_input_tokens", 0)) + understanding.input_tokens,
        "total_output_tokens": int(state.get("total_output_tokens", 0)) + understanding.output_tokens,
        "total_latency_ms": int(state.get("total_latency_ms", 0)) + understanding.latency_ms,
        "total_estimated_cost_usd": _coerce_decimal(state.get("total_estimated_cost_usd", Decimal("0")))
        + understanding_cost,
    }


async def _build_plan(state: GenerationGraphState) -> GenerationGraphState:
    understanding = state["understanding"]
    job = state["job"]
    classification_obj = JobClassification(
        job_type=JobType(job.job_type) if job.job_type else JobType.OTHER,
        automation_platform=AutomationPlatform(job.automation_platform) if job.automation_platform else None,
        confidence=job.classification_confidence or "low",
        reasoning=job.classification_reasoning or "unknown",
    )
    plan = build_generation_plan(
        job_id=state["job_id"],
        user_id=state["user_id"],
        understanding=understanding.contract,
        classification=classification_obj,
    )
    target_artifact = state.get("target_artifact")
    if target_artifact:
        filtered_items = [item for item in plan.items if item.artifact_type.value == target_artifact]
        if not filtered_items:
            # Resolve the workflow task dynamically based on the job's
            # classification/understanding so regeneration routes to the
            # correct platform-specific agent (n8n / Make / GHL).
            resolved_workflow_task = resolve_workflow_task(
                classification=classification_obj,
                understanding=understanding.contract,
            )
            artifact_map: dict[str, tuple[ArtifactType, RouteTask | None]] = {
                "proposal": (ArtifactType.PROPOSAL, RouteTask.PROPOSAL),
                # cover_letter aliases proposal for now.
                "cover_letter": (ArtifactType.PROPOSAL, RouteTask.PROPOSAL),
                "loom_script": (ArtifactType.LOOM_SCRIPT, RouteTask.LOOM_SCRIPT),
                "workflow": (ArtifactType.WORKFLOW, resolved_workflow_task),
                "doc": (ArtifactType.DOC, RouteTask.DOC),
            }
            mapped = artifact_map.get(target_artifact)
            if not mapped:
                raise AppException(
                    status_code=422,
                    code="invalid_target_output",
                    message="Requested regenerate artifact is not supported",
                )
            if target_artifact == "workflow" and resolved_workflow_task is None:
                raise AppException(
                    status_code=422,
                    code="workflow_not_supported_for_job_type",
                    message=(
                        "Workflow generation is only supported for n8n, Make.com, "
                        "and GoHighLevel automation jobs."
                    ),
                )
            artifact_type, task = mapped
            if task is None:
                raise AppException(
                    status_code=422,
                    code="workflow_not_supported_for_job_type",
                    message=(
                        "Workflow generation is only supported for n8n, Make.com, "
                        "and GoHighLevel automation jobs."
                    ),
                )
            route = get_route_for_task(task)
            filtered_items = [
                GenerationPlanItem(
                    task=task,
                    artifact_type=artifact_type,
                    primary_provider=route.primary_provider,
                    primary_model=route.primary_model,
                    fallback_provider=route.fallback_provider,
                    fallback_model=route.fallback_model,
                )
            ]
            plan = GenerationPlan(
                job_id=plan.job_id,
                user_id=plan.user_id,
                routing_mode=RoutingMode.FIXED_PER_ARTIFACT,
                platform_preference=AutomationPlatformPreference.N8N,
                requires_platform_confirmation=False,
                items=filtered_items,
            )
            return {"plan": plan, "classification": classification_obj}
        plan.items = filtered_items
    policy = await enforce_generation_policy(
        session=state["session"],
        user_id=state["user_id"],
        job_markdown=state["job"].job_markdown or "",
        notes_markdown=state["job"].notes_markdown,
        instruction=state.get("instruction"),
        artifact_count_hint=len(plan.items),
    )
    if not policy.allowed:
        metrics_state.record_ai_policy_denied()
        raise AIException(
            code=AIErrorCode.BUDGET_EXCEEDED,
            message="Generation blocked by budget/quota policy",
            details=policy.details or {},
        )
    return {"plan": plan, "classification": classification_obj}


async def _get_or_create_job_output(*, session: AsyncSession, job_id: UUID) -> JobOutput:
    output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job_id))
    if output is not None:
        return output
    output = JobOutput(job_id=job_id)
    session.add(output)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Typical race: job deleted while generation is running.
        await session.rollback()
        raise AppException(status_code=404, code="job_not_found", message="Job not found") from exc
    return output


async def _safe_mark_generation_run_failed(
    *,
    session: AsyncSession,
    run_id: UUID,
    failure_code: str,
    failure_message: str,
    usage: dict[str, int | Decimal],
) -> None:
    # A previous flush/commit failure leaves the session in pending-rollback.
    # Clear it before best-effort failure tracking.
    try:
        await session.rollback()
    except Exception:
        pass

    try:
        await mark_generation_run_failed(
            session=session,
            run_id=run_id,
            failure_code=failure_code,
            failure_message=failure_message,
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            estimated_cost_usd=usage["estimated_cost_usd"],
            latency_ms=int(usage["latency_ms"]),
            retry_count=int(usage["retry_count"]),
        )
    except Exception:
        # Best-effort only; don't mask the original API error.
        try:
            await session.rollback()
        except Exception:
            pass


def _upsert_extra_file_entry(
    *, output: JobOutput, artifact_type: ArtifactType, content_text: str | None
) -> None:
    entries = [entry for entry in (output.extra_files_json or []) if entry.get("artifact_type") != artifact_type.value]
    entries.append(
        {
            "artifact_type": artifact_type.value,
            "content_text": content_text,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    output.extra_files_json = entries


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


async def _persist_generated_artifact(
    *,
    session: AsyncSession,
    job_id: UUID,
    run_id: UUID,
    run_type: str,
    artifact: ArtifactPayload,
    instruction: str | None,
) -> None:
    output = await _get_or_create_job_output(session=session, job_id=job_id)
    changed_fields: list[str] = []

    mapped_field = _ARTIFACT_FIELD_MAP.get(artifact.artifact_type)
    if mapped_field == "workflow_jsons":
        workflow_name_by_type: dict[ArtifactType, str] = {
            ArtifactType.WORKFLOW: "n8n",
            ArtifactType.MAKE_WORKFLOW: "make",
            ArtifactType.GHL_WORKFLOW: "ghl",
        }
        output.workflow_jsons = [
            {
                "name": workflow_name_by_type.get(artifact.artifact_type, "workflow"),
                "workflow_json": artifact.content_json or {},
            }
        ]
        changed_fields.append("workflow_jsons")
        output.workflow_explanation = artifact.content_text
        changed_fields.append("workflow_explanation")
    elif mapped_field == "proposal_text":
        output.proposal_text = artifact.content_text
        changed_fields.append("proposal_text")
    elif mapped_field == "loom_script":
        output.loom_script = artifact.content_text
        changed_fields.append("loom_script")
    elif mapped_field == "google_doc_markdown":
        output.google_doc_markdown = artifact.content_text
        changed_fields.append("google_doc_markdown")
    else:
        _upsert_extra_file_entry(output=output, artifact_type=artifact.artifact_type, content_text=artifact.content_text)
        changed_fields.append("extra_files_json")

    _append_edit_log(
        output=output,
        action=run_type,
        target_output=artifact.artifact_type.value,
        changed_fields=changed_fields,
        instruction=instruction,
    )
    await append_artifact_version(
        session=session,
        job_id=job_id,
        artifact_type=artifact.artifact_type.value,
        content_text=artifact.content_text,
        content_json=artifact.content_json,
        instruction=instruction,
        generation_run_id=run_id,
        is_selected=False,
    )


async def _generate_artifacts(state: GenerationGraphState) -> GenerationGraphState:
    session = state["session"]
    plan = state["plan"]
    job = state["job"]
    profile = state.get("profile")
    run_id = state["run_id"]
    instruction = state.get("instruction")
    runtime_context = state.get("additional_context") or {}
    run_type = state["run_type"]

    total_input_tokens = int(state.get("total_input_tokens", 0))
    total_output_tokens = int(state.get("total_output_tokens", 0))
    total_latency_ms = int(state.get("total_latency_ms", 0))
    retry_count = int(state.get("retry_count", 0))
    total_estimated_cost_usd = _coerce_decimal(state.get("total_estimated_cost_usd", Decimal("0")))

    def _sync_progress_to_state() -> None:
        state["total_input_tokens"] = total_input_tokens
        state["total_output_tokens"] = total_output_tokens
        state["total_latency_ms"] = total_latency_ms
        state["retry_count"] = retry_count
        state["total_estimated_cost_usd"] = total_estimated_cost_usd

    output_snapshot = await _get_or_create_job_output(session=session, job_id=state["job_id"])
    artifact_summaries = _build_existing_artifact_summaries(output_snapshot)
    execution_items = sorted(plan.items, key=_artifact_execution_priority)

    for item in execution_items:
        extra_context: dict[str, Any] = {}
        if item.task in {RouteTask.PROPOSAL, RouteTask.COVER_LETTER}:
            extra_context = {**artifact_summaries, **runtime_context}
        elif item.task == RouteTask.LOOM_SCRIPT:
            understanding = state.get("understanding")
            classification = state.get("classification")
            extra_context = {
                k: v
                for k, v in artifact_summaries.items()
                if k in {"workflow_summary", "doc_summary", "doc_url"}
            }
            if understanding is not None:
                extra_context["job_summary"] = understanding.contract.summary_short
                extra_context["automation_platform_preference"] = (
                    understanding.contract.automation_platform_preference.value
                )
                extra_context["deliverables_required"] = [
                    artifact.value for artifact in understanding.contract.deliverables_required
                ]
                extra_context["job_constraints"] = understanding.contract.constraints
                if understanding.contract.missing_fields:
                    extra_context["missing_fields"] = understanding.contract.missing_fields
            extra_context["job_type"] = job.job_type or "unknown"
            extra_context["automation_platform"] = job.automation_platform or "unknown"
            extra_context["classification_confidence"] = job.classification_confidence or "low"
            extra_context["classification_reasoning"] = job.classification_reasoning or "unknown"
            if classification is not None:
                extra_context["classified_job_type"] = classification.job_type.value
                extra_context["classified_platform"] = (
                    classification.automation_platform.value
                    if classification.automation_platform is not None
                    else "unknown"
                )
        elif item.task == RouteTask.DOC:
            workflow_summary = (
                artifact_summaries.get("workflow_summary")
                or runtime_context.get("workflow_summary")
                or "None"
            )
            extra_context = {
                **runtime_context,
                "workflow_summary": workflow_summary,
            }
        elif item.task == RouteTask.WORKFLOW:
            intent_result = extract_workflow_intent(
                job_markdown=job.job_markdown or "",
                notes_markdown=job.notes_markdown,
                custom_instruction=instruction,
            )
            extra_context = {
                **runtime_context,
                **workflow_intent_to_context(intent_result.intent),
            }
        elif item.task == RouteTask.MAKE_WORKFLOW:
            intent_result = extract_workflow_intent(
                job_markdown=job.job_markdown or "",
                notes_markdown=job.notes_markdown,
                custom_instruction=instruction,
            )
            extra_context = {
                **runtime_context,
                **workflow_intent_to_context(intent_result.intent),
            }
        elif item.task == RouteTask.GHL_WORKFLOW:
            intent_result = extract_workflow_intent(
                job_markdown=job.job_markdown or "",
                notes_markdown=job.notes_markdown,
                custom_instruction=instruction,
            )
            extra_context = {
                **runtime_context,
                **workflow_intent_to_context(intent_result.intent),
            }
        prompt = build_prompt(
            task=item.task,
            context={
                "job_markdown": job.job_markdown,
                "notes_markdown": job.notes_markdown,
                "profile_context": profile.upwork_profile_markdown if profile else None,
                "custom_instruction": instruction,
                "custom_global_instruction": profile.custom_global_instruction if profile else None,
                "proposal_template": profile.proposal_template if profile else None,
                "doc_template": profile.doc_template if profile else None,
                "loom_template": profile.loom_template if profile else None,
                "workflow_template_notes": profile.workflow_template_notes if profile else None,
                "custom_prompt_blocks": profile.custom_prompt_blocks if profile else [],
                "extra_context": extra_context,
            },
        )
        artifact_payload: ArtifactPayload
        if item.task == RouteTask.MAKE_WORKFLOW:
            primary_provider = build_provider_adapter(item.primary_provider)
            if not isinstance(primary_provider, AnthropicProviderAdapter):
                raise AIException(
                    code=AIErrorCode.INVALID_ROUTE_CONFIG,
                    message="Make.com generator requires the Anthropic provider",
                    details={"provider": item.primary_provider.value},
                )
            artifact_payload = await run_make_agent(
                job_context={
                    "job_markdown": job.job_markdown,
                    "notes_markdown": job.notes_markdown,
                    "profile_context": profile.upwork_profile_markdown if profile else None,
                    "custom_instruction": instruction,
                    "extra_context": extra_context,
                },
                provider=primary_provider,
                model_name=item.primary_model,
            )
            agent_input, agent_output, agent_latency, agent_cost = _extract_artifact_usage(
                artifact_payload.metadata
            )
            if agent_input or agent_output or agent_latency or agent_cost > Decimal("0"):
                total_input_tokens += agent_input
                total_output_tokens += agent_output
                total_latency_ms += agent_latency
                total_estimated_cost_usd += agent_cost
                _sync_progress_to_state()
        elif item.task == RouteTask.GHL_WORKFLOW:
            primary_provider = build_provider_adapter(item.primary_provider)
            if not isinstance(primary_provider, AnthropicProviderAdapter):
                raise AIException(
                    code=AIErrorCode.INVALID_ROUTE_CONFIG,
                    message="GoHighLevel generator requires the Anthropic provider",
                    details={"provider": item.primary_provider.value},
                )
            artifact_payload = await run_ghl_agent(
                job_context={
                    "job_markdown": job.job_markdown,
                    "notes_markdown": job.notes_markdown,
                    "profile_context": profile.upwork_profile_markdown if profile else None,
                    "custom_instruction": instruction,
                    "extra_context": extra_context,
                },
                provider=primary_provider,
                model_name=item.primary_model,
            )
            agent_input, agent_output, agent_latency, agent_cost = _extract_artifact_usage(
                artifact_payload.metadata
            )
            if agent_input or agent_output or agent_latency or agent_cost > Decimal("0"):
                total_input_tokens += agent_input
                total_output_tokens += agent_output
                total_latency_ms += agent_latency
                total_estimated_cost_usd += agent_cost
                _sync_progress_to_state()
        elif item.task == RouteTask.WORKFLOW:
            primary_provider = build_provider_adapter(item.primary_provider)
            if isinstance(primary_provider, AnthropicProviderAdapter):
                try:
                    artifact_payload = await run_n8n_agent(
                        job_context={
                            "job_markdown": job.job_markdown,
                            "notes_markdown": job.notes_markdown,
                            "profile_context": profile.upwork_profile_markdown if profile else None,
                            "custom_instruction": instruction,
                            "extra_context": extra_context,
                        },
                        provider=primary_provider,
                        model_name=item.primary_model,
                        max_iterations=5,
                    )
                except AIException as primary_error:
                    if item.fallback_provider and item.fallback_model:
                        retry_count += 1
                        metrics_state.record_ai_fallback()
                        _sync_progress_to_state()
                        provider_request = ProviderGenerateRequest(
                            prompt=prompt.user_prompt,
                            system_prompt=prompt.system_prompt,
                            model_name=item.fallback_model,
                            temperature=0.2,
                            max_output_tokens=3000,
                            metadata={"task": item.task.value, "artifact_type": item.artifact_type.value},
                        )
                        assert_safe_input(content=provider_request.prompt, context=f"prompt:{item.artifact_type.value}")
                        fallback_provider = build_provider_adapter(item.fallback_provider)
                        provider_result = await fallback_provider.generate(provider_request)
                        total_input_tokens += provider_result.input_tokens
                        total_output_tokens += provider_result.output_tokens
                        total_latency_ms += provider_result.latency_ms
                        total_estimated_cost_usd += estimate_call_cost_usd(
                            provider=provider_result.provider,
                            input_tokens=provider_result.input_tokens,
                            output_tokens=provider_result.output_tokens,
                        )
                        _sync_progress_to_state()
                        content_json = (
                            provider_result.output_json
                            if isinstance(provider_result.output_json, dict)
                            else _parse_workflow_json(provider_result.output_text or "")
                        )
                        content_json = _ensure_workflow_defaults(content_json)
                        artifact_payload = ArtifactPayload(
                            artifact_type=item.artifact_type,
                            content_text=None,
                            content_json=content_json,
                            metadata={
                                "provider": provider_result.provider.value,
                                "model_name": provider_result.model_name,
                                "agent_mode": "fallback_provider_single_turn",
                            },
                        )
                    else:
                        output = await _get_or_create_job_output(session=session, job_id=state["job_id"])
                        details = (
                            json.dumps(primary_error.details, ensure_ascii=True)
                            if isinstance(primary_error.details, dict)
                            else ""
                        )
                        output.workflow_explanation = (
                            f"Workflow generation failed: {primary_error.message}"
                            + (f"\nDetails: {details}" if details else "")
                        )[:120000]
                        raise primary_error
            else:
                provider_request = ProviderGenerateRequest(
                    prompt=prompt.user_prompt,
                    system_prompt=prompt.system_prompt,
                    model_name=item.primary_model,
                    temperature=0.2,
                    max_output_tokens=3000,
                    metadata={"task": item.task.value, "artifact_type": item.artifact_type.value},
                )
                assert_safe_input(content=provider_request.prompt, context=f"prompt:{item.artifact_type.value}")

                provider_result = None
                try:
                    provider_result = await primary_provider.generate(provider_request)
                except AIException as primary_error:
                    if item.fallback_provider and item.fallback_model:
                        retry_count += 1
                        metrics_state.record_ai_fallback()
                        _sync_progress_to_state()
                        fallback_provider = build_provider_adapter(item.fallback_provider)
                        provider_request.model_name = item.fallback_model
                        provider_result = await fallback_provider.generate(provider_request)
                    else:
                        raise primary_error

                if provider_result is None:
                    raise AIException(
                        code=AIErrorCode.ORCHESTRATION_FAILED,
                        message="Provider did not return a generation result",
                    )

                total_input_tokens += provider_result.input_tokens
                total_output_tokens += provider_result.output_tokens
                total_latency_ms += provider_result.latency_ms
                total_estimated_cost_usd += estimate_call_cost_usd(
                    provider=provider_result.provider,
                    input_tokens=provider_result.input_tokens,
                    output_tokens=provider_result.output_tokens,
                )
                _sync_progress_to_state()

                content_json = (
                    provider_result.output_json
                    if isinstance(provider_result.output_json, dict)
                    else _parse_workflow_json(provider_result.output_text or "")
                )
                content_json = _ensure_workflow_defaults(content_json)
                artifact_payload = ArtifactPayload(
                    artifact_type=item.artifact_type,
                    content_text=provider_result.output_text,
                    content_json=content_json,
                    metadata={
                        "provider": provider_result.provider.value,
                        "model_name": provider_result.model_name,
                        "agent_mode": "single_turn",
                    },
                )
        else:
            provider_request = ProviderGenerateRequest(
                prompt=prompt.user_prompt,
                system_prompt=prompt.system_prompt,
                model_name=item.primary_model,
                temperature=0.2,
                max_output_tokens=3000,
                metadata={"task": item.task.value, "artifact_type": item.artifact_type.value},
            )
            assert_safe_input(content=provider_request.prompt, context=f"prompt:{item.artifact_type.value}")

            provider_result = None
            try:
                primary_provider = build_provider_adapter(item.primary_provider)
                provider_result = await primary_provider.generate(provider_request)
            except AIException as primary_error:
                if item.fallback_provider and item.fallback_model:
                    retry_count += 1
                    metrics_state.record_ai_fallback()
                    _sync_progress_to_state()
                    fallback_provider = build_provider_adapter(item.fallback_provider)
                    provider_request.model_name = item.fallback_model
                    provider_result = await fallback_provider.generate(provider_request)
                else:
                    raise primary_error

            if provider_result is None:
                raise AIException(
                    code=AIErrorCode.ORCHESTRATION_FAILED,
                    message="Provider did not return a generation result",
                )

            # Count provider usage immediately after generation so failed validation still
            # contributes to run-level token/cost accounting.
            total_input_tokens += provider_result.input_tokens
            total_output_tokens += provider_result.output_tokens
            total_latency_ms += provider_result.latency_ms
            total_estimated_cost_usd += estimate_call_cost_usd(
                provider=provider_result.provider,
                input_tokens=provider_result.input_tokens,
                output_tokens=provider_result.output_tokens,
            )
            _sync_progress_to_state()

            content_text = provider_result.output_text
            content_json: dict[str, Any] | None = None
            if item.artifact_type == ArtifactType.WORKFLOW:
                if isinstance(provider_result.output_json, dict):
                    content_json = provider_result.output_json
                elif provider_result.output_text:
                    content_json = _parse_workflow_json(provider_result.output_text)
                else:
                    raise AIException(
                        code=AIErrorCode.INVALID_OUTPUT,
                        message="Workflow generation did not return JSON",
                    )
                content_json = _ensure_workflow_defaults(content_json)

            artifact_payload = ArtifactPayload(
                artifact_type=item.artifact_type,
                content_text=content_text,
                content_json=content_json,
                metadata={"provider": provider_result.provider.value, "model_name": provider_result.model_name},
            )
        if item.task == RouteTask.WORKFLOW:
            agent_input, agent_output, agent_latency, agent_cost = _extract_artifact_usage(
                artifact_payload.metadata
            )
            if agent_input or agent_output or agent_latency or agent_cost > Decimal("0"):
                total_input_tokens += agent_input
                total_output_tokens += agent_output
                total_latency_ms += agent_latency
                total_estimated_cost_usd += agent_cost
                _sync_progress_to_state()
        content_text = artifact_payload.content_text
        if content_text:
            try:
                assert_safe_output(content=content_text, artifact_type=item.artifact_type.value)
            except AIException:
                metrics_state.record_ai_guardrail_block()
                raise
        validation = validate_artifact_payload(artifact_payload)
        if not validation.is_valid:
            raise AIException(
                code=AIErrorCode.INVALID_OUTPUT,
                message="Generated artifact failed deterministic validation",
                details={"issues": [issue.model_dump() for issue in validation.issues]},
            )

        await _persist_generated_artifact(
            session=session,
            job_id=state["job_id"],
            run_id=run_id,
            run_type=run_type,
            artifact=artifact_payload,
            instruction=instruction,
        )
        _merge_artifact_summary(
            summaries=artifact_summaries,
            artifact_type=item.artifact_type,
            content_text=artifact_payload.content_text,
            content_json=artifact_payload.content_json if isinstance(artifact_payload.content_json, dict) else None,
        )

    assert_output_token_budget(total_output_tokens=total_output_tokens)
    _sync_progress_to_state()

    return {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_latency_ms": total_latency_ms,
        "retry_count": retry_count,
        "total_estimated_cost_usd": total_estimated_cost_usd,
    }


def serialize_generation_run(run: JobGenerationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "job_id": str(run.job_id),
        "user_id": str(run.user_id),
        "run_type": run.run_type,
        "artifact_type": run.artifact_type,
        "provider": run.provider,
        "model_name": run.model_name,
        "routing_mode": run.routing_mode,
        "prompt_version": run.prompt_version,
        "prompt_hash": run.prompt_hash,
        "status": run.status,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "estimated_cost_usd": float(run.estimated_cost_usd),
        "latency_ms": run.latency_ms,
        "retry_count": run.retry_count,
        "failure_code": run.failure_code,
        "failure_message": run.failure_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


async def run_generation_pipeline(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    run_type: str,
    target_artifact: str | None = None,
    instruction: str | None = None,
    additional_context: dict[str, Any] | None = None,
) -> JobGenerationRun:
    # Fail fast when the job is already gone/unauthorized.
    await get_job_for_user(session=session, user_id=user_id, job_id=job_id)

    # Guard against concurrent generation for the same job.
    existing_running = await session.scalar(
        select(JobGenerationRun.id).where(
            JobGenerationRun.job_id == job_id,
            JobGenerationRun.status == "running",
        )
    )
    if existing_running is not None:
        raise AppException(
            status_code=409,
            code="generation_already_running",
            message="A generation is already running for this job. Please wait for it to finish.",
        )

    understanding_route = get_route_for_task(RouteTask.JOB_UNDERSTANDING)
    run = await create_generation_run(
        session=session,
        job_id=job_id,
        user_id=user_id,
        run_type=run_type,
        artifact_type=target_artifact,
        provider=understanding_route.primary_provider.value,
        model_name=understanding_route.primary_model,
        routing_mode="fixed_per_artifact",
    )
    run_id = run.id

    initial_state: GenerationGraphState = {
        "session": session,
        "user_id": user_id,
        "job_id": job_id,
        "run_type": run_type,
        "target_artifact": target_artifact,
        "instruction": instruction,
        "additional_context": additional_context or {},
        "run_id": run_id,
        "retry_count": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_latency_ms": 0,
        "total_estimated_cost_usd": Decimal("0"),
    }
    runtime_state: GenerationGraphState = dict(initial_state)

    try:
        for step in (_load_job_context, _run_understanding, _build_plan, _generate_artifacts):
            update = await step(runtime_state)
            if update:
                runtime_state.update(update)

        final_state = runtime_state
        usage = _state_usage_snapshot(final_state)
        updated_run = await mark_generation_run_success(
            session=session,
            run_id=run_id,
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            estimated_cost_usd=usage["estimated_cost_usd"],
            latency_ms=int(usage["latency_ms"]),
            retry_count=int(usage["retry_count"]),
        )
        metrics_state.record_ai_run(
            success=True,
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            estimated_cost_usd=usage["estimated_cost_usd"],
        )
        return updated_run

    except AIException as exc:
        usage = _state_usage_snapshot(runtime_state)
        await _safe_mark_generation_run_failed(
            session=session,
            run_id=run_id,
            failure_code=exc.code,
            failure_message=exc.message,
            usage=usage,
        )
        metrics_state.record_ai_run(
            success=False,
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            estimated_cost_usd=usage["estimated_cost_usd"],
        )
        raise
    except AppException as exc:
        usage = _state_usage_snapshot(runtime_state)
        await _safe_mark_generation_run_failed(
            session=session,
            run_id=run_id,
            failure_code=exc.code,
            failure_message=exc.message,
            usage=usage,
        )
        metrics_state.record_ai_run(
            success=False,
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            estimated_cost_usd=usage["estimated_cost_usd"],
        )
        raise
    except Exception as exc:
        usage = _state_usage_snapshot(runtime_state)
        await _safe_mark_generation_run_failed(
            session=session,
            run_id=run_id,
            failure_code=AIErrorCode.ORCHESTRATION_FAILED.value,
            failure_message=str(exc),
            usage=usage,
        )
        metrics_state.record_ai_run(
            success=False,
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            estimated_cost_usd=usage["estimated_cost_usd"],
        )
        raise AIException(
            code=AIErrorCode.ORCHESTRATION_FAILED,
            message="Generation pipeline failed unexpectedly",
            details={"error": str(exc)},
        ) from exc


async def list_generation_runs_for_job(
    *, session: AsyncSession, user_id: UUID, job_id: UUID
) -> list[JobGenerationRun]:
    runs = await session.scalars(
        select(JobGenerationRun)
        .where(JobGenerationRun.user_id == user_id, JobGenerationRun.job_id == job_id)
        .order_by(JobGenerationRun.created_at.desc())
    )
    return list(runs)


async def approve_output_versions(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    notes: str | None = None,
) -> JobOutput:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job.id))
    if output is None:
        raise AppException(status_code=404, code="job_output_not_found", message="Job output not found")

    versions = list(output.artifact_versions_json or [])
    if not versions:
        raise AppException(
            status_code=422,
            code="no_artifact_versions",
            message="No generated artifact versions are available for approval",
        )

    revision_map: dict[str, int] = {}
    for item in versions:
        artifact_type = str(item.get("artifact_type", ""))
        version_number = int(item.get("version_number", 0))
        current = revision_map.get(artifact_type, 0)
        if version_number > current:
            revision_map[artifact_type] = version_number

    output.approval_snapshot_json = {
        "approved_by_user_id": str(user_id),
        "approved_revision_map": revision_map,
        "notes": notes,
        "approved_at": datetime.now(UTC).isoformat(),
    }
    job.plan_approved = True
    await session.commit()
    await session.refresh(output)
    await session.refresh(job)
    return output
