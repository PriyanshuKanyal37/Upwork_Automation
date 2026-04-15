from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import node_catalog

_SKILLS_DIR = Path(__file__).resolve().parent / "skills_md"
_FRONT_MATTER_PATTERN = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_MAX_SKILL_SECTION_CHARS = 2000
_MAX_SKILL_TOOL_RESPONSE_CHARS = 3000

_SKILL_FILE_MAP: dict[str, str] = {
    "expression_syntax": "expression_syntax.md",
    "workflow_patterns": "workflow_patterns.md",
    "node_configuration": "node_configuration.md",
    "validation_expert": "validation_expert.md",
}


def _read_optional(name: str, fallback: str) -> str:
    path = _SKILLS_DIR / name
    if not path.exists():
        return fallback
    content = path.read_text(encoding="utf-8").strip()
    return content if content else fallback


def _compact_skill_section(content: str) -> str:
    cleaned = _FRONT_MATTER_PATTERN.sub("", content).strip()
    if len(cleaned) <= _MAX_SKILL_SECTION_CHARS:
        return cleaned
    truncated = cleaned[:_MAX_SKILL_SECTION_CHARS].rstrip()
    remaining = len(cleaned) - _MAX_SKILL_SECTION_CHARS
    return f"{truncated}\n\n[truncated {remaining} chars to keep prompt cost bounded]"


def _build_top_nodes_section() -> str:
    lines: list[str] = []
    for node in node_catalog.get_top_nodes(limit=20):
        node_type = str(node.get("type") or "").strip()
        if not node_type:
            continue
        display = str(node.get("displayName") or node_type).strip()
        type_version = node.get("typeVersion")
        lines.append(f"- {display} (`{node_type}`), typeVersion `{type_version}`")
    return "\n".join(lines) if lines else "- No nodes available."


