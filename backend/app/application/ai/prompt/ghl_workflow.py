"""Prompt assembler for the GoHighLevel build-spec generator."""
from __future__ import annotations

from typing import Any

from app.application.ai.prompt.common import build_context_block
from app.application.ai.skills.gohighlevel.skill_loader import GHL_SYSTEM_PROMPT

PROMPT_VERSION = "ghl_workflow_v1"
SYSTEM_PROMPT = GHL_SYSTEM_PROMPT


def build_user_prompt(context: dict[str, Any]) -> str:
    context_block = build_context_block(
        job_markdown=context.get("job_markdown"),
        notes_markdown=context.get("notes_markdown"),
        profile_context=context.get("profile_context"),
        custom_instruction=context.get("custom_instruction"),
        extra_context=context.get("extra_context"),
    )
    return (
        "Design one GoHighLevel workflow as a BUILD SPEC (not an import file).\n\n"
        "## Job Requirements\n"
        f"{context_block}\n\n"
        "## Your task\n"
        "Return a JSON object matching the build spec schema described in the "
        "system prompt. It has these top-level fields:\n"
        "- workflow_name\n"
        "- workflow_description\n"
        "- trigger (with type, category, configuration_notes, filter_conditions)\n"
        "- steps (flat array of step objects with step_number, step_type, etc.)\n"
        "- estimated_build_time_minutes\n"
        "- required_integrations\n"
        "- required_custom_fields\n\n"
        "Critical:\n"
        "- Use ONLY trigger and action names from the catalogs in the system prompt.\n"
        "- Branching is expressed via if_true_next_step / if_false_next_step on "
        "if_else steps — do not nest.\n"
        "- Step numbers are unique positive integers starting at 1 and increasing.\n"
        "- Keep configuration values realistic but concise."
    )
