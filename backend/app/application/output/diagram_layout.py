from __future__ import annotations

import math
from dataclasses import dataclass

from .diagram_models import DiagramSpec


@dataclass(frozen=True)
class LayoutNode:
    id: str
    title: str
    detail: str | None
    color_token: str | None
    index: int
    row: int
    column: int
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x - (self.width / 2)

    @property
    def right(self) -> float:
        return self.x + (self.width / 2)

    @property
    def top(self) -> float:
        return self.y - (self.height / 2)

    @property
    def bottom(self) -> float:
        return self.y + (self.height / 2)


@dataclass(frozen=True)
class LayoutEdge:
    source_id: str
    target_id: str
    edge_type: str
    label: str | None
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class HorizontalLayout:
    nodes: dict[str, LayoutNode]
    ordered_nodes: tuple[LayoutNode, ...]
    edges: tuple[LayoutEdge, ...]
    columns: int
    two_rows: bool
    card_width: float
    card_height: float


def _normalize_points(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    if not points:
        return tuple()
    cleaned: list[tuple[float, float]] = [points[0]]
    for point in points[1:]:
        px, py = cleaned[-1]
        if math.isclose(px, point[0], abs_tol=1e-3) and math.isclose(py, point[1], abs_tol=1e-3):
            continue
        cleaned.append(point)
    return tuple(cleaned)


def _route_points(
    *,
    source: LayoutNode,
    target: LayoutNode,
    edge_type: str,
    edge_index: int,
    top_lane: float,
    bottom_lane: float,
    middle_lane: float,
) -> tuple[tuple[float, float], ...]:
    lane_offset = (edge_index % 3) * 14.0
    is_forward = target.column >= source.column

    if source.row == target.row and is_forward and target.column == source.column + 1 and edge_type == "sequence":
        return ((source.right, source.y), (target.left, target.y))

    if source.row != target.row:
        if source.row < target.row:
            start = (source.x, source.bottom)
            end = (target.x, target.top)
        else:
            start = (source.x, source.top)
            end = (target.x, target.bottom)
        lane_y = middle_lane + (lane_offset if source.row == 0 else -lane_offset)
        return _normalize_points([start, (start[0], lane_y), (end[0], lane_y), end])

    if is_forward:
        start = (source.right, source.y)
        end = (target.left, target.y)
    else:
        start = (source.left, source.y)
        end = (target.right, target.y)

    lane_y = top_lane - lane_offset
    if edge_type in {"merge"}:
        lane_y = bottom_lane + lane_offset
    elif edge_type in {"feedback"} or not is_forward:
        lane_y = top_lane - 28.0 - lane_offset
    elif edge_type == "sequence" and target.column > source.column + 1:
        lane_y = bottom_lane + lane_offset

    return _normalize_points([start, (start[0], lane_y), (end[0], lane_y), end])


def build_horizontal_layout(*, spec: DiagramSpec, width: int, height: int) -> HorizontalLayout:
    count = len(spec.steps)
    # Keep dense flows readable in narrow UI previews by switching to a
    # horizontal two-lane "paired columns" layout from 6+ steps onward.
    two_rows = count >= 6
    columns = max(math.ceil(count / 2), 1) if two_rows else max(count, 1)

    margin_x = max(56.0, min(width * 0.05, 92.0))
    usable_width = max(620.0, width - (margin_x * 2))
    rough_gap = usable_width / max(1, columns - 1) if columns > 1 else 0.0
    card_width = min(340.0, max(220.0, rough_gap * 0.80 if columns > 1 else usable_width * 0.62))
    if columns > 1:
        # Ensure horizontal spacing never collapses into overlapping cards.
        min_horizontal_gap = 24.0
        max_card_width = (usable_width - ((columns - 1) * min_horizontal_gap)) / columns
        card_width = min(card_width, max_card_width)
    card_width = max(180.0, card_width)
    card_height = 180.0

    if two_rows:
        top_y = height * 0.35
        bottom_y = height * 0.66
    else:
        top_y = height * 0.52
        bottom_y = top_y

    top_lane = top_y - (card_height / 2) - 56.0
    bottom_lane = bottom_y + (card_height / 2) + 56.0
    middle_lane = ((top_y + (card_height / 2)) + (bottom_y - (card_height / 2))) / 2

    ordered_nodes: list[LayoutNode] = []
    nodes_by_id: dict[str, LayoutNode] = {}
    for idx, step in enumerate(spec.steps):
        if two_rows:
            row = 0 if idx % 2 == 0 else 1
            column = idx // 2
            y = top_y if row == 0 else bottom_y
            row_count = columns
        else:
            row = 0
            column = idx
            y = top_y
            row_count = max(1, count)

        if row_count == 1:
            x = width / 2
        else:
            min_center_x = margin_x + (card_width / 2)
            max_center_x = width - margin_x - (card_width / 2)
            row_gap = (max_center_x - min_center_x) / max(1, row_count - 1)
            x = min_center_x + (column * row_gap)

        node = LayoutNode(
            id=step.id,
            title=step.title,
            detail=step.detail,
            color_token=step.color_token,
            index=idx,
            row=row,
            column=column,
            x=x,
            y=y,
            width=card_width,
            height=card_height,
        )
        ordered_nodes.append(node)
        nodes_by_id[node.id] = node

    edges: list[LayoutEdge] = []
    for edge_index, conn in enumerate(spec.connections):
        source = nodes_by_id.get(conn.source_id)
        target = nodes_by_id.get(conn.target_id)
        if source is None or target is None or source.id == target.id:
            continue
        points = _route_points(
            source=source,
            target=target,
            edge_type=conn.edge_type,
            edge_index=edge_index,
            top_lane=top_lane,
            bottom_lane=bottom_lane,
            middle_lane=middle_lane,
        )
        if len(points) < 2:
            continue
        edges.append(
            LayoutEdge(
                source_id=conn.source_id,
                target_id=conn.target_id,
                edge_type=conn.edge_type,
                label=conn.label,
                points=points,
            )
        )

    return HorizontalLayout(
        nodes=nodes_by_id,
        ordered_nodes=tuple(ordered_nodes),
        edges=tuple(edges),
        columns=columns,
        two_rows=two_rows,
        card_width=card_width,
        card_height=card_height,
    )
