from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from app.application.ai.contracts import ProviderGenerateRequest, ProviderName, RouteTask
from app.application.ai.routing import get_route_for_task
from app.infrastructure.config.settings import get_settings
from app.infrastructure.ai.providers.factory import build_provider_adapter

from .diagram_models import DiagramConnection, DiagramSpec, DiagramStep

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_HEADING_PATTERN = re.compile(r"^\s*#{1,6}\s+")
_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
_TAG_PATTERN = re.compile(r"`([^`]+)`")
_MULTI_SPACE_PATTERN = re.compile(r"\s+")
_FORBIDDEN_LAYOUTS = {"vertical", "top_down", "timeline_vertical"}
_LAYOUTS = ("roadmap_cards", "zigzag_path", "swimlane_process", "radial_hub_horizontal")


@dataclass(frozen=True)
class DiagramSpecBuildResult:
    spec: DiagramSpec
    source: str
    input_tokens: int
    output_tokens: int
    model_name: str | None = None
    provider_name: str | None = None


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or "Project Delivery Diagram"
    return "Project Delivery Diagram"


def _clean_line(value: str) -> str:
    value = _HEADING_PATTERN.sub("", value.strip())
    value = _BULLET_PATTERN.sub("", value)
    value = _TAG_PATTERN.sub(r"\1", value)
    value = value.replace("|", " ").replace("->", " ").replace("=>", " ")
    value = re.sub(r"\[[^\]]+\]\([^)]+\)", "", value)
    value = value.replace("**", "").replace("__", "").replace("*", "")
    value = _MULTI_SPACE_PATTERN.sub(" ", value).strip()
    return value


def _split_title_and_detail(value: str) -> tuple[str, str | None]:
    parts = re.split(r"\s+-\s+|:\s+", value, maxsplit=1)
    if len(parts) == 1:
        title = parts[0].strip()
        return title, None
    return parts[0].strip(), parts[1].strip() or None

def _derive_creativity_level(instruction: str | None) -> str:
    default_level = get_settings().diagram_default_creativity_level
    if default_level not in {"low", "medium", "high"}:
        default_level = "medium"
    if not instruction:
        return default_level
    lowered = instruction.lower()
    if any(marker in lowered for marker in ("creative", "visual", "stylish", "bold", "explore", "variation")):
        return "high"
    if any(marker in lowered for marker in ("strict", "minimal", "simple", "plain")):
        return "low"
    return default_level


def _normalize_connection_style(connection_style: str | None) -> str:
    lowered = (connection_style or "").strip().lower()
    if lowered in {"clean", "orthogonal", "curved"}:
        return lowered
    return "clean"


def _extract_step_candidates(*, markdown: str, preferred_section_text: str | None, max_steps: int = 8) -> list[str]:
    candidates: list[str] = []
    for block in (preferred_section_text or "", markdown):
        if len(candidates) >= max_steps:
            break
        for raw in block.splitlines():
            cleaned = _clean_line(raw)
            if not cleaned:
                continue
            # Skip tiny lines and markdown table separators.
            if len(cleaned) < 5 or set(cleaned) <= {"-", ":", "|"}:
                continue
            if cleaned.lower().startswith(("timeline", "price", "budget")):
                continue
            candidates.append(cleaned)
            if len(candidates) >= max_steps:
                break
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:max_steps]


def _fallback_steps(*, markdown: str, preferred_section_text: str | None, max_steps: int = 8) -> list[DiagramStep]:
    lines = _extract_step_candidates(markdown=markdown, preferred_section_text=preferred_section_text, max_steps=max_steps)
    if len(lines) < 3:
        lines = [
            "Understand the root problem and goals",
            "Design the implementation approach and sequence",
            "Build and validate the solution end to end",
            "Deliver, monitor, and hand over with documentation",
        ]
    steps: list[DiagramStep] = []
    for idx, line in enumerate(lines, start=1):
        title, detail = _split_title_and_detail(line)
        if len(title) > 72:
            title = title[:69].rstrip() + "..."
        if detail and len(detail) > 110:
            detail = detail[:107].rstrip() + "..."
        steps.append(
            DiagramStep(
                id=f"s{idx}",
                title=title,
                detail=detail,
                color_token=None,
                icon_key=None,
            )
        )
    return steps


