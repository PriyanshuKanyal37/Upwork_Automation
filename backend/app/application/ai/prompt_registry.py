from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.application.ai.contracts import RouteTask
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.prompt import (
    doc,
    ghl_workflow,
    job_understanding,
    loom_script,
    make_workflow,
    proposal,
    workflow,
)


@dataclass(frozen=True)
class PromptTemplateSpec:
    task: RouteTask
    version: str
    system_prompt: str
    build_user_prompt: Callable[[dict[str, Any]], str]


_PROMPT_TEMPLATE_REGISTRY: dict[RouteTask, PromptTemplateSpec] = {
    RouteTask.JOB_UNDERSTANDING: PromptTemplateSpec(
        task=RouteTask.JOB_UNDERSTANDING,
        version=job_understanding.PROMPT_VERSION,
        system_prompt=job_understanding.SYSTEM_PROMPT,
        build_user_prompt=lambda context: job_understanding.build_user_prompt(
            job_markdown=str(context.get("job_markdown") or ""),
            notes_markdown=context.get("notes_markdown"),
            profile_context=context.get("profile_context"),
        ),
    ),
    RouteTask.PROPOSAL: PromptTemplateSpec(
        task=RouteTask.PROPOSAL,
        version=proposal.PROMPT_VERSION,
        system_prompt=proposal.SYSTEM_PROMPT,
        build_user_prompt=proposal.build_user_prompt,
    ),
    RouteTask.COVER_LETTER: PromptTemplateSpec(
        task=RouteTask.COVER_LETTER,
        # Cover letter currently aliases proposal prompt behavior.
        version=proposal.PROMPT_VERSION,
        system_prompt=proposal.SYSTEM_PROMPT,
        build_user_prompt=proposal.build_user_prompt,
    ),
    RouteTask.LOOM_SCRIPT: PromptTemplateSpec(
        task=RouteTask.LOOM_SCRIPT,
        version=loom_script.PROMPT_VERSION,
        system_prompt=loom_script.SYSTEM_PROMPT,
        build_user_prompt=loom_script.build_user_prompt,
    ),
    RouteTask.WORKFLOW: PromptTemplateSpec(
        task=RouteTask.WORKFLOW,
        version=workflow.PROMPT_VERSION,
        system_prompt=workflow.SYSTEM_PROMPT,
        build_user_prompt=workflow.build_user_prompt,
    ),
    RouteTask.MAKE_WORKFLOW: PromptTemplateSpec(
        task=RouteTask.MAKE_WORKFLOW,
        version=make_workflow.PROMPT_VERSION,
        system_prompt=make_workflow.SYSTEM_PROMPT,
        build_user_prompt=make_workflow.build_user_prompt,
    ),
    RouteTask.GHL_WORKFLOW: PromptTemplateSpec(
        task=RouteTask.GHL_WORKFLOW,
        version=ghl_workflow.PROMPT_VERSION,
        system_prompt=ghl_workflow.SYSTEM_PROMPT,
        build_user_prompt=ghl_workflow.build_user_prompt,
    ),
    RouteTask.DOC: PromptTemplateSpec(
        task=RouteTask.DOC,
        version=doc.PROMPT_VERSION,
        system_prompt=doc.SYSTEM_PROMPT,
        build_user_prompt=doc.build_user_prompt,
    ),
}


def get_prompt_template(task: RouteTask) -> PromptTemplateSpec:
    template = _PROMPT_TEMPLATE_REGISTRY.get(task)
    if not template:
        raise AIException(
            code=AIErrorCode.INVALID_ROUTE_CONFIG,
            message="No prompt template registered for task",
            details={"task": task.value},
        )
    return template
