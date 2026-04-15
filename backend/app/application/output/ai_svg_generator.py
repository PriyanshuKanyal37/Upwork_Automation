from __future__ import annotations

import re
from dataclasses import dataclass

from app.application.ai.contracts import ProviderGenerateRequest, ProviderName, RouteTask
from app.application.ai.routing import get_route_for_task
from app.infrastructure.ai.providers.factory import build_provider_adapter

_SVG_EXTRACT_RE = re.compile(r"<svg[\s\S]*?</svg>", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)

_SYSTEM_PROMPT = """You are a senior information-design illustrator. Given a document about a
project plan, you output ONE production-ready SVG flowchart that a paying client would
happily read. You have full creative control over visual style — pick whatever aesthetic
best fits the content (modern professional, sketch/hand-drawn, infographic, swimlane,
roadmap, etc). Aim for the polish level of Napkin AI, Eraser.io, or Whimsical.

HARD REQUIREMENTS (non-negotiable):
1. Output ONLY the SVG markup starting with <svg ...> and ending with </svg>. No prose,
   no markdown fences, no XML declaration, no <!DOCTYPE>.
2. Root <svg> MUST declare xmlns="http://www.w3.org/2000/svg" and a valid viewBox.
3. Use the canvas dimensions given by the user (width × height). Everything — every
   text, shape, arrow — MUST sit inside the viewBox with comfortable padding.
4. NEVER truncate text with "..." — if a label is long, wrap it onto multiple <tspan>
   lines and expand the container. Readability beats compactness.
5. Minimum font-size is 14px for body text, 18px for step titles, 24px+ for the diagram
   title. Use a safe font stack: font-family="Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif".
6. NEVER emit <script>, <foreignObject>, <iframe>, external <image href> to http URLs,
   or event attributes (onclick etc). Pure static SVG only.
7. Arrows between steps must be clearly visible: use <defs><marker> for arrowheads and
   <path>/<line> elements that unambiguously connect source to target.
8. 4-8 steps max. If the source has more, merge or condense.

STRONGLY RECOMMENDED (for quality):
- Use soft shadows (feGaussianBlur filter) and rounded corners (rx/ry on rects).
- Use a cohesive palette — 3-5 colors max, good contrast against the background.
- Number each step (badges, colored dots, or numeric prefixes).
- Include a title at the top of the diagram.
- Keep whitespace generous — a sparse layout beats a crammed one.
- For horizontal flows with 5+ steps, consider wrapping to two rows or a zigzag path
  so cards stay large enough to read.

If you receive ISSUES FROM PREVIOUS ATTEMPT, fix those specific problems while keeping
everything else that worked. Do not abandon the overall approach unless issues are
structural."""


@dataclass(frozen=True)
class SvgGenerationResult:
    svg: str
    model_name: str
    provider_name: str
    input_tokens: int
    output_tokens: int


class SvgGenerationError(Exception):
    def __init__(self, message: str, *, raw_output: str | None = None):
        super().__init__(message)
        self.raw_output = raw_output


def _strip_preamble(text: str) -> str:
    cleaned = _CODE_FENCE_RE.sub("", text or "").strip()
    match = _SVG_EXTRACT_RE.search(cleaned)
    if match:
        return match.group(0).strip()
    return cleaned


def _build_user_prompt(
    *,
    title: str,
    markdown: str,
    preferred_section_text: str | None,
    instruction: str | None,
    canvas_width: int,
    canvas_height: int,
    previous_issues: list[str] | None,
) -> str:
    focus_block = preferred_section_text.strip() if preferred_section_text else "(none — use full document)"
    user_instruction = instruction.strip() if instruction and instruction.strip() else "(none)"
    retry_block = ""
    if previous_issues:
        bulleted = "\n".join(f"- {issue}" for issue in previous_issues[:12])
        retry_block = f"\nISSUES FROM PREVIOUS ATTEMPT (fix these):\n{bulleted}\n"

    return (
        f"Canvas: {canvas_width}×{canvas_height}px (horizontal orientation preferred).\n"
        f"Diagram title: {title}\n"
        f"User instruction: {user_instruction}\n"
        f"{retry_block}"
        f"\nFocus section (use this as the primary source of steps):\n{focus_block}\n"
        f"\nFull document context:\n{markdown}\n"
        f"\nNow output the complete SVG. Remember: ONLY the <svg>...</svg> markup."
    )


async def generate_svg_flowchart(
    *,
    title: str,
    markdown: str,
    preferred_section_text: str | None,
    instruction: str | None,
    canvas_width: int,
    canvas_height: int,
    previous_issues: list[str] | None = None,
    force_fallback_provider: bool = False,
) -> SvgGenerationResult:
    route = get_route_for_task(RouteTask.DIAGRAM)
    if force_fallback_provider and route.fallback_provider and route.fallback_model:
        provider_name: ProviderName = route.fallback_provider
        model_name = route.fallback_model
    else:
        provider_name = route.primary_provider
        model_name = route.primary_model

    adapter = build_provider_adapter(provider_name)
    prompt = _build_user_prompt(
        title=title,
        markdown=markdown,
        preferred_section_text=preferred_section_text,
        instruction=instruction,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        previous_issues=previous_issues,
    )
    request = ProviderGenerateRequest(
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        model_name=model_name,
        temperature=0.6,
        max_output_tokens=8000,
        metadata={"task": "doc_flowchart_svg"},
    )
    result = await adapter.generate(request)
    raw = result.output_text or ""
    svg = _strip_preamble(raw)
    if not svg.lower().startswith("<svg"):
        raise SvgGenerationError("llm_did_not_return_svg", raw_output=raw[:500])

    return SvgGenerationResult(
        svg=svg,
        model_name=result.model_name,
        provider_name=result.provider.value,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