def _normalize_spec(spec: DiagramSpec) -> DiagramSpec:
    if spec.layout_family in _FORBIDDEN_LAYOUTS:
        spec.layout_family = "roadmap_cards"
    spec.orientation = "horizontal"
    spec.connection_style = _normalize_connection_style(spec.connection_style)
    spec.steps = spec.steps[:9]

    # Normalize step text aggressively so SVG stays readable and balanced.
    for step in spec.steps:
        if len(step.title) > 72:
            step.title = step.title[:69].rstrip() + "..."
        if step.detail and len(step.detail) > 120:
            step.detail = step.detail[:117].rstrip() + "..."

    ids = {step.id for step in spec.steps}
    cleaned_connections: list[DiagramConnection] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for conn in spec.connections:
        if conn.source_id not in ids or conn.target_id not in ids or conn.source_id == conn.target_id:
            continue
        edge_key = (conn.source_id, conn.target_id, conn.edge_type)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        if conn.label and len(conn.label) > 24:
            conn.label = conn.label[:21].rstrip() + "..."
        cleaned_connections.append(conn)

    if not cleaned_connections and len(spec.steps) >= 2:
        cleaned_connections = [
            DiagramConnection(source_id=spec.steps[i].id, target_id=spec.steps[i + 1].id, edge_type="sequence")
            for i in range(len(spec.steps) - 1)
        ]

    # Build DAG-like ordering from non-feedback edges so visual direction is stable.
    index_of = {step.id: idx for idx, step in enumerate(spec.steps)}
    adjacency: dict[str, set[str]] = {step.id: set() for step in spec.steps}
    indegree: dict[str, int] = {step.id: 0 for step in spec.steps}
    for conn in cleaned_connections:
        if conn.edge_type == "feedback":
            continue
        if conn.target_id in adjacency[conn.source_id]:
            continue
        adjacency[conn.source_id].add(conn.target_id)
        indegree[conn.target_id] += 1

    queue = deque(sorted((node_id for node_id, deg in indegree.items() if deg == 0), key=lambda x: index_of[x]))
    ordered_ids: list[str] = []
    while queue:
        node_id = queue.popleft()
        ordered_ids.append(node_id)
        for nxt in sorted(adjacency[node_id], key=lambda x: index_of[x]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(ordered_ids) != len(spec.steps):
        # Cycle or malformed graph: preserve original order.
        ordered_ids = [step.id for step in spec.steps]

    step_by_id = {step.id: step for step in spec.steps}
    spec.steps = [step_by_id[node_id] for node_id in ordered_ids]
    rank = {step.id: idx for idx, step in enumerate(spec.steps)}

    # Rebuild display-safe edges:
    # 1) Always keep a clean sequential spine in step order.
    # 2) Keep at most one explicit feedback loop when present.
    sequence_spine: list[DiagramConnection] = [
        DiagramConnection(source_id=spec.steps[i].id, target_id=spec.steps[i + 1].id, edge_type="sequence")
        for i in range(len(spec.steps) - 1)
    ]
    feedback_candidates = [
        conn
        for conn in cleaned_connections
        if conn.edge_type == "feedback"
        and conn.source_id in rank
        and conn.target_id in rank
        and rank[conn.target_id] < rank[conn.source_id]
    ]
    feedback_edge: list[DiagramConnection] = []
    if feedback_candidates:
        # Prefer the longest loop-back, it reads best visually.
        best = max(feedback_candidates, key=lambda c: rank[c.source_id] - rank[c.target_id])
        feedback_edge = [DiagramConnection(source_id=best.source_id, target_id=best.target_id, edge_type="feedback")]

    spec.connections = (sequence_spine + feedback_edge)[: max(0, len(spec.steps))]
    return spec


def _build_fallback_spec(
    *,
    markdown: str,
    preferred_section_text: str | None,
    instruction: str | None,
    connection_style: str | None,
) -> DiagramSpec:
    title = _extract_title(markdown=markdown)
    steps = _fallback_steps(markdown=markdown, preferred_section_text=preferred_section_text)
    creativity = _derive_creativity_level(instruction)
    lowered_instruction = (instruction or "").lower()
    if any(word in lowered_instruction for word in ("swimlane", "lane")):
        layout = "swimlane_process"
    elif any(word in lowered_instruction for word in ("radial", "hub")):
        layout = "radial_hub_horizontal"
    elif any(word in lowered_instruction for word in ("zigzag", "serpentine", "path")):
        layout = "zigzag_path"
    else:
        layout = _LAYOUTS[(len(steps) - 3) % len(_LAYOUTS)]
    spec = DiagramSpec(
        title=title,
        orientation="horizontal",
        layout_family=layout,  # type: ignore[arg-type]
        creativity_level=creativity,  # type: ignore[arg-type]
        connection_style=_normalize_connection_style(connection_style),  # type: ignore[arg-type]
        steps=steps,
        connections=[
            DiagramConnection(source_id=steps[i].id, target_id=steps[i + 1].id, edge_type="sequence")
            for i in range(len(steps) - 1)
        ],
    )
    return _normalize_spec(spec)


def _parse_json_payload(raw_text: str) -> dict[str, Any]:
    stripped = _CODE_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("spec payload must be a JSON object")
    return parsed


def _build_spec_prompt(
    *,
    markdown: str,
    preferred_section_text: str | None,
    preferred_section_kind: str | None,
    instruction: str | None,
    connection_style: str | None,
) -> str:
    preferred_block = preferred_section_text.strip() if preferred_section_text else "None"
    instruction_block = instruction.strip() if instruction and instruction.strip() else "None"
    return (
        "Create a horizontal process diagram spec from the document context.\n"
        "Return JSON only, no markdown.\n\n"
        "Schema:\n"
        "{\n"
        '  "title": "short string",\n'
        '  "orientation": "horizontal",\n'
        '  "layout_family": "roadmap_cards|zigzag_path|swimlane_process|radial_hub_horizontal",\n'
        '  "creativity_level": "low|medium|high",\n'
        '  "connection_style": "clean|orthogonal|curved",\n'
        '  "steps": [\n'
        '    {"id":"s1","title":"...","detail":"optional","color_token":"optional","icon_key":"optional"}\n'
        "  ],\n"
        '  "connections": [{"source_id":"s1","target_id":"s2","label":"optional","edge_type":"sequence|branch|merge|feedback"}]\n'
        "}\n\n"
        "Rules:\n"
        "1) Orientation MUST be horizontal and left-to-right.\n"
        "2) Never output vertical timelines or top-down charts.\n"
        "3) Focus on problem-solving, approach, implementation sequence, validation, and handover.\n"
        "4) Use 4-8 steps. Keep each title <= 7 words and each detail <= 16 words.\n"
        "5) Use explicit node IDs (`s1..sN`) and connect them with meaningful edges only.\n"
        "6) Keep non-feedback edges forward-only (source before target). Use feedback only for real loops.\n"
        "7) Prefer sequence edges; use branch/merge only when document clearly implies a split or convergence.\n"
        "8) Avoid decorative-only connections; every edge must represent real flow intent.\n"
        "9) If user instruction conflicts with horizontal-only rule, keep horizontal.\n"
        "10) Prefer the provided focus section, then use full document context for missing steps.\n\n"
        f"Suggested creativity level: {_derive_creativity_level(instruction)}\n"
        f"Required connection style: {_normalize_connection_style(connection_style)}\n"
        f"Focus section kind: {preferred_section_kind or 'none'}\n"
        f"Focus section text:\n{preferred_block}\n\n"
        f"User instruction:\n{instruction_block}\n\n"
        f"Full document markdown:\n{markdown}\n"
    )


async def _generate_spec_with_provider(
    *,
    provider_name: ProviderName,
    model_name: str,
    prompt: str,
) -> DiagramSpecBuildResult:
    adapter = build_provider_adapter(provider_name)
    request = ProviderGenerateRequest(
        prompt=prompt,
        system_prompt=(
            "You are a diagram-spec generator. Return only valid JSON that fits the provided schema."
        ),
        model_name=model_name,
        temperature=0.2,
        max_output_tokens=1600,
        metadata={"task": "doc_flowchart_spec"},
    )
    result = await adapter.generate(request)
    payload = (
        result.output_json
        if isinstance(result.output_json, dict)
        else _parse_json_payload(result.output_text or "")
    )
    spec = DiagramSpec.model_validate(payload)
    normalized = _normalize_spec(spec)
    return DiagramSpecBuildResult(
        spec=normalized,
        source="llm",
        provider_name=result.provider.value,
        model_name=result.model_name,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


def build_deterministic_diagram_spec(
    *,
    markdown: str,
    preferred_section_text: str | None,
    instruction: str | None,
    connection_style: str | None,
) -> DiagramSpecBuildResult:
    fallback = _build_fallback_spec(
        markdown=markdown,
        preferred_section_text=preferred_section_text,
        instruction=instruction,
        connection_style=connection_style,
    )
    return DiagramSpecBuildResult(
        spec=fallback,
        source="deterministic_fallback",
        model_name=None,
        provider_name=None,
        input_tokens=0,
        output_tokens=0,
    )


async def build_diagram_spec(
    *,
    markdown: str,
    preferred_section_text: str | None,
    preferred_section_kind: str | None,
    instruction: str | None,
    connection_style: str | None,
) -> DiagramSpecBuildResult:
    route = get_route_for_task(RouteTask.DIAGRAM)
    prompt = _build_spec_prompt(
        markdown=markdown,
        preferred_section_text=preferred_section_text,
        preferred_section_kind=preferred_section_kind,
        instruction=instruction,
        connection_style=connection_style,
    )
    try:
        primary = await _generate_spec_with_provider(
            provider_name=route.primary_provider,
            model_name=route.primary_model,
            prompt=prompt,
        )
        return primary
    except Exception:
        if route.fallback_provider and route.fallback_model:
            try:
                fallback_llm = await _generate_spec_with_provider(
                    provider_name=route.fallback_provider,
                    model_name=route.fallback_model,
                    prompt=prompt,
                )
                return DiagramSpecBuildResult(
                    spec=fallback_llm.spec,
                    source="llm_fallback_provider",
                    model_name=fallback_llm.model_name,
                    provider_name=fallback_llm.provider_name,
                    input_tokens=fallback_llm.input_tokens,
                    output_tokens=fallback_llm.output_tokens,
                )
            except Exception:
                pass
        return build_deterministic_diagram_spec(
            markdown=markdown,
            preferred_section_text=preferred_section_text,
            instruction=instruction,
            connection_style=connection_style,
        )

