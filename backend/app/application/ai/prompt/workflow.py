from __future__ import annotations

from typing import Any

from app.application.ai.prompt.common import build_context_block
from app.application.ai.skills.n8n.example_picker import pick_example
from app.application.ai.skills.n8n.skill_loader import N8N_SYSTEM_PROMPT

PROMPT_VERSION = "workflow_v3"
SYSTEM_PROMPT = N8N_SYSTEM_PROMPT


def build_user_prompt(context: dict[str, Any]) -> str:
    context_block = build_context_block(
        job_markdown=context.get("job_markdown"),
        notes_markdown=context.get("notes_markdown"),
        profile_context=context.get("profile_context"),
        custom_instruction=context.get("custom_instruction"),
        extra_context=context.get("extra_context"),
    )
    example = pick_example(context)
    return (
        "Design and generate one n8n workflow for this job.\n\n"
        "## Job Requirements\n"
        f"{context_block}\n\n"
        "## Example Workflow (real importable JSON for reference)\n"
        "<example_workflow>\n"
        f"{example}\n"
        "</example_workflow>\n\n"
        "## Output Format\n"
        "First write:\n"
        "## WRITTEN PLAN\n"
        "[2-3 sentences: what nodes are used, how data flows, and what the workflow does]\n\n"
        "Then write:\n"
        "## WORKFLOW JSON\n"
        "[valid n8n workflow JSON only, no markdown code fences]\n\n"
        "Critical requirements:\n"
        "- Include at least one trigger node.\n"
        "- Every node must include id, name, type, typeVersion, and position [x, y].\n"
        "- connections keys must match node names exactly.\n"
        "- Include settings.executionOrder.\n"
        "- Use placeholder credentials only.\n"
    )
