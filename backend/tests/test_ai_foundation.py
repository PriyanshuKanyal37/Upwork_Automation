from app.application.ai.contracts import (
    ArtifactType,
    ConfidenceLevel,
    JobUnderstandingContract,
    RouteTask,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.routing import get_route_for_task


def test_routing_defaults_match_blueprint_for_understanding_and_workflow() -> None:
    understanding_route = get_route_for_task(RouteTask.JOB_UNDERSTANDING)
    workflow_route = get_route_for_task(RouteTask.WORKFLOW)

    assert understanding_route.primary_model == "gpt-5.4-mini"
    assert understanding_route.fallback_model == "claude-sonnet-4-5"
    assert workflow_route.primary_model == "claude-sonnet-4-6"
    assert workflow_route.fallback_model is None


def test_diagram_route_is_configured_for_svg_generation() -> None:
    diagram_route = get_route_for_task(RouteTask.DIAGRAM)

    assert diagram_route.primary_model == "claude-sonnet-4-6"
    assert diagram_route.fallback_model == "gpt-5.4"


def test_ai_exception_maps_status_code_from_error_code() -> None:
    exc = AIException(code=AIErrorCode.PROVIDER_UNAVAILABLE, message="provider down")
    assert exc.status_code == 503
    assert exc.code == "provider_unavailable"
    assert exc.message == "provider down"


def test_job_understanding_dedupes_deliverables_and_applies_confidence_gate() -> None:
    contract = JobUnderstandingContract(
        summary_short="Need automation engineer.",
        deliverables_required=[
            ArtifactType.PROPOSAL,
            ArtifactType.PROPOSAL,
            ArtifactType.WORKFLOW,
        ],
        extraction_confidence=ConfidenceLevel.MEDIUM,
    )
    assert contract.deliverables_required == [ArtifactType.PROPOSAL, ArtifactType.WORKFLOW]
    assert contract.is_generation_allowed is True

    blocked_contract = JobUnderstandingContract(
        summary_short="Unclear markdown.",
        extraction_confidence=ConfidenceLevel.LOW,
    )
    assert blocked_contract.is_generation_allowed is False
