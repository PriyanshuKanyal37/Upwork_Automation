from __future__ import annotations

from typing import Any


def normalize_optional_section(value: str | None) -> str:
    if value is None:
        return "None"
    stripped = value.strip()
    return stripped if stripped else "None"


def build_context_block(
    *,
    job_markdown: str | None,
    notes_markdown: str | None,
    profile_context: str | None,
    custom_instruction: str | None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    extras: list[str] = []
    for key, value in (extra_context or {}).items():
        section_value = "None" if value is None else str(value).strip() or "None"
        extras.append(f"{key}:\n{section_value}")

    extras_block = "\n\n".join(extras) if extras else "None"
    return (
        "## Job Post\n"
        f"{normalize_optional_section(job_markdown)}\n\n"
        "## Extra context:\n"
        f"{extras_block}\n\n"
        "## Custom Instruction\n"
        f"{normalize_optional_section(custom_instruction)}\n\n"
        "## User Notes\n"
        f"{normalize_optional_section(notes_markdown)}\n\n"
        "## Profile Context\n"
        f"{normalize_optional_section(profile_context)}\n"
    )


def build_default_generation_prompt(
    *,
    job_markdown: str | None,
    notes_markdown: str | None,
    profile_context: str | None,
    custom_instruction: str | None,
) -> str:
    return "Use the provided context to produce the requested artifact.\n" + build_context_block(
        job_markdown=job_markdown,
        notes_markdown=notes_markdown,
        profile_context=profile_context,
        custom_instruction=custom_instruction,
    )