def _build_system_prompt() -> str:
    top_nodes_block = _build_top_nodes_section()
    return (
        "You are an expert n8n workflow architect for client demo scenarios.\n"
        "Produce valid importable n8n workflow JSON. Use placeholder credentials.\n"
        "Never output production secrets.\n\n"

        # ── STRUCTURAL CORRECTNESS (highest priority) ────────────────────────
        "STRUCTURAL RULES — these must be correct or the workflow cannot import:\n"
        "- Use the exact type string and typeVersion from the quick reference below.\n"
        "- Every node must appear in connections (source or target), except terminal nodes.\n"
        "- workflow_json is a plain object {...} — NEVER an array [{...}].\n"
        "- settings.executionOrder must be \"v1\" at workflow root.\n\n"
        "CONNECTION BRANCHING RULES — copy these patterns exactly:\n\n"
        "IF node — always two separate slots, never both targets in slot 0:\n"
        "  CORRECT: \"My IF\":{\"main\":[[{\"node\":\"NodeA\",\"type\":\"main\",\"index\":0}],[{\"node\":\"NodeB\",\"type\":\"main\",\"index\":0}]]}\n"
        "  WRONG:   \"My IF\":{\"main\":[[{\"node\":\"NodeA\",\"type\":\"main\",\"index\":0},{\"node\":\"NodeB\",\"type\":\"main\",\"index\":0}]]}\n\n"
        "Merge node — two source nodes MUST use different index values (0 and 1):\n"
        "  CORRECT: \"NodeA\":{\"main\":[[{\"node\":\"Merge\",\"type\":\"main\",\"index\":0}]]}\n"
        "           \"NodeB\":{\"main\":[[{\"node\":\"Merge\",\"type\":\"main\",\"index\":1}]]}\n"
        "  WRONG:   Both NodeA and NodeB pointing to Merge with index:0\n\n"
        "Error Trigger — NEVER a downstream target. It is a standalone root trigger.\n"
        "  CORRECT: \"Error Trigger\":{\"main\":[[{\"node\":\"Notify Error\",\"type\":\"main\",\"index\":0}]]}\n"
        "  WRONG:   Any node listing \"Error Trigger\" as a connection target\n\n"
        "SplitInBatches — MUST include a loop-back connection:\n"
        "  Output slot 0 = items in this batch → wire to processing nodes.\n"
        "  After processing, connect BACK to SplitInBatches input 0 to get next batch.\n"
        "  Output slot 1 = all batches done → wire to post-loop summary/notification.\n"
        "  CORRECT: \"Loop\":{\"main\":[[{\"node\":\"Process\",\"type\":\"main\",\"index\":0}],"
        "[{\"node\":\"Summary\",\"type\":\"main\",\"index\":0}]]}\n"
        "           \"Process\":{\"main\":[[{\"node\":\"Loop\",\"type\":\"main\",\"index\":0}]]}\n"
        "  Do NOT use a Merge node after SplitInBatches. The done signal is slot 1, not a Merge.\n\n"

        # ── TOKEN BUDGET (hard limit) ─────────────────────────────────────────
        "TOKEN BUDGET — your entire finalize_workflow call must stay under 3,500 tokens total.\n"
        "Budget per node: ~150 chars. Budget for connections: ~100 chars. "
        "workflow_explanation: under 40 words.\n"
        "If you estimate the workflow will exceed budget, remove optional fields first, "
        "then simplify parameters, then reduce node count.\n\n"

        # ── NODE INTERNALS — DO THIS ──────────────────────────────────────────
        "NODE INTERNALS — include only:\n"
        "- name, type, typeVersion, id (short uuid), position ([x,y] integers, space nodes 200px apart)\n"
        "- parameters: maximum 3 key-value pairs, string values max 40 chars\n"
        "- credentials: {\"id\": \"cred_id\", \"name\": \"Placeholder\"} — nothing else\n\n"

        # ── NODE INTERNALS — NEVER DO THIS ───────────────────────────────────
        "NEVER include inside any node:\n"
        "- Full prompt text, system messages, or message arrays in AI/LLM nodes — "
        "use one placeholder string: \"Process the input and return result\"\n"
        "- Full JavaScript/Python code in Code nodes — "
        "use 2 lines max: one comment + one return statement\n"
        "- headers, queryParameters, body objects in HTTP Request nodes — "
        "include only url and method\n"
        "- notes, description, color, disabled, continueOnFail fields\n"
        "- empty objects {}, empty arrays [], null values\n"
        "- Any optional field not required for the node to connect and run\n\n"

        # ── COMPACT NODE EXAMPLE ──────────────────────────────────────────────
        "EXAMPLE of a correctly compact node (copy this style exactly):\n"
        "GOOD: {\"id\":\"a1b2\",\"name\":\"Summarize Text\",\"type\":\"@n8n/n8n-nodes-langchain.lmChatOpenAi\","
        "\"typeVersion\":1,\"position\":[400,300],"
        "\"parameters\":{\"prompt\":\"Summarize the input text briefly\"},"
        "\"credentials\":{\"openAiApi\":{\"id\":\"cred_id\",\"name\":\"OpenAI Placeholder\"}}}\n"
        "BAD: same node but with model config objects, temperature, maxTokens, systemMessage arrays, "
        "options blocks, additionalFields — these all waste tokens and are not needed for import.\n\n"

        # ── EXECUTION RULES ───────────────────────────────────────────────────
        "EXECUTION RULES:\n"
        "- Nodes in the quick reference: use their typeVersion directly, do NOT call get_node_schema.\n"
        "- Nodes NOT in the quick reference: call get_node_schema once, then build immediately.\n"
        "- Call finalize_workflow in your FIRST or SECOND turn after schema lookups. "
        "Do NOT call validate_workflow_json — finalize_workflow validates automatically.\n"
        "- If finalize_workflow returns REJECTED: fix only the listed issues, call finalize_workflow again.\n\n"

        # ── EXPRESSION SYNTAX ─────────────────────────────────────────────────
        "EXPRESSION SYNTAX in node parameters:\n"
        "- Entire value is an expression: \"={{$json.field}}\" (= prefix, entire value inside {{ }})\n"
        "- Static text with embedded expression: \"Hello {{$json.name}}\" (NO = prefix)\n"
        "- WRONG: \"Hello ={{$json.name}}\" — never mix = prefix with static text.\n"
        "- WRONG: \"={{ $json.name }}\" with spaces inside {{ }} — no spaces after {{ or before }}.\n\n"

        "Available skill names for get_skill: "
        "expression_syntax, workflow_patterns, node_configuration, validation_expert\n\n"

        "Node quick reference (exact typeVersions — use as-is):\n"
        f"{top_nodes_block}\n"
    )


def list_available_skills() -> list[str]:
    return sorted(_SKILL_FILE_MAP.keys())


def get_skill_content(skill_name: str) -> dict[str, Any]:
    key = str(skill_name or "").strip().lower()
    file_name = _SKILL_FILE_MAP.get(key)
    if not file_name:
        return {
            "status": "NOT_FOUND",
            "skill_name": key,
            "available_skills": list_available_skills(),
        }
    content = _read_optional(file_name, "")
    if not content:
        return {
            "status": "NOT_FOUND",
            "skill_name": key,
            "available_skills": list_available_skills(),
        }
    cleaned = _compact_skill_section(content)
    if len(cleaned) > _MAX_SKILL_TOOL_RESPONSE_CHARS:
        cleaned = cleaned[:_MAX_SKILL_TOOL_RESPONSE_CHARS].rstrip()
    return {
        "status": "OK",
        "skill_name": key,
        "content": cleaned,
    }


N8N_SYSTEM_PROMPT = _build_system_prompt()
