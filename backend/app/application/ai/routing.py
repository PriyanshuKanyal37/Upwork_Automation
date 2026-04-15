from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.ai.contracts import ProviderName, RouteTask
from app.application.ai.errors import AIErrorCode, AIException


@dataclass(frozen=True)
class RouteRule:
    task: RouteTask
    primary_provider: ProviderName
    primary_model: str
    fallback_provider: ProviderName | None = None
    fallback_model: str | None = None
    max_cost_per_call_usd: Decimal | None = None
    active: bool = True


_DEFAULT_FIXED_ROUTES: dict[RouteTask, RouteRule] = {
    RouteTask.JOB_UNDERSTANDING: RouteRule(
        task=RouteTask.JOB_UNDERSTANDING,
        primary_provider=ProviderName.OPENAI,
        primary_model="gpt-5.4-mini",
        fallback_provider=ProviderName.ANTHROPIC,
        fallback_model="claude-sonnet-4-5",
    ),
    RouteTask.PROPOSAL: RouteRule(
        task=RouteTask.PROPOSAL,
        primary_provider=ProviderName.OPENAI,
        primary_model="gpt-5.4-mini",
        fallback_provider=ProviderName.OPENAI,
        fallback_model="gpt-5.4",
    ),
    RouteTask.COVER_LETTER: RouteRule(
        task=RouteTask.COVER_LETTER,
        primary_provider=ProviderName.OPENAI,
        primary_model="gpt-5.4-mini",
        fallback_provider=ProviderName.OPENAI,
        fallback_model="gpt-5.4",
    ),
    RouteTask.LOOM_SCRIPT: RouteRule(
        task=RouteTask.LOOM_SCRIPT,
        primary_provider=ProviderName.OPENAI,
        primary_model="gpt-5.4-mini",
        fallback_provider=ProviderName.OPENAI,
        fallback_model="gpt-5.4",
    ),
    RouteTask.WORKFLOW: RouteRule(
        task=RouteTask.WORKFLOW,
        primary_provider=ProviderName.ANTHROPIC,
        primary_model="claude-sonnet-4-6",
        fallback_provider=None,
        fallback_model=None,
    ),
    RouteTask.MAKE_WORKFLOW: RouteRule(
        task=RouteTask.MAKE_WORKFLOW,
        primary_provider=ProviderName.ANTHROPIC,
        primary_model="claude-sonnet-4-6",
        fallback_provider=None,
        fallback_model=None,
    ),
    RouteTask.GHL_WORKFLOW: RouteRule(
        task=RouteTask.GHL_WORKFLOW,
        primary_provider=ProviderName.ANTHROPIC,
        primary_model="claude-sonnet-4-6",
        fallback_provider=None,
        fallback_model=None,
    ),
    RouteTask.DOC: RouteRule(
        task=RouteTask.DOC,
        primary_provider=ProviderName.OPENAI,
        primary_model="gpt-5.4-mini",
        fallback_provider=ProviderName.OPENAI,
        fallback_model="gpt-5.4",
    ),
    RouteTask.DIAGRAM: RouteRule(
        task=RouteTask.DIAGRAM,
        primary_provider=ProviderName.ANTHROPIC,
        primary_model="claude-sonnet-4-6",
        fallback_provider=ProviderName.OPENAI,
        fallback_model="gpt-5.4",
    ),
}


def get_route_for_task(task: RouteTask) -> RouteRule:
    route = _DEFAULT_FIXED_ROUTES.get(task)
    if not route:
        raise AIException(
            code=AIErrorCode.INVALID_ROUTE_CONFIG,
            message="No route configured for requested AI task",
            details={"task": task.value},
        )
    return route


def list_active_routes() -> list[RouteRule]:
    return [route for route in _DEFAULT_FIXED_ROUTES.values() if route.active]
