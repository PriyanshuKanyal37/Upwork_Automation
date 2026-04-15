from __future__ import annotations

import html
import math
import tempfile
from pathlib import Path

from app.infrastructure.errors.exceptions import AppException

from .diagram_layout import HorizontalLayout, LayoutEdge, LayoutNode, build_horizontal_layout
from .diagram_models import DiagramSpec

_PALETTE = (
    "#4E8EF7",
    "#2FBF71",
    "#E6B91E",
    "#F08A24",
    "#EA5A5A",
    "#D85DB1",
    "#27A6D9",
    "#8C6BE7",
)
_BG_COLOR = "#ECECEC"
_TITLE_COLOR = "#42484E"
_TEXT_COLOR = "#4F5660"
_PATH_COLOR = "#707780"
_FONT_FAMILY = "Inter, 'Segoe UI', Roboto, Arial, sans-serif"


def _step_color(index: int, override: str | None = None) -> str:
    if override:
        sanitized = override.strip()
        if sanitized.startswith("#") and len(sanitized) in {4, 7}:
            return sanitized
    return _PALETTE[index % len(_PALETTE)]


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines


def _truncate_lines(lines: list[str], *, max_lines: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    trimmed = lines[:max_lines]
    last = trimmed[-1]
    if len(last) > 2:
        trimmed[-1] = last[:-1].rstrip() + "..."
    return trimmed


def _draw_text_block(*, x: float, y: float, lines: list[str], color: str, size: int, weight: int = 500) -> str:
    chunks: list[str] = []
    for idx, line in enumerate(lines):
        dy = idx * (size + 5)
        chunks.append(
            f'<text x="{x:.1f}" y="{y + dy:.1f}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" font-family="{_FONT_FAMILY}" text-anchor="middle">{_escape(line)}</text>'
        )
    return "\n".join(chunks)


def _diagram_header(*, width: int, height: int, title: str) -> str:
    title_lines = _truncate_lines(_wrap_text(title, max(28, int(width / 34))), max_lines=2)
    title_y = 82 if len(title_lines) == 1 else 66
    title_svg = _draw_text_block(
        x=width / 2,
        y=title_y,
        lines=title_lines,
        color=_TITLE_COLOR,
        size=52 if len(title_lines) == 1 else 42,
        weight=730,
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        "<defs>\n"
        '<linearGradient id="canvasGrad" x1="0" y1="0" x2="1" y2="1">\n'
        '<stop offset="0%" stop-color="#F7F8FB"/>\n'
        '<stop offset="100%" stop-color="#E6E9EF"/>\n'
        "</linearGradient>\n"
        '<filter id="cardShadow" x="-20%" y="-20%" width="140%" height="140%">\n'
        '<feDropShadow dx="0" dy="3" stdDeviation="2.1" flood-color="#000" flood-opacity="0.18"/>\n'
        "</filter>\n"
        '<marker id="flowArrow" markerWidth="12" markerHeight="8" refX="10" refY="4" orient="auto">\n'
        f'<polygon points="0 0, 11 4, 0 8" fill="{_PATH_COLOR}"/>\n'
        "</marker>\n"
        "</defs>\n"
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#canvasGrad)"/>\n'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{_BG_COLOR}" opacity="0.16"/>\n'
        f"{title_svg}\n"
    )


def _edge_label_position(edge: LayoutEdge) -> tuple[float, float] | None:
    if not edge.label:
        return None
    best_len = -1.0
    best_mid: tuple[float, float] | None = None
    for p1, p2 in zip(edge.points[:-1], edge.points[1:]):
        seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if seg_len > best_len:
            best_len = seg_len
            best_mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    if best_mid is None:
        return None
    return (best_mid[0], best_mid[1] - 10)


def _build_edge_path(points: tuple[tuple[float, float], ...], *, connection_style: str) -> str:
    if connection_style not in {"curved"} or len(points) < 3:
        return " ".join(
            (
                f"M {points[0][0]:.1f} {points[0][1]:.1f}",
                *[f"L {x:.1f} {y:.1f}" for x, y in points[1:]],
            )
        )

    # Gentle smoothing over orthogonal anchors for a cleaner organic variant.
    path_chunks: list[str] = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for idx in range(1, len(points)):
        prev = points[idx - 1]
        curr = points[idx]
        cx = (prev[0] + curr[0]) / 2
        cy = (prev[1] + curr[1]) / 2
        path_chunks.append(f"Q {prev[0]:.1f} {prev[1]:.1f} {cx:.1f} {cy:.1f}")
    path_chunks.append(f"L {points[-1][0]:.1f} {points[-1][1]:.1f}")
    return " ".join(path_chunks)


def _draw_connectors(layout: HorizontalLayout, *, connection_style: str) -> str:
    pieces: list[str] = []
    for edge in layout.edges:
        path = _build_edge_path(edge.points, connection_style=connection_style)
        dash = ' stroke-dasharray="10 8"' if edge.edge_type == "feedback" else ""
        pieces.append(
            f'<path d="{path}" stroke="{_PATH_COLOR}" stroke-width="3.4" fill="none" '
            f'marker-end="url(#flowArrow)" stroke-linecap="round" stroke-linejoin="round"{dash} opacity="0.9"/>'
        )
        # Skip connector labels in the visual to avoid clutter in dense horizontal layouts.
    return "\n".join(pieces)


def _draw_swimlanes(layout: HorizontalLayout, *, width: int) -> str:
    if not layout.two_rows:
        return ""
    top = min(node.top for node in layout.ordered_nodes if node.row == 0) - 20
    bottom = min(node.top for node in layout.ordered_nodes if node.row == 1) - 20
    lane_h = layout.card_height + 40
    return "\n".join(
        (
            f'<rect x="68" y="{top:.1f}" width="{width - 136}" height="{lane_h:.1f}" rx="20" fill="#ffffff30" stroke="#ffffff77" stroke-width="1"/>',
            f'<rect x="68" y="{bottom:.1f}" width="{width - 136}" height="{lane_h:.1f}" rx="20" fill="#ffffff24" stroke="#ffffff66" stroke-width="1"/>',
        )
    )


def _draw_single_card(node: LayoutNode, *, scale: float) -> str:
    color = _step_color(node.index, override=node.color_token)
    radius = 20.0 * scale
    badge_r = 20.0 * scale
    x0 = node.left
    y0 = node.top
    title_chars = max(14, int(node.width / 15.8))
    detail_chars = max(16, int(node.width / 13.8))
    title_lines = _truncate_lines(_wrap_text(node.title, title_chars), max_lines=2)
    detail_lines = _truncate_lines(_wrap_text(node.detail or "", detail_chars), max_lines=2) if node.detail else []
    title_size = max(22, int(28 * scale))
    detail_size = max(16, int(18 * scale))
    badge_x = x0 + (36.0 * scale)
    badge_y = node.y

    parts: list[str] = []
    parts.append(
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{node.width:.1f}" height="{node.height:.1f}" '
        f'rx="{radius:.1f}" fill="#FEFEFF" stroke="{color}" stroke-width="2.6" filter="url(#cardShadow)"/>'
    )
    parts.append(
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{node.width:.1f}" height="{max(14.0, 18.0 * scale):.1f}" '
        f'rx="{radius:.1f}" fill="{color}" opacity="0.18"/>'
    )
    parts.append(f'<circle cx="{badge_x:.1f}" cy="{badge_y:.1f}" r="{badge_r:.1f}" fill="{color}"/>')
    parts.append(
        f'<text x="{badge_x:.1f}" y="{badge_y + (8 * scale):.1f}" font-size="{max(17, int(22 * scale))}" '
        f'font-weight="700" fill="#fff" text-anchor="middle">{node.index + 1}</text>'
    )
    parts.append(
        _draw_text_block(
            x=node.x + (18.0 * scale),
            y=node.y - (10.0 * scale),
            lines=title_lines,
            color=_TITLE_COLOR,
            size=title_size,
            weight=730,
        )
    )
    if detail_lines:
        parts.append(
            _draw_text_block(
                x=node.x + (18.0 * scale),
                y=node.y + (42.0 * scale),
                lines=detail_lines,
                color=_TEXT_COLOR,
                size=detail_size,
                weight=560,
            )
        )
    return "\n".join(parts)


def _draw_cards(spec: DiagramSpec, *, layout: HorizontalLayout, width: int) -> str:
    scale = min(max(width / 1600, 0.98), 1.2)
    pieces: list[str] = []
    if spec.layout_family == "swimlane_process":
        pieces.append(_draw_swimlanes(layout, width=width))
    for node in layout.ordered_nodes:
        pieces.append(_draw_single_card(node, scale=scale))
    return "\n".join(pieces)


def render_diagram_svg(*, spec: DiagramSpec, width: int = 1600, height: int = 1200) -> str:
    if spec.orientation != "horizontal":
        raise AppException(
            status_code=422,
            code="invalid_diagram_orientation",
            message="Diagram orientation must be horizontal",
        )

    layout = build_horizontal_layout(spec=spec, width=width, height=height)
    header = _diagram_header(width=width, height=height, title=spec.title)
    body = "\n".join(
        (
            _draw_connectors(layout, connection_style=spec.connection_style),
            _draw_cards(spec, layout=layout, width=width),
        )
    )
    footer = (
        f'<text x="{width - 30}" y="{height - 22}" font-size="18" font-weight="500" fill="#9EA3AA" font-family="{_FONT_FAMILY}" text-anchor="end">'
        "Generated by AgentLoopr</text>\n"
        "</svg>"
    )
    return header + body + "\n" + footer


async def convert_svg_to_png(*, svg_content: str, width: int = 1600, height: int = 1200) -> bytes:
    try:
        import cairosvg  # type: ignore

        return cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), output_width=width, output_height=height)
    except Exception as cairo_exc:
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except Exception as playwright_import_exc:
            raise AppException(
                status_code=503,
                code="diagram_png_conversion_unavailable",
                message="PNG conversion is unavailable (CairoSVG and Playwright are not available)",
                details={
                    "cairosvg_error": str(cairo_exc),
                    "playwright_import_error": str(playwright_import_exc),
                },
            ) from playwright_import_exc

        with tempfile.TemporaryDirectory(prefix="diagram-render-") as tmp:
            svg_path = Path(tmp) / "diagram.svg"
            png_path = Path(tmp) / "diagram.png"
            svg_path.write_text(svg_content, encoding="utf-8")
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                page = await browser.new_page(viewport={"width": width, "height": height})
                await page.goto(svg_path.as_uri())
                await page.screenshot(path=str(png_path), full_page=True)
                await browser.close()
            if not png_path.exists():
                raise AppException(
                    status_code=503,
                    code="diagram_png_conversion_failed",
                    message="Playwright fallback did not produce a PNG file",
                )
            return png_path.read_bytes()
