"""Generation planner.

Converts a JobUnderstandingContract (+ optional JobClassification) into a
concrete GenerationPlan — a list of GenerationPlanItems each bound to a
specific RouteTask and model.

Workflow artifact routing is platform-aware:
- n8n classification  → RouteTask.WORKFLOW         (n8n agent)
- Make classification → RouteTask.MAKE_WORKFLOW    (Make.com agent)
- GHL classification  → RouteTask.GHL_WORKFLOW     (GoHighLevel build-spec agent)
- Any other automation platform (Zapier, etc.)     → workflow skipped, plan.blocked_reason set
- Non-automation job types (ai_ml, web_dev, other) → workflow skipped silently

All other artifact types (proposal, cover_letter, loom_script, doc) are
platform-independent and always routed through their fixed tasks.
"""
from __future__ import annotations

from uuid import UUID

from app.application.ai.contracts import (
    AutomationPlatform,
    ArtifactType,
    AutomationPlatformPreference,
    GenerationPlan,
    GenerationPlanItem,
    JobClassification,
    JobType,
    JobUnderstandingContract,
    RouteTask,
    RoutingMode,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.routing import get_route_for_task


# Fixed mapping for all NON-workflow artifact types. Workflow is resolved
# separately by _resolve_workflow_task() because it depends on the target
# automation platform.
_TASK_BY_ARTIFACT: dict[ArtifactType, RouteTask] = {
    ArtifactType.PROPOSAL: RouteTask.PROPOSAL,
    # Cover letter is treated as proposal alias for now.
    ArtifactType.COVER_LETTER: RouteTask.PROPOSAL,
    ArtifactType.LOOM_SCRIPT: RouteTask.LOOM_SCRIPT,
    ArtifactType.DOC: RouteTask.DOC,
}


# Platform → RouteTask lookup for workflow generation. Only platforms with a
# built generator appear here. Everything else is treated as unsupported.
_WORKFLOW_TASK_BY_PLATFORM: dict[AutomationPlatform, RouteTask] = {
    AutomationPlatform.N8N: RouteTask.WORKFLOW,
    AutomationPlatform.MAKE: RouteTask.MAKE_WORKFLOW,
    AutomationPlatform.GHL: RouteTask.GHL_WORKFLOW,
}


# Platform preference → matching AutomationPlatform (used when classification
# is missing and we have to fall back to what the understanding extracted).
_PREFERENCE_TO_PLATFORM: dict[AutomationPlatformPreference, AutomationPlatform] = {
    AutomationPlatformPreference.N8N: AutomationPlatform.N8N,
    AutomationPlatformPreference.MAKE: AutomationPlatform.MAKE,
    AutomationPlatformPreference.GHL: AutomationPlatform.GHL,
}


_DEFAULT_ARTIFACTS: list[ArtifactType] = [
    ArtifactType.PROPOSAL,
    ArtifactType.LOOM_SCRIPT,
    ArtifactType.WORKFLOW,
    ArtifactType.DOC,
]


def resolve_workflow_task(
    *,
    classification: JobClassification | None,
    understanding: JobUnderstandingContract | None = None,
) -> RouteTask | None:
    """Return the correct workflow RouteTask for a job, or None if unsupported.

    Precedence:
    1. If classification says AUTOMATION + known platform → use that platform.
    2. If classification says AUTOMATION + explicitly unsupported platform
       (Zapier, OTHER, UNKNOWN) → None (unsupported).
    3. If classification is non-AUTOMATION → None (not an automation job).
    4. Else (no classification OR classification is AUTOMATION with unknown
       platform with no classifier hit) → fall back to understanding's
       platform preference:
       - matches a generator → return that task
       - MAKE/GHL preference → already handled above
       - anything else (UNKNOWN, BOTH, or missing) → default to
         RouteTask.WORKFLOW (n8n) to preserve historical behavior when
         the classifier hasn't run yet.

    Exported so the orchestrator's regenerate fallback path can reuse it.
    """
    # 1 & 2 & 3: classification is authoritative when present.
    if classification is not None:
        if classification.job_type != JobType.AUTOMATION:
            # Non-automation job: no workflow.
            return None
        platform = classification.automation_platform
        if platform is not None and platform in _WORKFLOW_TASK_BY_PLATFORM:
            return _WORKFLOW_TASK_BY_PLATFORM[platform]
        if platform in {
            AutomationPlatform.ZAPIER,
            AutomationPlatform.OTHER,
        }:
            # Explicitly unsupported platform.
            return None
        # AUTOMATION + (UNKNOWN or None) → fall through to understanding.

    # 4. Fall back to understanding-level preference, with n8n default.
    if understanding is not None:
        preference = understanding.automation_platform_preference
        platform = _PREFERENCE_TO_PLATFORM.get(preference)
        if platform is not None:
            return _WORKFLOW_TASK_BY_PLATFORM.get(platform)

    # Historical default: when we can't determine the platform, assume n8n.
    # This preserves the prior behavior where "no classification" produced
    # an n8n workflow artifact.
    return RouteTask.WORKFLOW


def _is_workflow_generation_possible(
    classification: JobClassification | None,
) -> bool:
    """Return True if the job is an automation job on a supported platform."""
    if classification is None:
        # No classification yet — allow workflow through and let
        # resolve_workflow_task handle platform resolution from understanding.
        return True
    if classification.job_type != JobType.AUTOMATION:
        return False
    platform = classification.automation_platform
    if platform is None:
        return True  # unknown, give it a chance via understanding
    # Any known platform is fine at this gate — resolve_workflow_task will
    # decide whether we have a generator for it. We return True here so the
    # workflow artifact stays in the plan and we can surface a clear
    # "unsupported platform" reason downstream if needed.
    return True


def build_generation_plan(
    *,
    job_id: UUID,
    user_id: UUID,
    understanding: JobUnderstandingContract,
    classification: JobClassification | None = None,
) -> GenerationPlan:
    if not understanding.is_generation_allowed:
        raise AIException(
            code=AIErrorCode.LOW_CONFIDENCE_UNDERSTANDING,
            message="Cannot plan generation for low-confidence job understanding",
            details={"missing_fields": understanding.missing_fields},
        )

    raw_artifacts = understanding.deliverables_required or _DEFAULT_ARTIFACTS
    artifacts: list[ArtifactType] = []
    for artifact in raw_artifacts:
        # Treat cover letter as proposal so both paths converge.
        normalized = ArtifactType.PROPOSAL if artifact == ArtifactType.COVER_LETTER else artifact
        if normalized not in artifacts:
            artifacts.append(normalized)

    # Workflow gating: only keep the WORKFLOW artifact when the job is an
    # automation job AND we can resolve it to a supported platform generator.
    blocked_reason: str | None = None
    if ArtifactType.WORKFLOW in artifacts:
        workflow_task = resolve_workflow_task(
            classification=classification,
            understanding=understanding,
        )
        if classification is not None and classification.job_type != JobType.AUTOMATION:
            # Non-automation job: silently drop the workflow artifact.
            artifacts = [a for a in artifacts if a != ArtifactType.WORKFLOW]
        elif workflow_task is None:
            # Automation job but no generator for the requested platform.
            platform_name = "this platform"
            if classification is not None and classification.automation_platform:
                platform_name = classification.automation_platform.value
            artifacts = [a for a in artifacts if a != ArtifactType.WORKFLOW]
            blocked_reason = (
                f"Workflow generation is not supported for {platform_name} yet. "
                "Other artifacts (proposal, Loom script, doc) will still be generated."
            )

    # Guarantee at least some artifacts to generate so the run isn't empty.
    if not artifacts:
        artifacts = [ArtifactType.PROPOSAL, ArtifactType.LOOM_SCRIPT, ArtifactType.DOC]

    platform_preference = understanding.automation_platform_preference
    requires_platform_confirmation = platform_preference in {
        AutomationPlatformPreference.MAKE,
        AutomationPlatformPreference.GHL,
    }
    if platform_preference == AutomationPlatformPreference.UNKNOWN:
        platform_preference = AutomationPlatformPreference.N8N

    plan_items: list[GenerationPlanItem] = []
    for artifact_type in artifacts:
        if artifact_type == ArtifactType.WORKFLOW:
            task = resolve_workflow_task(
                classification=classification,
                understanding=understanding,
            )
            if task is None:
                # Safety net — shouldn't reach here because we filtered above.
                continue
        else:
            task = _TASK_BY_ARTIFACT.get(artifact_type)
            if task is None:
                raise AIException(
                    code=AIErrorCode.INVALID_ROUTE_CONFIG,
                    message="No route task mapping found for artifact",
                    details={"artifact_type": artifact_type.value},
                )
        route = get_route_for_task(task)
        primary_model = route.primary_model
        # Pin workflow tasks to the current sonnet model regardless of what
        # the routing config has, for consistency with the existing planner
        # behavior on n8n.
        if task in {
            RouteTask.WORKFLOW,
            RouteTask.MAKE_WORKFLOW,
            RouteTask.GHL_WORKFLOW,
        }:
            primary_model = "claude-sonnet-4-6"
        plan_items.append(
            GenerationPlanItem(
                task=task,
                artifact_type=artifact_type,
                primary_provider=route.primary_provider,
                primary_model=primary_model,
                fallback_provider=route.fallback_provider,
                fallback_model=route.fallback_model,
            )
        )

    return GenerationPlan(
        job_id=job_id,
        user_id=user_id,
        routing_mode=RoutingMode.FIXED_PER_ARTIFACT,
        platform_preference=platform_preference,
        requires_platform_confirmation=requires_platform_confirmation,
        items=plan_items,
        blocked_reason=blocked_reason,
    )
