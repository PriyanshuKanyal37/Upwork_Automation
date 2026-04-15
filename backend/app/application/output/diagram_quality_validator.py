from __future__ import annotations

import math
from dataclasses import dataclass

from .diagram_layout import LayoutEdge, LayoutNode, build_horizontal_layout
from .diagram_models import DiagramSpec


@dataclass(frozen=True)
class DiagramQualityResult:
    passed: bool
    status: str
    score: float
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _node_overlap(a: LayoutNode, b: LayoutNode) -> bool:
    return not (
        a.right <= b.left
        or b.right <= a.left
        or a.bottom <= b.top
        or b.bottom <= a.top
    )


def _node_min_gap(a: LayoutNode, b: LayoutNode) -> float:
    gap_x = max(a.left - b.right, b.left - a.right, 0.0)
    gap_y = max(a.top - b.bottom, b.top - a.bottom, 0.0)
    if gap_x == 0.0:
        return gap_y
    if gap_y == 0.0:
        return gap_x
    return math.hypot(gap_x, gap_y)


def _segment_intersects_node(
    *,
    p1: tuple[float, float],
    p2: tuple[float, float],
    node: LayoutNode,
    padding: float = 10.0,
) -> bool:
    left = node.left + padding
    right = node.right - padding
    top = node.top + padding
    bottom = node.bottom - padding
    x1, y1 = p1
    x2, y2 = p2

    if math.isclose(y1, y2, abs_tol=1e-3):
        y = y1
        if y < top or y > bottom:
            return False
        seg_min_x = min(x1, x2)
        seg_max_x = max(x1, x2)
        return not (seg_max_x < left or seg_min_x > right)

    if math.isclose(x1, x2, abs_tol=1e-3):
        x = x1
        if x < left or x > right:
            return False
        seg_min_y = min(y1, y2)
        seg_max_y = max(y1, y2)
        return not (seg_max_y < top or seg_min_y > bottom)

    return False


def _orthogonal_intersection(
    *,
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    ax1, ay1 = a1
    ax2, ay2 = a2
    bx1, by1 = b1
    bx2, by2 = b2
    a_h = math.isclose(ay1, ay2, abs_tol=1e-3)
    b_h = math.isclose(by1, by2, abs_tol=1e-3)
    a_v = math.isclose(ax1, ax2, abs_tol=1e-3)
    b_v = math.isclose(bx1, bx2, abs_tol=1e-3)

    if a_h and b_v:
        return (
            min(ax1, ax2) <= bx1 <= max(ax1, ax2)
            and min(by1, by2) <= ay1 <= max(by1, by2)
        )
    if a_v and b_h:
        return (
            min(bx1, bx2) <= ax1 <= max(bx1, bx2)
            and min(ay1, ay2) <= by1 <= max(ay1, ay2)
        )
    return False


def _edge_segments(edge: LayoutEdge) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(edge.points[:-1], edge.points[1:]))


def validate_diagram_quality(*, spec: DiagramSpec, width: int, height: int) -> DiagramQualityResult:
    layout = build_horizontal_layout(spec=spec, width=width, height=height)
    errors: list[str] = []
    warnings: list[str] = []
    score = 100.0

    nodes = list(layout.ordered_nodes)
    for idx, left in enumerate(nodes):
        if left.left < 8 or left.right > width - 8 or left.top < 90 or left.bottom > height - 16:
            errors.append(f"node_clipped:{left.id}")
            score -= 20
        for right in nodes[idx + 1 :]:
            if _node_overlap(left, right):
                errors.append(f"node_overlap:{left.id}->{right.id}")
                score -= 35
                continue
            if _node_min_gap(left, right) < 18:
                warnings.append(f"node_spacing_tight:{left.id}->{right.id}")
                score -= 6

    for edge in layout.edges:
        source = layout.nodes.get(edge.source_id)
        target = layout.nodes.get(edge.target_id)
        if source is None or target is None:
            errors.append("edge_node_missing")
            score -= 20
            continue

        if target.x + 8 < source.x and edge.edge_type != "feedback":
            errors.append(f"edge_backward:{edge.source_id}->{edge.target_id}")
            score -= 14

        if edge.label and len(edge.label.strip()) > 28:
            warnings.append(f"edge_label_long:{edge.source_id}->{edge.target_id}")
            score -= 2

        for p1, p2 in _edge_segments(edge):
            seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if seg_len < 8.0:
                warnings.append(f"edge_segment_too_short:{edge.source_id}->{edge.target_id}")
                score -= 1.5
            for node in nodes:
                if node.id in {edge.source_id, edge.target_id}:
                    continue
                if _segment_intersects_node(p1=p1, p2=p2, node=node):
                    errors.append(f"edge_collides_node:{edge.source_id}->{edge.target_id}:{node.id}")
                    score -= 9
                    break
        end_x = edge.points[-1][0]
        start_x = edge.points[0][0]
        if edge.edge_type != "feedback":
            if end_x < start_x - 1.0:
                errors.append(f"edge_arrow_direction_invalid:{edge.source_id}->{edge.target_id}")
                score -= 12
            elif math.isclose(end_x, start_x, abs_tol=1.0) and target.y < source.y - 1.0:
                errors.append(f"edge_arrow_direction_invalid:{edge.source_id}->{edge.target_id}")
                score -= 12

    crossings = 0
    for idx, edge_a in enumerate(layout.edges):
        segments_a = _edge_segments(edge_a)
        for edge_b in layout.edges[idx + 1 :]:
            if {edge_a.source_id, edge_a.target_id} & {edge_b.source_id, edge_b.target_id}:
                continue
            segments_b = _edge_segments(edge_b)
            hit = False
            for a1, a2 in segments_a:
                for b1, b2 in segments_b:
                    if _orthogonal_intersection(a1=a1, a2=a2, b1=b1, b2=b2):
                        crossings += 1
                        hit = True
                        break
                if hit:
                    break
    if crossings > 1:
        errors.append(f"edge_crossings:{crossings}")
        score -= min(28.0, (crossings - 1) * 6.0)
    elif crossings > 0:
        warnings.append(f"edge_crossings:{crossings}")
        score -= crossings * 2.0

    normalized_score = max(0.0, min(100.0, round(score, 2)))
    passed = len(errors) == 0
    status = "passed" if passed else "failed"
    return DiagramQualityResult(
        passed=passed,
        status=status,
        score=normalized_score,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
