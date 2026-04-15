from uuid import uuid4

from app.application.ai.contracts import (
    AutomationPlatform,
    ArtifactType,
    AutomationPlatformPreference,
    ConfidenceLevel,
    JobClassification,
    JobType,
    JobUnderstandingContract,
    ProviderName,
)
from app.application.ai.planner_service import build_generation_plan


def test_planner_builds_items_from_understanding_deliverables() -> None:
    understanding = JobUnderstandingContract(
        summary_short="Need workflow and proposal.",
        deliverables_required=[ArtifactType.PROPOSAL, ArtifactType.WORKFLOW],
        extraction_confidence=ConfidenceLevel.HIGH,
    )

    plan = build_generation_plan(job_id=uuid4(), user_id=uuid4(), understanding=understanding)

    assert len(plan.items) == 2
    assert plan.items[0].artifact_type == ArtifactType.PROPOSAL
    assert plan.items[0].primary_model == "gpt-5.4-mini"
    assert plan.items[1].artifact_type == ArtifactType.WORKFLOW
    assert plan.items[1].primary_provider == ProviderName.ANTHROPIC
    assert plan.items[1].primary_model == "claude-sonnet-4-6"
    assert plan.requires_platform_confirmation is False


def test_planner_requires_platform_confirmation_for_make_only_jobs() -> None:
    understanding = JobUnderstandingContract(
        summary_short="Make.com specific request.",
        deliverables_required=[ArtifactType.WORKFLOW],
        automation_platform_preference=AutomationPlatformPreference.MAKE,
        extraction_confidence=ConfidenceLevel.HIGH,
    )

    plan = build_generation_plan(job_id=uuid4(), user_id=uuid4(), understanding=understanding)

    assert plan.platform_preference == AutomationPlatformPreference.MAKE
    assert plan.requires_platform_confirmation is True


def test_planner_defaults_unknown_platform_to_n8n() -> None:
    understanding = JobUnderstandingContract(
        summary_short="General automation request.",
        deliverables_required=[ArtifactType.PROPOSAL],
        automation_platform_preference=AutomationPlatformPreference.UNKNOWN,
        extraction_confidence=ConfidenceLevel.HIGH,
    )

    plan = build_generation_plan(job_id=uuid4(), user_id=uuid4(), understanding=understanding)
    assert plan.platform_preference == AutomationPlatformPreference.N8N


def test_planner_routes_make_classification_to_make_workflow_task() -> None:
    from app.application.ai.contracts import RouteTask

    understanding = JobUnderstandingContract(
        summary_short="Automation request.",
        deliverables_required=[ArtifactType.PROPOSAL, ArtifactType.WORKFLOW],
        extraction_confidence=ConfidenceLevel.HIGH,
    )
    classification = JobClassification(
        job_type=JobType.AUTOMATION,
        automation_platform=AutomationPlatform.MAKE,
        confidence="high",
        reasoning="Make mentioned explicitly.",
    )

    plan = build_generation_plan(
        job_id=uuid4(),
        user_id=uuid4(),
        understanding=understanding,
        classification=classification,
    )

    artifact_types = [item.artifact_type for item in plan.items]
    assert ArtifactType.WORKFLOW in artifact_types
    workflow_item = next(item for item in plan.items if item.artifact_type == ArtifactType.WORKFLOW)
    assert workflow_item.task == RouteTask.MAKE_WORKFLOW


def test_planner_routes_ghl_classification_to_ghl_workflow_task() -> None:
    from app.application.ai.contracts import RouteTask

    understanding = JobUnderstandingContract(
        summary_short="GoHighLevel workflow needed.",
        deliverables_required=[ArtifactType.PROPOSAL, ArtifactType.WORKFLOW],
        extraction_confidence=ConfidenceLevel.HIGH,
    )
    classification = JobClassification(
        job_type=JobType.AUTOMATION,
        automation_platform=AutomationPlatform.GHL,
        confidence="high",
        reasoning="GoHighLevel explicitly requested.",
    )

    plan = build_generation_plan(
        job_id=uuid4(),
        user_id=uuid4(),
        understanding=understanding,
        classification=classification,
    )

    workflow_item = next(item for item in plan.items if item.artifact_type == ArtifactType.WORKFLOW)
    assert workflow_item.task == RouteTask.GHL_WORKFLOW


def test_planner_skips_workflow_for_unsupported_platform_with_reason() -> None:
    understanding = JobUnderstandingContract(
        summary_short="Zapier automation.",
        deliverables_required=[ArtifactType.PROPOSAL, ArtifactType.WORKFLOW],
        extraction_confidence=ConfidenceLevel.HIGH,
    )
    classification = JobClassification(
        job_type=JobType.AUTOMATION,
        automation_platform=AutomationPlatform.ZAPIER,
        confidence="high",
        reasoning="Zapier mentioned explicitly.",
    )

    plan = build_generation_plan(
        job_id=uuid4(),
        user_id=uuid4(),
        understanding=understanding,
        classification=classification,
    )

    assert [item.artifact_type for item in plan.items] == [ArtifactType.PROPOSAL]
    assert plan.blocked_reason is not None
    assert "zapier" in plan.blocked_reason.lower()


def test_planner_skips_workflow_for_non_automation_job() -> None:
    understanding = JobUnderstandingContract(
        summary_short="React dashboard build.",
        deliverables_required=[ArtifactType.PROPOSAL, ArtifactType.WORKFLOW],
        extraction_confidence=ConfidenceLevel.HIGH,
    )
    classification = JobClassification(
        job_type=JobType.WEB_DEV,
        automation_platform=None,
        confidence="high",
        reasoning="Frontend React request.",
    )

    plan = build_generation_plan(
        job_id=uuid4(),
        user_id=uuid4(),
        understanding=understanding,
        classification=classification,
    )

    assert [item.artifact_type for item in plan.items] == [ArtifactType.PROPOSAL]
    # Non-automation jobs drop workflow silently, no blocked_reason.
    assert plan.blocked_reason is None
