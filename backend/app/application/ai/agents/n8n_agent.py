from __future__ import annotations

import json
import re
import unicodedata
import uuid
from typing import Any

from app.application.ai.contracts import (
    ArtifactPayload,
    ArtifactType,
    ProviderAgentRequest,
    ProviderAgentTurnResult,
    ToolChoice,
    ToolDefinition,
    ToolUse,
)
from app.application.ai.costing import estimate_call_cost_usd
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.skills.n8n.example_picker import get_workflow_example
from app.application.ai.skills.n8n.node_catalog import get_node_schema
from app.application.ai.skills.n8n.skill_loader import N8N_SYSTEM_PROMPT, get_skill_content
from app.application.ai.validators.workflow_validator import WorkflowArtifactValidator
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter
from app.infrastructure.logging.setup import get_logger

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

_WORKFLOW_VALIDATOR = WorkflowArtifactValidator()
_logger = get_logger(__name__)

_MAX_JOB_MARKDOWN_CHARS = 8_000
_MAX_NOTES_CHARS = 4_000
_MAX_PROFILE_CHARS = 2_000
_MAX_CUSTOM_INSTRUCTION_CHARS = 2_000
_MAX_EXTRA_CONTEXT_VALUE_CHARS = 800

_MAX_SCHEMA_PROPERTIES = 24
_MAX_PROPERTY_OPTIONS = 12

_MAX_TURN_INPUT_TOKENS = 14_000
_MAX_RUN_INPUT_TOKENS = 30_000
_MAX_OUTPUT_TOKENS = 4_000
_MAX_HISTORY_STUB_CHARS = 300
_MAX_HISTORY_STUB_TOTAL_PER_TURN = 1_500
_MAX_ROLLING_SUMMARY_CHARS = 1_000
_MAX_TOOL_RESULT_COMPACT_CHARS = 320
_ENABLE_TOKEN_PRECHECK = False


