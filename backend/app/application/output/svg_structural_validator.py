from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

_SVG_NS = "http://www.w3.org/2000/svg"
_FORBIDDEN_TAGS = {"script", "foreignObject", "iframe", "object", "embed"}
_MIN_TEXT_FONT_PX = 9.0
_MAX_SVG_BYTES = 600_000


@dataclass
class SvgStructuralResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    viewbox: tuple[float, float, float, float] | None = None
    text_count: int = 0


def _localname(tag: object) -> str:
    # lxml may expose processing instructions/comments where `tag` is not a str.
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _parse_viewbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        nums = tuple(float(p) for p in parts)
    except ValueError:
        return None
    if nums[2] <= 0 or nums[3] <= 0:
        return None
    return nums  # type: ignore[return-value]


def _parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    stripped = value.strip().rstrip("px").rstrip("pt")
    try:
        return float(stripped)
    except ValueError:
        return default


def validate_svg_structure(svg_content: str, *, expected_min_text_elements: int = 3) -> SvgStructuralResult:
    """Fast structural checks on LLM-produced SVG.

    Catches issues before we spend tokens on visual validation:
    malformed XML, security-sensitive elements, missing viewBox,
    text elements completely outside the canvas, tiny unreadable fonts.
    """
    result = SvgStructuralResult(passed=False)

    if not svg_content or not svg_content.strip():
        result.errors.append("empty_svg")
        return result

    if len(svg_content.encode("utf-8")) > _MAX_SVG_BYTES:
        result.errors.append("svg_too_large")
        return result

    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        root = etree.fromstring(svg_content.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as exc:
        result.errors.append(f"xml_syntax_error:{exc.msg}")
        return result

    if _localname(root.tag).lower() != "svg":
        result.errors.append("root_not_svg")
        return result

    viewbox = _parse_viewbox(root.get("viewBox") or root.get("viewbox"))
    if viewbox is None:
        width = _parse_float(root.get("width"))
        height = _parse_float(root.get("height"))
        if width > 0 and height > 0:
            viewbox = (0.0, 0.0, width, height)
        else:
            result.errors.append("missing_viewbox")
            return result
    result.viewbox = viewbox

    vb_x, vb_y, vb_w, vb_h = viewbox
    if vb_w < 200 or vb_h < 150:
        result.errors.append("viewbox_too_small")
        return result

    text_count = 0
    out_of_bounds = 0
    tiny_font = 0
    for node in root.iter():
        local = _localname(node.tag).lower()
        if not local:
            continue
        if local in _FORBIDDEN_TAGS:
            result.errors.append(f"forbidden_element:{local}")
            return result

        if local == "text":
            text_count += 1
            x = _parse_float(node.get("x"))
            y = _parse_float(node.get("y"))
            if x < vb_x - 10 or x > vb_x + vb_w + 10 or y < vb_y - 10 or y > vb_y + vb_h + 10:
                out_of_bounds += 1
            font_size = _parse_float(node.get("font-size"))
            if 0 < font_size < _MIN_TEXT_FONT_PX:
                tiny_font += 1

    result.text_count = text_count

    if text_count < expected_min_text_elements:
        result.errors.append(f"too_few_text_elements:{text_count}<{expected_min_text_elements}")
        return result

    if out_of_bounds > 0:
        result.errors.append(f"text_out_of_viewbox:{out_of_bounds}")
        return result

    if tiny_font > 0:
        result.warnings.append(f"tiny_font_size:{tiny_font}")

    result.passed = True
    return result
