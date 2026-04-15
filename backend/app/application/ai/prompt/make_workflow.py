"""Prompt assembler for the Make.com one-shot generator.

Mirrors the shape of prompt/workflow.py but targets Make.com blueprints
instead of n8n workflows. No agent loop — this feeds a single structured-output
Claude call.
"""
from __future__ import annotations

from typing import Any

from app.application.ai.prompt.common import build_context_block
from app.application.ai.skills.make.skill_loader import (
    MAKE_EXAMPLES_BLOCK,
    MAKE_SYSTEM_PROMPT,
)

PROMPT_VERSION = "make_workflow_v1"
SYSTEM_PROMPT = MAKE_SYSTEM_PROMPT


def build_user_prompt(context: dict[str, Any]) -> str:
    context_block = build_context_block(
        job_markdown=context.get("job_markdown"),
        notes_markdown=context.get("notes_markdown"),
        profile_context=context.get("profile_context"),
        custom_instruction=context.get("custom_instruction"),
        extra_context=context.get("extra_context"),
    )
    return (
        "Design one Make.com scenario for this job and emit it in the FLAT "
        "module list format defined in the system prompt.\n\n"
        "## Job Requirements\n"
        f"{context_block}\n\n"
        "## Reference Examples\n"
        f"{MAKE_EXAMPLES_BLOCK}\n\n"
        "## Your task\n"
        "Return a JSON object with exactly two top-level fields:\n"
        "1. `plan_text` — 2-3 sentences summarizing what the scenario does, "
        "what modules it uses, and how data flows through it.\n"
        "2. `blueprint` — the FLAT module list object with keys: "
        "`name`, `zone`, `instant`, and `modules`.\n\n"
        "Critical:\n"
        "- The first module in `modules` must be a trigger.\n"
        "- Module IDs are unique positive integers starting at 1.\n"
        "- Routers have `is_router: true` and `route_count: N`; their children "
        "reference `parent_id` and `route_index`.\n"
        "- Use placeholder integer 1 for `__IMTCONN__` and `__IMTHOOK__`.\n"
        "- Never emit real credentials, API keys, or secrets."
    )