N8N_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_node_schema",
        description="Returns compact n8n node schema details (typeVersion, key properties, credentials).",
        input_schema={
            "type": "object",
            "properties": {"type_string": {"type": "string"}},
            "required": ["type_string"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="get_workflow_example",
        description="Returns one importable sample n8n workflow JSON by category.",
        input_schema={
            "type": "object",
            "properties": {"category": {"type": "string"}},
            "required": ["category"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="get_skill",
        description=(
            "Returns one skill section for n8n guidance. "
            "Allowed skill names: expression_syntax, workflow_patterns, node_configuration, validation_expert."
        ),
        input_schema={
            "type": "object",
            "properties": {"skill_name": {"type": "string"}},
            "required": ["skill_name"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="validate_workflow_json",
        description="Validates workflow JSON and returns VALID or compact error details.",
        input_schema={
            "type": "object",
            "properties": {"workflow_json": {}},
            "required": ["workflow_json"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="finalize_workflow",
        description=(
            "Finalize workflow generation. Must be called to complete. "
            "Input must include workflow_json and workflow_explanation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "workflow_json": {"type": "object"},
                "workflow_explanation": {"type": "string"},
            },
            "required": ["workflow_json", "workflow_explanation"],
            "additionalProperties": False,
        },
    ),
]


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_PATTERN.sub("", text).strip()


def _truncate_text(value: Any, *, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        return "None"
    if len(text) <= max_chars:
        return text
    remaining = len(text) - max_chars
    return f"{text[:max_chars].rstrip()} ...[truncated {remaining} chars]"


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_strip_code_fences(value))
    except json.JSONDecodeError as exc:
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Agent workflow JSON is invalid",
        ) from exc
    if not isinstance(parsed, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Agent workflow output must be a JSON object",
        )
    return parsed


def _format_context(job_context: dict[str, Any]) -> str:
    def _block(label: str, key: str, *, max_chars: int) -> str:
        value = _truncate_text(job_context.get(key), max_chars=max_chars)
        return f"## {label}\n{value}"

    extra_context = job_context.get("extra_context")
    extra_context_text = "None"
    if isinstance(extra_context, dict) and extra_context:
        lines: list[str] = []
        for key, value in extra_context.items():
            serialized = _truncate_text(value, max_chars=_MAX_EXTRA_CONTEXT_VALUE_CHARS)
            lines.append(f"{key}: {serialized if serialized else 'None'}")
        extra_context_text = "\n".join(lines)

    return "\n\n".join(
        [
            _block("Job Markdown", "job_markdown", max_chars=_MAX_JOB_MARKDOWN_CHARS),
            _block("User Notes", "notes_markdown", max_chars=_MAX_NOTES_CHARS),
            _block("Profile Context", "profile_context", max_chars=_MAX_PROFILE_CHARS),
            _block("Custom Instruction", "custom_instruction", max_chars=_MAX_CUSTOM_INSTRUCTION_CHARS),
            f"## Extracted Workflow Intent\n{extra_context_text}",
        ]
    )


def _build_user_prompt(job_context: dict[str, Any]) -> str:
    return (
        "Generate an n8n workflow for this client scenario.\n\n"
        f"{_format_context(job_context)}\n\n"
        "Rules:\n"
        "- Fetch details using tools only when needed.\n"
        "- Prioritize a clear, easy-to-explain workflow over complexity.\n"
        "- Let workflow size match job complexity; do not force a fixed node count.\n"
        "- Prefer a single clean main path, with branches only when necessary.\n"
        "- Keep JSON concise; avoid verbose jsCode blocks and long inline comments.\n"
        "- Use placeholder credentials and API URLs when unknown.\n"
        "- You must call finalize_workflow to finish.\n"
        "- finalize_workflow input must include workflow_json and workflow_explanation.\n"
        "- Avoid unicode punctuation in node names.\n"
    )


def _ascii_safe_name(name: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("->", " to ")
    ascii_text = re.sub(r"[^A-Za-z0-9 _()/-]", " ", ascii_text)
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()
    return ascii_text or fallback


def _collect_edges_from_connections(connections: dict[str, Any], node_names: set[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for source, payload in connections.items():
        if source not in node_names or not isinstance(payload, dict):
            continue
        main = payload.get("main")
        if not isinstance(main, list):
            continue
        for branch in main:
            if not isinstance(branch, list):
                continue
            for edge in branch:
                if not isinstance(edge, dict):
                    continue
                target = str(edge.get("node") or "").strip()
                if target in node_names:
                    edges.append((source, target))
    return edges


def _rebuild_connections_from_edges(edges: list[tuple[str, str]]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for source, target in edges:
        by_source.setdefault(source, []).append({"node": target, "type": "main", "index": 0})
    connections: dict[str, Any] = {}
    for source, targets in by_source.items():
        connections[source] = {"main": [targets]}
    return connections


def _sanitize_node_names_and_connections(workflow_json: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow_json.get("nodes")
    if not isinstance(nodes, list):
        return workflow_json

    old_to_new: dict[str, str] = {}
    used: set[str] = set()
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        old_name = str(node.get("name") or "").strip()
        base = _ascii_safe_name(old_name, fallback=f"Node {idx + 1}")
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base} {suffix}"
            suffix += 1
        used.add(candidate)
        node["name"] = candidate
        if old_name:
            old_to_new[old_name] = candidate

    connections = workflow_json.get("connections")
    if isinstance(connections, dict):
        new_connections: dict[str, Any] = {}
        for old_source, payload in connections.items():
            source = old_to_new.get(str(old_source), str(old_source))
            if not isinstance(payload, dict):
                continue
            main = payload.get("main")
            if not isinstance(main, list):
                continue
            rebuilt_main: list[list[dict[str, Any]]] = []
            for branch in main:
                if not isinstance(branch, list):
                    continue
                rebuilt_branch: list[dict[str, Any]] = []
                for edge in branch:
                    if not isinstance(edge, dict):
                        continue
                    target = old_to_new.get(str(edge.get("node") or ""), str(edge.get("node") or ""))
                    rebuilt_branch.append({"node": target, "type": "main", "index": 0})
                rebuilt_main.append(rebuilt_branch)
            new_connections[source] = {"main": rebuilt_main}
        workflow_json["connections"] = new_connections
    return workflow_json


def _repair_workflow_graph(workflow_json: dict[str, Any]) -> dict[str, Any]:
    workflow_json = _sanitize_node_names_and_connections(workflow_json)
    nodes = workflow_json.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return workflow_json

    node_names: list[str] = [str(node.get("name") or "") for node in nodes if isinstance(node, dict)]
    node_name_set = {name for name in node_names if name}
    if not node_names:
        return workflow_json

    trigger_names = [
        str(node.get("name") or "")
        for node in nodes
        if isinstance(node, dict)
        and ("trigger" in str(node.get("type") or "").lower() or "webhook" in str(node.get("type") or "").lower())
    ]
    if not trigger_names:
        trigger_names = [node_names[0]]
    primary_trigger = trigger_names[0]

    existing_connections = workflow_json.get("connections")
    edges = _collect_edges_from_connections(
        existing_connections if isinstance(existing_connections, dict) else {},
        node_name_set,
    )

    incoming: dict[str, int] = {name: 0 for name in node_name_set}
    outgoing: dict[str, int] = {name: 0 for name in node_name_set}
    for src, dst in edges:
        outgoing[src] += 1
        incoming[dst] += 1

    ordered = node_names
    if not edges:
        for i in range(len(ordered) - 1):
            edges.append((ordered[i], ordered[i + 1]))
    else:
        # connect unreachable nodes into main flow
        reachable = {primary_trigger}
        changed = True
        while changed:
            changed = False
            for src, dst in edges:
                if src in reachable and dst not in reachable:
                    reachable.add(dst)
                    changed = True
        last_anchor = ordered[0]
        for name in ordered[1:]:
            if name not in reachable:
                edges.append((last_anchor, name))
                reachable.add(name)
            last_anchor = name

    # Ensure every non-trigger has inbound.
    incoming = {name: 0 for name in node_name_set}
    outgoing = {name: 0 for name in node_name_set}
    for src, dst in edges:
        incoming[dst] += 1
        outgoing[src] += 1
    for idx, name in enumerate(ordered):
        if name == primary_trigger:
            continue
        if incoming.get(name, 0) == 0:
            parent = ordered[max(0, idx - 1)]
            if parent != name:
                edges.append((parent, name))
                incoming[name] += 1
                outgoing[parent] += 1

    workflow_json["connections"] = _rebuild_connections_from_edges(edges)

    # Re-layout nodes in simple lanes by BFS level.
    adjacency: dict[str, list[str]] = {name: [] for name in node_name_set}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)
    level: dict[str, int] = {primary_trigger: 0}
    queue: list[str] = [primary_trigger]
    while queue:
        src = queue.pop(0)
        src_level = level.get(src, 0)
        for dst in adjacency.get(src, []):
            if dst not in level or level[dst] > src_level + 1:
                level[dst] = src_level + 1
                queue.append(dst)
    missing = [name for name in ordered if name not in level]
    base_level = max(level.values()) + 1 if level else 0
    for idx, name in enumerate(missing):
        level[name] = base_level + idx

    level_counts: dict[int, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name") or "")
        x_level = level.get(name, 0)
        lane = level_counts.get(x_level, 0)
        level_counts[x_level] = lane + 1
        node["position"] = [x_level * 280, 180 + lane * 180]

    return workflow_json


def _sanitize_workflow(workflow_json: dict[str, Any]) -> dict[str, Any]:
    """
    Layer 2 auto-fix: deterministically corrects the most common structural
    mistakes the model makes before validation ever runs.

    Fixes applied (in order):
      1. IF node branching — splits targets that are all in main[0] into main[0]
         (true branch) and main[1] (false branch) when the IF node has exactly
         two distinct outgoing targets crammed into a single slot.
      2. Merge node input indexing — when two source nodes both connect to the
         same Merge node at index 0, reassigns the second one to index 1.
      3. Error Trigger downstream wiring — removes any connection whose target
         is an errorTrigger node (it is a root trigger, never a downstream target).
      4. Duplicate connection edges — removes duplicate (target, index) entries
         within each output slot.
    """
    nodes = workflow_json.get("nodes")
    connections = workflow_json.get("connections")
    if not isinstance(nodes, list) or not isinstance(connections, dict):
        return workflow_json

    # Build lookup: node name → node type (lower-cased)
    node_type_by_name: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name") or "").strip()
        ntype = str(node.get("type") or "").lower()
        if name:
            node_type_by_name[name] = ntype

    error_trigger_names: set[str] = {
        name for name, ntype in node_type_by_name.items() if "errortrigger" in ntype
    }
    if_node_names: set[str] = {
        name for name, ntype in node_type_by_name.items() if ntype.endswith(".if")
    }
    merge_node_names: set[str] = {
        name for name, ntype in node_type_by_name.items() if ntype.endswith(".merge")
    }

    # Fix 3: remove Error Trigger as a connection target across all sources.
    for source, payload in list(connections.items()):
        if not isinstance(payload, dict):
            continue
        main = payload.get("main")
        if not isinstance(main, list):
            continue
        changed = False
        new_main: list[list[dict[str, Any]]] = []
        for slot in main:
            if not isinstance(slot, list):
                new_main.append(slot)
                continue
            filtered = [
                edge for edge in slot
                if not (isinstance(edge, dict) and str(edge.get("node") or "") in error_trigger_names)
            ]
            if len(filtered) != len(slot):
                changed = True
            new_main.append(filtered)
        if changed:
            payload["main"] = new_main

    # Fix 1: IF node — if all targets are in main[0] (single slot), split into two slots.
    for if_name in if_node_names:
        payload = connections.get(if_name)
        if not isinstance(payload, dict):
            continue
        main = payload.get("main")
        if not isinstance(main, list) or len(main) != 1:
            # Already has multiple slots or no slots — leave alone.
            continue
        slot0 = main[0]
        if not isinstance(slot0, list) or len(slot0) < 2:
            # Only one target — nothing to split.
            continue
        # Deduplicate targets in slot0 first.
        seen: set[str] = set()
        unique_targets: list[dict[str, Any]] = []
        for edge in slot0:
            if not isinstance(edge, dict):
                continue
            key = str(edge.get("node") or "")
            if key not in seen:
                seen.add(key)
                unique_targets.append(edge)
        if len(unique_targets) >= 2:
            # First target → true branch (slot 0), second → false branch (slot 1).
            true_edge = {**unique_targets[0], "index": 0}
            false_edge = {**unique_targets[1], "index": 0}
            payload["main"] = [[true_edge], [false_edge]]
        elif len(unique_targets) == 1:
            payload["main"] = [[{**unique_targets[0], "index": 0}]]

    # Fix 2: Merge node — ensure the two sources connecting to a Merge node
    # use distinct input indices (0 and 1).
    for merge_name in merge_node_names:
        # Collect all (source, slot_index, edge_index) entries pointing to this merge.
        incoming: list[tuple[str, int, int]] = []
        for source, payload in connections.items():
            if not isinstance(payload, dict):
                continue
            main = payload.get("main")
            if not isinstance(main, list):
                continue
            for slot_idx, slot in enumerate(main):
                if not isinstance(slot, list):
                    continue
                for edge_idx, edge in enumerate(slot):
                    if isinstance(edge, dict) and str(edge.get("node") or "") == merge_name:
                        incoming.append((source, slot_idx, edge_idx))

        if len(incoming) < 2:
            continue  # Nothing to fix.

        # Assign distinct merge input indices to the first two incoming edges.
        for assign_index, (source, slot_idx, edge_idx) in enumerate(incoming[:2]):
            connections[source]["main"][slot_idx][edge_idx]["index"] = assign_index

    # Fix 4: Deduplicate edges within each slot (same target + index = duplicate).
    for source, payload in connections.items():
        if not isinstance(payload, dict):
            continue
        main = payload.get("main")
        if not isinstance(main, list):
            continue
        for slot_idx, slot in enumerate(main):
            if not isinstance(slot, list):
                continue
            seen_edges: set[tuple[str, int]] = set()
            deduped: list[dict[str, Any]] = []
            for edge in slot:
                if not isinstance(edge, dict):
                    continue
                key = (str(edge.get("node") or ""), int(edge.get("index") or 0))
                if key not in seen_edges:
                    seen_edges.add(key)
                    deduped.append(edge)
            main[slot_idx] = deduped

    # Fix 5: Strip empty connection slots and remove entries with no real connections.
    empty_sources: list[str] = []
    for source, payload in connections.items():
        if not isinstance(payload, dict):
            empty_sources.append(source)
            continue
        main = payload.get("main")
        if not isinstance(main, list):
            empty_sources.append(source)
            continue
        # Remove empty slots from the end (e.g., [[{"node":"X",...}], []] → [[{"node":"X",...}]])
        while main and isinstance(main[-1], list) and len(main[-1]) == 0:
            main.pop()
        if not main:
            empty_sources.append(source)
    for source in empty_sources:
        connections.pop(source, None)

    return workflow_json


def _prepare_workflow_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_payload = payload.get("workflow_json")
    # Unwrap if model mistakenly returned [{...}] instead of {...}
    if isinstance(workflow_payload, list) and len(workflow_payload) == 1 and isinstance(workflow_payload[0], dict):
        workflow_payload = workflow_payload[0]
    if isinstance(workflow_payload, dict):
        workflow = workflow_payload
    else:
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Provide workflow_json",
        )
    workflow = _ensure_workflow_defaults(workflow)
    workflow = _repair_workflow_graph(workflow)  # connects orphans, layouts positions (flattens branches to main[0])
    workflow = _sanitize_workflow(workflow)       # fixes IF/Merge/ErrorTrigger/duplicates AFTER repair
    return workflow


def _ensure_node_positions(workflow_json: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow_json.get("nodes")
    if not isinstance(nodes, list):
        return workflow_json
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        position = node.get("position")
        if (
            not isinstance(position, list)
            or len(position) != 2
            or not all(isinstance(x, (int, float)) for x in position)
        ):
            node["position"] = [260 + (idx * 220), 300]
    return workflow_json


def _ensure_workflow_defaults(workflow_json: dict[str, Any]) -> dict[str, Any]:
    # Top-level workflow id and versionId (required for n8n import).
    if not str(workflow_json.get("id") or "").strip():
        workflow_json["id"] = uuid.uuid4().hex[:8]
    if not str(workflow_json.get("versionId") or "").strip():
        workflow_json["versionId"] = uuid.uuid4().hex[:12]

    nodes = workflow_json.get("nodes")
    if isinstance(nodes, list):
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            if not str(node.get("id") or "").strip():
                node["id"] = f"node_{idx + 1}"
            if not str(node.get("name") or "").strip():
                node["name"] = f"Node {idx + 1}"
            if not isinstance(node.get("typeVersion"), (int, float)):
                node_type = str(node.get("type") or "").strip()
                schema = get_node_schema(node_type) if node_type else None
                resolved = schema.get("typeVersion") if isinstance(schema, dict) else None
                node["typeVersion"] = resolved if isinstance(resolved, (int, float)) else 1

    if not isinstance(workflow_json.get("connections"), dict):
        workflow_json["connections"] = {}

    settings = workflow_json.get("settings")
    if not isinstance(settings, dict):
        workflow_json["settings"] = {"executionOrder": "v1"}
    elif not isinstance(settings.get("executionOrder"), str) or not settings.get("executionOrder", "").strip():
        settings["executionOrder"] = "v1"

    return _ensure_node_positions(workflow_json)


def _validate_final_workflow(workflow_json: dict[str, Any]) -> list[dict[str, Any]]:
    artifact = ArtifactPayload(artifact_type=ArtifactType.WORKFLOW, content_json=workflow_json)
    result = _WORKFLOW_VALIDATOR.validate(artifact)
    if result.is_valid:
        return []
    return [issue.model_dump() for issue in result.issues]


def _compact_node_schema(schema: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "type": str(schema.get("type") or ""),
        "displayName": str(schema.get("displayName") or ""),
        "typeVersion": schema.get("typeVersion"),
        "description": _truncate_text(schema.get("description"), max_chars=300),
        "category": str(schema.get("category") or ""),
    }

    credentials: list[dict[str, Any]] = []
    raw_credentials = schema.get("credentials")
    if isinstance(raw_credentials, list):
        for item in raw_credentials[:10]:
            if isinstance(item, dict):
                credentials.append(
                    {
                        "name": str(item.get("name") or item.get("displayName") or ""),
                        "required": bool(item.get("required", False)),
                    }
                )
            else:
                credentials.append({"name": str(item), "required": False})
    compact["credentials"] = credentials

    required_properties: list[str] = []
    properties_preview: list[dict[str, Any]] = []
    raw_properties = schema.get("properties")
    if isinstance(raw_properties, list):
        for item in raw_properties:
            if not isinstance(item, dict):
                continue
            if item.get("required") is True:
                name = str(item.get("name") or item.get("displayName") or "").strip()
                if name:
                    required_properties.append(name)
        for item in raw_properties[:_MAX_SCHEMA_PROPERTIES]:
            if not isinstance(item, dict):
                continue
            preview = {
                "name": str(item.get("name") or item.get("displayName") or "").strip(),
                "type": str(item.get("type") or "").strip(),
                "required": bool(item.get("required", False)),
            }
            options = item.get("options")
            if isinstance(options, list):
                preview["options"] = [str(option) for option in options[:_MAX_PROPERTY_OPTIONS]]
            elif isinstance(options, dict):
                values = options.get("values")
                if isinstance(values, list):
                    option_names: list[str] = []
                    for value in values[:_MAX_PROPERTY_OPTIONS]:
                        if isinstance(value, dict):
                            option_names.append(str(value.get("name") or value.get("value") or ""))
                        else:
                            option_names.append(str(value))
                    preview["options"] = [name for name in option_names if name]
            properties_preview.append(preview)
    compact["required_properties"] = sorted(set(required_properties))
    compact["properties_preview"] = properties_preview
    compact["property_count"] = len(raw_properties) if isinstance(raw_properties, list) else 0
    return compact


def _summarize_issues(issues: list[dict[str, Any]], *, max_items: int = 3) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for issue in issues[:max_items]:
        summarized.append(
            {
                "code": str(issue.get("code") or "unknown"),
                "path": str(issue.get("path") or ""),
                "message": _truncate_text(issue.get("message"), max_chars=120),
            }
        )
    return summarized


def _auto_workflow_explanation(workflow_json: dict[str, Any]) -> str:
    nodes = workflow_json.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return "This workflow outlines the proposed automation flow with placeholder configuration details."
    names: list[str] = []
    for node in nodes:
        if isinstance(node, dict):
            node_name = str(node.get("name") or "").strip()
            if node_name:
                names.append(node_name)
    if not names:
        return "This workflow outlines the proposed automation flow with placeholder configuration details."
    preview = ", ".join(names[:6])
    if len(names) > 6:
        preview = f"{preview}, and {len(names) - 6} more nodes"
    return (
        "This workflow demonstrates the end-to-end client scenario using the following main steps: "
        f"{preview}. Configuration values are placeholders and can be finalized during implementation."
    )


def _build_tool_stub(tool: ToolUse, summary: str) -> str:
    base = f"{tool.name}: {summary}"
    return _truncate_text(base, max_chars=_MAX_HISTORY_STUB_CHARS)


def _append_assistant_message(
    messages: list[dict[str, Any]],
    *,
    text: str | None,
    tool_uses: list[ToolUse],
) -> None:
    content_blocks: list[dict[str, Any]] = []
    if text:
        content_blocks.append({"type": "text", "text": text})
    for tool in tool_uses:
        content_blocks.append(
            {
                "type": "tool_use",
                "id": tool.id,
                "name": tool.name,
                "input": tool.input,
            }
        )
    if content_blocks:
        messages.append({"role": "assistant", "content": content_blocks})


def _redact_latest_tool_use_inputs(messages: list[dict[str, Any]], tool_stubs: dict[str, str]) -> None:
    if len(messages) < 2:
        return
    assistant_message = messages[-2]
    content = assistant_message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        tool_id = str(block.get("id") or "")
        block["input"] = {"summary": tool_stubs.get(tool_id, "tool input consumed")}


def _compact_old_tool_results(messages: list[dict[str, Any]]) -> None:
    if len(messages) <= 3:
        return
    # Keep latest tool_result message verbatim; compact older ones.
    for idx, message in enumerate(messages[:-1]):
        role = message.get("role")
        if role != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        has_tool_result = any(
            isinstance(item, dict) and item.get("type") == "tool_result"
            for item in content
        )
        if not has_tool_result:
            continue
        compacted: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_result":
                continue
            compacted.append(
                {
                    "type": "tool_result",
                    "tool_use_id": item.get("tool_use_id"),
                    "content": _truncate_text("previous tool result compacted", max_chars=_MAX_TOOL_RESULT_COMPACT_CHARS),
                }
            )
        messages[idx] = {"role": "user", "content": compacted}


def _prune_message_history(messages: list[dict[str, Any]]) -> None:
    if len(messages) <= 7:
        return
    head = messages[0]
    tail = messages[-6:]
    messages[:] = [head] + tail


def _compress_tool_stubs(stubs: list[str]) -> str:
    if not stubs:
        return ""
    joined = " | ".join(stubs)
    return _truncate_text(joined, max_chars=_MAX_ROLLING_SUMMARY_CHARS)


def _tool_choice_for_iteration(iteration: int, max_iterations: int) -> ToolChoice:
    if iteration >= max_iterations - 1:
        return ToolChoice(type="tool", name="finalize_workflow")
    return ToolChoice(type="any")


def _coerce_turn_result(
    raw_result: ProviderAgentTurnResult | tuple[str | None, list[ToolUse], str],
    *,
    model_name: str,
) -> ProviderAgentTurnResult:
    if isinstance(raw_result, ProviderAgentTurnResult):
        return raw_result
    text, tool_uses, stop_reason = raw_result
    return ProviderAgentTurnResult(
        provider=AnthropicProviderAdapter.provider,
        model_name=model_name,
        output_text=text,
        tool_uses=tool_uses,
        stop_reason=stop_reason,
        input_tokens=0,
        output_tokens=0,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        latency_ms=0,
        raw_response={"compat_mode": True, "provider": AnthropicProviderAdapter.provider.value},
    )


def _ensure_tool_request(
    *,
    messages: list[dict[str, Any]],
    model_name: str,
    iteration: int,
    max_iterations: int,
) -> ProviderAgentRequest:
    return ProviderAgentRequest(
        messages=messages,
        system_prompt=N8N_SYSTEM_PROMPT,
        model_name=model_name,
        tools=N8N_TOOLS,
        tool_choice=_tool_choice_for_iteration(iteration, max_iterations),
        temperature=0.2,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
    )


def _execute_tool(
    *,
    tool: ToolUse,
    execution_state: dict[str, Any],
) -> tuple[str, str]:
    name = tool.name
    payload = tool.input

    if name == "get_node_schema":
        type_string = str(payload.get("type_string") or "").strip()
        if not type_string:
            return json.dumps({"error": "type_string is required"}), _build_tool_stub(tool, "missing type_string")
        schema = get_node_schema(type_string)
        if schema is None:
            return (
                json.dumps({"error": "node_not_found", "type_string": type_string}),
                _build_tool_stub(tool, f"schema not found for {type_string}"),
            )
        compact = _compact_node_schema(schema)
        summary = f"schema fetched for {type_string}, typeVersion={compact.get('typeVersion')}"
        return json.dumps(compact), _build_tool_stub(tool, summary)

    if name == "get_workflow_example":
        category = str(payload.get("category") or "").strip().lower()
        if not category:
            category = "webhook_http"
        sample = get_workflow_example(category)
        result = {
            "status": "OK",
            "category": category,
            "workflow_json": _truncate_text(sample, max_chars=5_500),
        }
        return json.dumps(result), _build_tool_stub(tool, f"example fetched for {category}")

    if name == "get_skill":
        skill_name = str(payload.get("skill_name") or "").strip().lower()
        result = get_skill_content(skill_name)
        stub = (
            f"skill loaded {skill_name}"
            if result.get("status") == "OK"
            else f"skill not found {skill_name}"
        )
        return json.dumps(result), _build_tool_stub(tool, stub)

    if name == "validate_workflow_json":
        incoming = payload.get("workflow_json")
        workflow_json: dict[str, Any]
        if isinstance(incoming, dict):
            workflow_json = _repair_workflow_graph(_ensure_workflow_defaults(incoming))
        else:
            try:
                workflow_json = _repair_workflow_graph(_ensure_workflow_defaults(_parse_json_object(str(incoming or ""))))
            except AIException as exc:
                result = {"status": "INVALID", "error": "invalid_json", "message": exc.message}
                return json.dumps(result), _build_tool_stub(tool, "validation invalid_json")
        issues = _validate_final_workflow(workflow_json)
        if not issues:
            return "VALID", _build_tool_stub(tool, "validation passed")
        compact_issues = _summarize_issues(issues)
        result = {"status": "INVALID", "issues": compact_issues}
        issue_codes = ", ".join(issue["code"] for issue in compact_issues)
        return json.dumps(result), _build_tool_stub(tool, f"validation failed: {issue_codes}")

    if name == "finalize_workflow":
        if payload.get("_truncated"):
            result = {
                "status": "REJECTED",
                "issue_codes": ["output_truncated"],
                "message": (
                    "Your previous response was cut off before the workflow JSON was complete. "
                    "Generate a SMALLER workflow (3-5 nodes, required parameters only) and call finalize_workflow again."
                ),
            }
            return json.dumps(result), _build_tool_stub(tool, "finalize rejected: output truncated")
        workflow_explanation_raw = _truncate_text(payload.get("workflow_explanation"), max_chars=24_000)
        try:
            workflow_json = _prepare_workflow_from_payload(payload)
        except AIException as exc:
            result = {
                "status": "REJECTED",
                "issue_codes": ["invalid_payload"],
                "message": exc.message,
            }
            return json.dumps(result), _build_tool_stub(tool, "finalize rejected: invalid payload")
        issues = _validate_final_workflow(workflow_json)
        if issues:
            compact_issues = _summarize_issues(issues)
            result = {
                "status": "REJECTED",
                "issue_codes": [issue["code"] for issue in compact_issues],
                "issues": compact_issues,
            }
            issue_codes = ", ".join(issue["code"] for issue in compact_issues)
            return json.dumps(result), _build_tool_stub(tool, f"finalize rejected: {issue_codes}")

        workflow_explanation = (
            _auto_workflow_explanation(workflow_json)
            if workflow_explanation_raw == "None"
            else workflow_explanation_raw
        )
        execution_state["finalized_workflow"] = workflow_json
        execution_state["finalized_explanation"] = workflow_explanation
        node_count = len(workflow_json.get("nodes", [])) if isinstance(workflow_json.get("nodes"), list) else 0
        execution_state["finalized_node_count"] = node_count
        result = {
            "status": "ACCEPTED",
            "node_count": node_count,
            "message": "workflow accepted",
        }
        return json.dumps(result), _build_tool_stub(tool, f"finalize accepted ({node_count} nodes)")

    return json.dumps({"error": "unsupported_tool", "tool": name}), _build_tool_stub(tool, "unsupported tool")


def _append_tool_results(
    *,
    messages: list[dict[str, Any]],
    tool_uses: list[ToolUse],
    execution_state: dict[str, Any],
) -> None:
    if not tool_uses:
        return
    results: list[dict[str, Any]] = []
    tool_stubs: dict[str, str] = {}
    turn_stubs: list[str] = []
    running_chars = 0

    for tool in tool_uses:
        result_text, stub = _execute_tool(tool=tool, execution_state=execution_state)
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool.id,
                "content": result_text,
            }
        )
        tool_stubs[tool.id] = stub
        if running_chars < _MAX_HISTORY_STUB_TOTAL_PER_TURN:
            trimmed = _truncate_text(stub, max_chars=_MAX_HISTORY_STUB_CHARS)
            turn_stubs.append(trimmed)
            running_chars += len(trimmed)

    messages.append({"role": "user", "content": results})
    _redact_latest_tool_use_inputs(messages, tool_stubs)
    _compact_old_tool_results(messages)
    _prune_message_history(messages)

    previous_summary = str(execution_state.get("rolling_summary") or "").strip()
    merged = turn_stubs if not previous_summary else [previous_summary, *turn_stubs]
    execution_state["rolling_summary"] = _compress_tool_stubs(merged)


async def _token_precheck_or_raise(
    *,
    provider: AnthropicProviderAdapter,
    request: ProviderAgentRequest,
    usage_totals: dict[str, Any],
    trace_entry: dict[str, Any],
) -> None:
    if int(usage_totals.get("input_tokens", 0)) > _MAX_RUN_INPUT_TOKENS:
        raise AIException(
            code=AIErrorCode.BUDGET_EXCEEDED,
            message="n8n agent aborted due to run input-token budget",
            details={"max_run_input_tokens": _MAX_RUN_INPUT_TOKENS},
        )

    if not _ENABLE_TOKEN_PRECHECK:
        trace_entry["precheck_status"] = "skipped"
        return

    try:
        estimated_tokens = await provider.count_tokens_for_tools(request)
    except AIException as exc:
        trace_entry["precheck_status"] = "failed"
        trace_entry["precheck_error"] = exc.message
        return

    trace_entry["precheck_status"] = "ok"
    trace_entry["precheck_input_tokens"] = estimated_tokens
    if estimated_tokens > _MAX_TURN_INPUT_TOKENS:
        raise AIException(
            code=AIErrorCode.BUDGET_EXCEEDED,
            message="n8n agent turn exceeds input-token budget",
            details={
                "max_turn_input_tokens": _MAX_TURN_INPUT_TOKENS,
                "estimated_input_tokens": estimated_tokens,
            },
        )


async def run_n8n_agent(
    *,
    job_context: dict[str, Any],
    provider: AnthropicProviderAdapter,
    model_name: str = "claude-sonnet-4-6",
    max_iterations: int = 3,
) -> ArtifactPayload:
    messages: list[dict[str, Any]] = [{"role": "user", "content": _build_user_prompt(job_context)}]
    trace: list[dict[str, Any]] = []
    usage_totals: dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "latency_ms": 0,
        "estimated_cost_usd": 0.0,
    }
    execution_state: dict[str, Any] = {}

    for iteration in range(max_iterations):
        turn_trace: dict[str, Any] = {"iteration": iteration + 1}
        request = _ensure_tool_request(
            messages=messages,
            model_name=model_name,
            iteration=iteration,
            max_iterations=max_iterations,
        )
        await _token_precheck_or_raise(
            provider=provider,
            request=request,
            usage_totals=usage_totals,
            trace_entry=turn_trace,
        )
        raw_turn_result = await provider.generate_with_tools(request)
        turn_result = _coerce_turn_result(raw_turn_result, model_name=model_name)

        turn_cost_usd = estimate_call_cost_usd(
            provider=turn_result.provider,
            input_tokens=turn_result.input_tokens,
            output_tokens=turn_result.output_tokens,
        )
        usage_totals["input_tokens"] = int(usage_totals.get("input_tokens", 0)) + turn_result.input_tokens
        usage_totals["output_tokens"] = int(usage_totals.get("output_tokens", 0)) + turn_result.output_tokens
        usage_totals["cache_read_input_tokens"] = int(usage_totals.get("cache_read_input_tokens", 0)) + int(
            turn_result.cache_read_input_tokens
        )
        usage_totals["cache_creation_input_tokens"] = int(
            usage_totals.get("cache_creation_input_tokens", 0)
        ) + int(turn_result.cache_creation_input_tokens)
        usage_totals["latency_ms"] = int(usage_totals.get("latency_ms", 0)) + turn_result.latency_ms
        usage_totals["estimated_cost_usd"] = float(usage_totals.get("estimated_cost_usd", 0.0)) + float(
            turn_cost_usd
        )

        tool_names = [tool.name for tool in turn_result.tool_uses]
        turn_trace.update(
            {
                "model_used": turn_result.model_name,
                "stop_reason": turn_result.stop_reason,
                "tool_names": tool_names,
                "input_tokens": turn_result.input_tokens,
                "output_tokens": turn_result.output_tokens,
                "cache_read_input_tokens": turn_result.cache_read_input_tokens,
                "cache_creation_input_tokens": turn_result.cache_creation_input_tokens,
                "latency_ms": turn_result.latency_ms,
                "estimated_cost_usd": float(turn_cost_usd),
            }
        )
        trace.append(turn_trace)
        _logger.info(
            "n8n.agent.turn",
            extra={
                "iteration": iteration + 1,
                "stop_reason": turn_result.stop_reason,
                "tool_names": tool_names,
                "input_tokens": turn_result.input_tokens,
                "output_tokens": turn_result.output_tokens,
                "cache_read_input_tokens": turn_result.cache_read_input_tokens,
                "cache_creation_input_tokens": turn_result.cache_creation_input_tokens,
                "latency_ms": turn_result.latency_ms,
                "estimated_cost_usd": float(turn_cost_usd),
            },
        )

        _append_assistant_message(messages, text=turn_result.output_text, tool_uses=turn_result.tool_uses)
        if turn_result.tool_uses:
            # If output was truncated mid-tool-call, skip tool_results entirely — the tool
            # inputs are partial/invalid. Add ONE recovery user message instead of two.
            if turn_result.stop_reason == "max_tokens" and iteration < max_iterations - 1:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your response was cut off (output token limit reached). "
                            "Generate a COMPACT workflow: 3-5 nodes, required parameters only, "
                            "workflow_explanation under 50 words. Call finalize_workflow now."
                        ),
                    }
                )
                _prune_message_history(messages)
                continue
            _append_tool_results(messages=messages, tool_uses=turn_result.tool_uses, execution_state=execution_state)
            if isinstance(execution_state.get("finalized_workflow"), dict):
                return ArtifactPayload(
                    artifact_type=ArtifactType.WORKFLOW,
                    content_text=str(execution_state.get("finalized_explanation") or ""),
                    content_json=execution_state["finalized_workflow"],
                    metadata={
                        "agent_mode": "tool_loop",
                        "iterations": iteration + 1,
                        "usage": usage_totals,
                        "agent_trace": trace,
                    },
                )
            continue

        # If model ended turn without tool call, ask it to finalize in next turn.
        if iteration < max_iterations - 1:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You must call finalize_workflow to complete this task. "
                        "Provide workflow_json and workflow_explanation in the tool input."
                    ),
                }
            )
            _prune_message_history(messages)
            continue

    failure_reason = "n8n agent could not finalize a valid workflow in allotted turns"
    details = {
        "reason": failure_reason,
        "agent_trace": trace,
        "rolling_summary": execution_state.get("rolling_summary"),
    }
    raise AIException(
        code=AIErrorCode.INVALID_OUTPUT,
        message=failure_reason,
        details=details,
    )
