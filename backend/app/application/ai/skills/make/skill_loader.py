"""System prompt and example loader for the Make.com generator.

Single-shot design: the entire system prompt (rules + module reference +
output format) is assembled once at import time and cached. No tool calls,
no multi-turn lookups. The model emits a flat module list that downstream
code converts to a nested Make.com blueprint.
"""
from __future__ import annotations

import json
from pathlib import Path

_SKILLS_MD_DIR = Path(__file__).resolve().parent / "skills_md"
_EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


def _read_md(name: str) -> str:
    path = _SKILLS_MD_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _read_example(name: str) -> str:
    path = _EXAMPLES_DIR / name
    if not path.exists():
        return ""
    # Compact the JSON so it uses fewer tokens in the prompt.
    raw = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, separators=(",", ":"))
    except json.JSONDecodeError:
        return raw.strip()


def _build_system_prompt() -> str:
    blueprint_structure = _read_md("blueprint_structure.md")
    common_modules = _read_md("common_modules.md")
    output_format = _read_md("output_format.md")

    return (
        "You are an expert Make.com (formerly Integromat) scenario architect.\n"
        "Your job: read a user's natural-language automation brief and emit a "
        "FLAT module list that our post-processor will convert into a valid, "
        "importable Make.com blueprint JSON.\n\n"
        "CRITICAL: You MUST emit the flat JSON format described in the "
        "OUTPUT FORMAT section below. Do NOT emit a nested blueprint. Do NOT "
        "wrap the output in markdown code fences. Use placeholder connection IDs "
        "(integer 1) for all credentials. Never output real secrets.\n\n"
        "=== BLUEPRINT STRUCTURE (reference only — you will NOT emit this shape) ===\n"
        f"{blueprint_structure}\n\n"
        "=== COMMON MODULES (use these exact module strings and versions) ===\n"
        f"{common_modules}\n\n"
        "=== OUTPUT FORMAT (THIS is what you emit) ===\n"
        f"{output_format}\n\n"
        "=== QUALITY BAR ===\n"
        "- Always include a trigger as the first module (id=1, parent_id=null).\n"
        "- Use realistic expressions in mapper values: reference the trigger "
        "module's output with {{1.<fieldName>}}.\n"
        "- If the brief implies branching (e.g. \"if X send email, else post to Slack\"), "
        "use a builtin:BasicRouter with one route per branch and a `filter` on each "
        "downstream module.\n"
        "- If the brief implies looping over a list, use builtin:BasicFeeder.\n"
        "- Keep mapper values concise but realistic; the user will tweak them on import.\n"
        "- Leave explanatory prose OUT of the JSON output. Write your plan in the "
        "`plan_text` field, not in the flat modules."
    )


def _build_example_pair() -> str:
    simple = _read_example("asana_to_slack.json")
    complex_example = _read_example("sheets_router_calendar_email.json")
    return (
        "Example 1 (simple linear — Asana new task -> Slack message):\n"
        f"<nested_blueprint_example>{simple}</nested_blueprint_example>\n\n"
        "Example 2 (router with two branches, each with a filter):\n"
        f"<nested_blueprint_example>{complex_example}</nested_blueprint_example>\n\n"
        "NOTE: These examples show the FINAL nested blueprint shape for your reference. "
        "Your output must be the FLAT module list format described above, NOT these "
        "nested shapes. The post-processor builds the nested shape from your flat list."
    )


MAKE_SYSTEM_PROMPT: str = _build_system_prompt()
MAKE_EXAMPLES_BLOCK: str = _build_example_pair()
