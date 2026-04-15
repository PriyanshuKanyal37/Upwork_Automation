from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.application.ai.contracts import RouteTask
from app.application.ai.prompt_registry import get_prompt_template


@dataclass(frozen=True)
class BuiltPrompt:
    task: RouteTask
    prompt_version: str
    prompt_hash: str
    system_prompt: str
    user_prompt: str


_TEMPLATE_FIELD_BY_TASK: dict[RouteTask, str] = {
    RouteTask.PROPOSAL: "proposal_template",
    RouteTask.DOC: "doc_template",
    RouteTask.LOOM_SCRIPT: "loom_template",
    RouteTask.WORKFLOW: "workflow_template_notes",
}


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_personalization_appendix(*, task: RouteTask, context: dict[str, Any]) -> str:
    sections: list[str] = []

    template_field = _TEMPLATE_FIELD_BY_TASK.get(task)
    template_text = _normalize_optional_text(context.get(template_field)) if template_field else None
    if template_text:
        template_header = "User Output Template Preference (from user profile, highest priority for this artifact):"
        if task == RouteTask.LOOM_SCRIPT:
            template_header = (
                "User Output Template Preference (from DB loom_template, highest priority for Loom structure/style):"
            )
        sections.append(
            f"{template_header}\n"
            f"{template_text}\n\n"
            "Use this as style/structure guidance. Do not copy it blindly.\n"
            "Adapt it to the current job post, user notes, and proof context.\n"
            "Never import facts from the template unless those facts also exist in current context."
        )

    custom_global_instruction = _normalize_optional_text(context.get("custom_global_instruction"))
    if custom_global_instruction:
        global_header = "User Global Instruction (secondary to artifact template when both are present):"
        if task != RouteTask.LOOM_SCRIPT:
            global_header = "User Global Instruction (high priority):"
        sections.append(
            f"{global_header}\n"
            f"{custom_global_instruction}"
        )

    enabled_prompt_blocks: list[str] = []
    raw_blocks = context.get("custom_prompt_blocks")
    if isinstance(raw_blocks, list):
        for item in raw_blocks:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("enabled")):
                continue
            title = _normalize_optional_text(item.get("title"))
            content = _normalize_optional_text(item.get("content"))
            if not title or not content:
                continue
            enabled_prompt_blocks.append(f"{title}:\n{content}")
    if enabled_prompt_blocks:
        sections.append(
            "Enabled User Prompt Blocks (high priority):\n"
            + "\n\n".join(enabled_prompt_blocks)
        )

    if not sections:
        return ""

    return (
        "Priority Instructions (apply in this order; user-specific rules override defaults on conflict):\n"
        + "\n\n".join(sections)
    )


def build_prompt(*, task: RouteTask, context: dict[str, Any]) -> BuiltPrompt:
    template = get_prompt_template(task)
    base_user_prompt = template.build_user_prompt(context)
    personalization = _build_personalization_appendix(task=task, context=context)
    if personalization:
        user_prompt = (
            personalization
            + "\n\n"
            + "Base Generation Guidance (secondary; follow this while respecting priority instructions):\n"
            + base_user_prompt
        )
    else:
        user_prompt = base_user_prompt
    payload_for_hash = {
        "task": task.value,
        "prompt_version": template.version,
        "system_prompt": template.system_prompt,
        "user_prompt": user_prompt,
    }
    serialized = json.dumps(payload_for_hash, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    prompt_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return BuiltPrompt(
        task=task,
        prompt_version=template.version,
        prompt_hash=prompt_hash,
        system_prompt=template.system_prompt,
        user_prompt=user_prompt,
    )
