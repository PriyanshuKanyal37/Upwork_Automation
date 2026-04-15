from __future__ import annotations

from app.application.ai.contracts import ArtifactPayload, ArtifactType, ValidationIssue, ValidationResult
from app.application.ai.validators.base import ArtifactValidator


class WorkflowArtifactValidator(ArtifactValidator):
    def validate(self, artifact: ArtifactPayload) -> ValidationResult:
        if artifact.artifact_type != ArtifactType.WORKFLOW:
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="unsupported_artifact_type",
                        message="Workflow validator received unsupported artifact type",
                    )
                ]
            )

        if not isinstance(artifact.content_json, dict):
            return ValidationResult.invalid(
                [ValidationIssue(code="missing_workflow_json", message="Workflow JSON object is required")]
            )

        nodes = artifact.content_json.get("nodes")
        connections = artifact.content_json.get("connections")
        settings = artifact.content_json.get("settings")
        if not isinstance(nodes, list) or not nodes:
            return ValidationResult.invalid(
                [ValidationIssue(code="missing_nodes", message="Workflow must contain at least one node")]
            )

        node_names: list[str] = []
        node_names_set: set[str] = set()
        has_trigger = False
        trigger_node_names: set[str] = set()

        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="invalid_node_shape",
                            message="Each workflow node must be an object",
                            path=f"nodes[{index}]",
                        )
                    ]
                )
            missing_fields = [key for key in ("id", "name", "type") if key not in node]
            if missing_fields:
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="missing_node_fields",
                            message=f"Workflow node is missing required fields: {', '.join(missing_fields)}",
                            path=f"nodes[{index}]",
                        )
                    ]
                )
            name = str(node.get("name") or "").strip()
            if not name:
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="invalid_node_name",
                            message="Workflow node name must be a non-empty string",
                            path=f"nodes[{index}].name",
                        )
                    ]
                )
            if name in node_names_set:
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="duplicate_node_name",
                            message="Workflow node names must be unique",
                            path=f"nodes[{index}].name",
                        )
                    ]
                )
            node_names.append(name)
            node_names_set.add(name)

            node_id = str(node.get("id") or "").strip()
            if not node_id:
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="invalid_node_id",
                            message="Workflow node id must be a non-empty string",
                            path=f"nodes[{index}].id",
                        )
                    ]
                )

            type_version = node.get("typeVersion")
            if not isinstance(type_version, (int, float)):
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="missing_type_version",
                            message="Workflow node must include numeric typeVersion",
                            path=f"nodes[{index}].typeVersion",
                        )
                    ]
                )

            position = node.get("position")
            if (
                not isinstance(position, list)
                or len(position) != 2
                or not all(isinstance(item, (int, float)) for item in position)
            ):
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="invalid_node_position",
                            message="Workflow node position must be [x, y] numeric array",
                            path=f"nodes[{index}].position",
                        )
                    ]
                )

            node_type = str(node.get("type") or "").lower()
            if "trigger" in node_type or "webhook" in node_type:
                has_trigger = True
                trigger_node_names.add(name)

        if not isinstance(connections, dict):
            return ValidationResult.invalid(
                [ValidationIssue(code="invalid_connections", message="Workflow connections must be an object")]
            )

        connection_keys = {str(key) for key in connections.keys()}
        unknown_connection_nodes = sorted(connection_keys - node_names_set)
        if unknown_connection_nodes:
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="invalid_connection_node",
                        message=f"Connections reference unknown node(s): {', '.join(unknown_connection_nodes)}",
                        path="connections",
                    )
                ]
            )

        incoming_counts: dict[str, int] = {name: 0 for name in node_names_set}
        outgoing_counts: dict[str, int] = {name: 0 for name in node_names_set}
        adjacency: dict[str, set[str]] = {name: set() for name in node_names_set}

        for node_name, connection_payload in connections.items():
            if not isinstance(connection_payload, dict):
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="invalid_connection_shape",
                            message="Each connection entry must be an object",
                            path=f"connections.{node_name}",
                        )
                    ]
                )
            main = connection_payload.get("main")
            if main is None:
                continue
            if not isinstance(main, list):
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="invalid_main_connection",
                            message="Connection 'main' must be a list",
                            path=f"connections.{node_name}.main",
                        )
                    ]
                )
            for branch_idx, branch in enumerate(main):
                if not isinstance(branch, list):
                    return ValidationResult.invalid(
                        [
                            ValidationIssue(
                                code="invalid_connection_branch",
                                message="Each main connection branch must be a list",
                                path=f"connections.{node_name}.main[{branch_idx}]",
                            )
                        ]
                    )
                for item_idx, edge in enumerate(branch):
                    if not isinstance(edge, dict):
                        return ValidationResult.invalid(
                            [
                                ValidationIssue(
                                    code="invalid_connection_edge",
                                    message="Each connection edge must be an object",
                                    path=f"connections.{node_name}.main[{branch_idx}][{item_idx}]",
                                )
                            ]
                        )
                    target_node = str(edge.get("node") or "").strip()
                    if not target_node or target_node not in node_names_set:
                        return ValidationResult.invalid(
                            [
                                ValidationIssue(
                                    code="unknown_connection_target",
                                    message="Connection edge references unknown target node",
                                    path=f"connections.{node_name}.main[{branch_idx}][{item_idx}].node",
                                )
                            ]
                        )
                    outgoing_counts[node_name] = outgoing_counts.get(node_name, 0) + 1
                    incoming_counts[target_node] = incoming_counts.get(target_node, 0) + 1
                    adjacency.setdefault(node_name, set()).add(target_node)

        if not has_trigger:
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="missing_trigger_node",
                        message="Workflow must include at least one trigger/webhook node",
                    )
                ]
            )

        for name in node_names:
            if name in trigger_node_names:
                continue
            if incoming_counts.get(name, 0) <= 0:
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="graph_node_without_inbound",
                            message="Each non-trigger node must have at least one inbound connection",
                            path=f"nodes[{node_names.index(name)}].name",
                        )
                    ]
                )

        if len(node_names) > 1:
            orphan_nodes = [
                name
                for name in node_names
                if incoming_counts.get(name, 0) <= 0 and outgoing_counts.get(name, 0) <= 0
            ]
            if orphan_nodes:
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="graph_orphan_node",
                            message=f"Workflow contains orphan node(s): {', '.join(orphan_nodes[:5])}",
                            path="connections",
                        )
                    ]
                )

        reachable: set[str] = set(trigger_node_names)
        frontier = list(trigger_node_names)
        while frontier:
            src = frontier.pop(0)
            for dst in adjacency.get(src, set()):
                if dst not in reachable:
                    reachable.add(dst)
                    frontier.append(dst)

        unreachable = [name for name in node_names if name not in reachable]
        if unreachable:
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="graph_unreachable_node",
                        message=f"Workflow contains node(s) unreachable from trigger: {', '.join(unreachable[:5])}",
                        path="connections",
                    )
                ]
            )

        if not isinstance(settings, dict):
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="missing_settings",
                        message="Workflow must include settings object with executionOrder",
                        path="settings",
                    )
                ]
            )

        execution_order = settings.get("executionOrder")
        if not isinstance(execution_order, str) or not execution_order.strip():
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="missing_execution_order",
                        message="Workflow settings.executionOrder is required",
                        path="settings.executionOrder",
                    )
                ]
            )

        # ── Structural connection checks ──────────────────────────────────────
        # Build node-type lookup for branch-aware checks.
        node_type_by_name: dict[str, str] = {}
        for node in nodes:
            if isinstance(node, dict):
                n = str(node.get("name") or "").strip()
                t = str(node.get("type") or "").lower()
                if n:
                    node_type_by_name[n] = t

        error_trigger_names: set[str] = {
            n for n, t in node_type_by_name.items() if "errortrigger" in t
        }
        if_node_names: set[str] = {
            n for n, t in node_type_by_name.items() if t.endswith(".if")
        }
        merge_node_names: set[str] = {
            n for n, t in node_type_by_name.items() if t.endswith(".merge")
        }

        # Check: Error Trigger must never appear as a downstream connection target.
        for node_name, connection_payload in connections.items():
            if not isinstance(connection_payload, dict):
                continue
            main = connection_payload.get("main")
            if not isinstance(main, list):
                continue
            for branch_idx, branch in enumerate(main):
                if not isinstance(branch, list):
                    continue
                for item_idx, edge in enumerate(branch):
                    if not isinstance(edge, dict):
                        continue
                    target = str(edge.get("node") or "").strip()
                    if target in error_trigger_names:
                        return ValidationResult.invalid(
                            [
                                ValidationIssue(
                                    code="error_trigger_wired_downstream",
                                    message=(
                                        f"Error Trigger node '{target}' must not be wired as a downstream "
                                        "target. It is a root trigger that fires automatically on workflow errors."
                                    ),
                                    path=f"connections.{node_name}.main[{branch_idx}][{item_idx}]",
                                )
                            ]
                        )

        # Check: IF node must have exactly two output slots when it has outgoing connections.
        for if_name in if_node_names:
            payload = connections.get(if_name)
            if not isinstance(payload, dict):
                continue
            main = payload.get("main")
            if not isinstance(main, list) or len(main) == 0:
                continue
            # Flatten all targets to check if they're split correctly.
            if len(main) == 1 and isinstance(main[0], list) and len(main[0]) >= 2:
                # All targets crammed into a single output slot — not split.
                targets = [str(e.get("node") or "") for e in main[0] if isinstance(e, dict)]
                return ValidationResult.invalid(
                    [
                        ValidationIssue(
                            code="if_node_branches_not_split",
                            message=(
                                f"IF node '{if_name}' has multiple targets in a single output slot. "
                                f"True branch must be main[0] and false branch must be main[1]. "
                                f"Found targets {targets} all in main[0]."
                            ),
                            path=f"connections.{if_name}.main",
                        )
                    ]
                )

        # Check: Merge node must receive inputs on distinct indices.
        for merge_name in merge_node_names:
            incoming_indices: list[int] = []
            for source, payload in connections.items():
                if not isinstance(payload, dict):
                    continue
                main = payload.get("main")
                if not isinstance(main, list):
                    continue
                for slot in main:
                    if not isinstance(slot, list):
                        continue
                    for edge in slot:
                        if isinstance(edge, dict) and str(edge.get("node") or "") == merge_name:
                            incoming_indices.append(int(edge.get("index") or 0))
            if len(incoming_indices) >= 2:
                duplicated = [i for i in incoming_indices if incoming_indices.count(i) > 1]
                if duplicated:
                    return ValidationResult.invalid(
                        [
                            ValidationIssue(
                                code="merge_node_duplicate_input_index",
                                message=(
                                    f"Merge node '{merge_name}' has multiple incoming connections using "
                                    f"the same input index {duplicated[0]}. "
                                    "First source must use index 0, second source must use index 1."
                                ),
                                path="connections",
                            )
                        ]
                    )

        # Check: No duplicate edges within any output slot (same target+index).
        for node_name, connection_payload in connections.items():
            if not isinstance(connection_payload, dict):
                continue
            main = connection_payload.get("main")
            if not isinstance(main, list):
                continue
            for branch_idx, branch in enumerate(main):
                if not isinstance(branch, list):
                    continue
                seen_edges: set[tuple[str, int]] = set()
                for item_idx, edge in enumerate(branch):
                    if not isinstance(edge, dict):
                        continue
                    key = (str(edge.get("node") or ""), int(edge.get("index") or 0))
                    if key in seen_edges:
                        return ValidationResult.invalid(
                            [
                                ValidationIssue(
                                    code="duplicate_connection_edge",
                                    message=(
                                        f"Duplicate connection from '{node_name}' to '{key[0]}' "
                                        f"at index {key[1]} in main[{branch_idx}]."
                                    ),
                                    path=f"connections.{node_name}.main[{branch_idx}][{item_idx}]",
                                )
                            ]
                        )
                    seen_edges.add(key)

        return ValidationResult.valid()
