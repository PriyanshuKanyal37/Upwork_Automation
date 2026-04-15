"""Structural validator for Make.com blueprints.

Intentionally lightweight. Only checks things that would break `import blueprint`
on the Make.com UI side. No auto-repair — the one-shot generator either produces
a valid blueprint or fails clearly.
"""
from __future__ import annotations

from typing import Any


class MakeValidationError(ValueError):
    """Raised when a Make.com blueprint fails structural validation."""


def validate_flat_modules(flat: dict[str, Any]) -> list[str]:
    """Validate the flat module representation emitted by the agent.

    Returns a list of human-readable error strings. Empty list = valid.
    """
    errors: list[str] = []

    if not isinstance(flat, dict):
        return ["Top-level must be an object."]

    name = flat.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("Missing or empty `name`.")

    zone = flat.get("zone")
    if not isinstance(zone, str) or not zone.strip():
        errors.append("Missing or empty `zone` (expected e.g. 'us1.make.com').")

    instant = flat.get("instant")
    if not isinstance(instant, bool):
        errors.append("`instant` must be a boolean.")

    modules = flat.get("modules")
    if not isinstance(modules, list) or not modules:
        errors.append("`modules` must be a non-empty array.")
        return errors

    ids_seen: set[int] = set()
    router_route_counts: dict[int, int] = {}
    children_by_parent_route: dict[tuple[int, int], list[int]] = {}
    first_module = modules[0]

    if not isinstance(first_module, dict) or first_module.get("parent_id") is not None:
        errors.append("First module must be a top-level trigger with parent_id=null.")

    for idx, mod in enumerate(modules):
        if not isinstance(mod, dict):
            errors.append(f"modules[{idx}] is not an object.")
            continue

        mod_id = mod.get("id")
        if not isinstance(mod_id, int) or mod_id < 1:
            errors.append(f"modules[{idx}].id must be a positive integer.")
            continue
        if mod_id in ids_seen:
            errors.append(f"Duplicate module id {mod_id}.")
        ids_seen.add(mod_id)

        module_type = mod.get("module")
        if not isinstance(module_type, str) or ":" not in module_type and module_type != "scheduler":
            errors.append(
                f"modules[{idx}].module must be 'appName:operation' format (got {module_type!r})."
            )

        version = mod.get("version")
        if not isinstance(version, int) or version < 1:
            errors.append(f"modules[{idx}].version must be a positive integer.")

        parent_id = mod.get("parent_id")
        route_index = mod.get("route_index")

        if parent_id is not None:
            if not isinstance(parent_id, int):
                errors.append(f"modules[{idx}].parent_id must be an integer or null.")
            elif parent_id not in ids_seen:
                errors.append(
                    f"modules[{idx}] references parent_id {parent_id} that does not appear earlier."
                )
            if not isinstance(route_index, int) or route_index < 0:
                errors.append(
                    f"modules[{idx}] has parent_id but missing/invalid route_index."
                )
            else:
                children_by_parent_route.setdefault((parent_id, route_index), []).append(mod_id)
        else:
            if route_index is not None:
                errors.append(
                    f"modules[{idx}] is top-level (parent_id=null) so route_index must also be null."
                )

        is_router = bool(mod.get("is_router"))
        route_count = mod.get("route_count")
        if is_router:
            if not isinstance(route_count, int) or route_count < 1:
                errors.append(
                    f"modules[{idx}] is a router but route_count is missing or < 1."
                )
            else:
                router_route_counts[mod_id] = route_count
            if mod.get("mapper") not in (None, {}):
                errors.append(f"modules[{idx}] is a router so mapper must be null or empty object.")
        else:
            mapper = mod.get("mapper")
            if mapper is not None and not isinstance(mapper, dict):
                errors.append(f"modules[{idx}].mapper must be an object or null.")

        if not isinstance(mod.get("parameters"), dict):
            errors.append(f"modules[{idx}].parameters must be an object.")

    # Every router must have all its routes populated.
    for router_id, count in router_route_counts.items():
        for ri in range(count):
            if not children_by_parent_route.get((router_id, ri)):
                errors.append(
                    f"Router id {router_id} route_index {ri} has no child modules."
                )

    return errors


def validate_nested_blueprint(blueprint: dict[str, Any]) -> list[str]:
    """Validate the final nested Make.com blueprint shape (post-transform)."""
    errors: list[str] = []

    if not isinstance(blueprint, dict):
        return ["Blueprint must be a JSON object."]

    if not isinstance(blueprint.get("name"), str) or not blueprint["name"].strip():
        errors.append("Blueprint `name` is missing or empty.")

    flow = blueprint.get("flow")
    if not isinstance(flow, list) or not flow:
        errors.append("Blueprint `flow` must be a non-empty array.")
        return errors

    metadata = blueprint.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("Blueprint `metadata` must be an object.")
    else:
        scenario = metadata.get("scenario")
        if not isinstance(scenario, dict):
            errors.append("metadata.scenario must be an object.")

    seen_ids: set[int] = set()
    _walk_flow_for_validation(flow, errors, seen_ids, path="flow")
    return errors


def _walk_flow_for_validation(
    flow: list[Any],
    errors: list[str],
    seen_ids: set[int],
    *,
    path: str,
) -> None:
    for i, mod in enumerate(flow):
        if not isinstance(mod, dict):
            errors.append(f"{path}[{i}] is not an object.")
            continue
        mod_id = mod.get("id")
        if not isinstance(mod_id, int):
            errors.append(f"{path}[{i}].id missing or not an integer.")
        else:
            if mod_id in seen_ids:
                errors.append(f"{path}[{i}] duplicate id {mod_id}.")
            seen_ids.add(mod_id)
        if "module" not in mod or not isinstance(mod["module"], str):
            errors.append(f"{path}[{i}].module missing.")
        routes = mod.get("routes")
        if routes is not None:
            if not isinstance(routes, list) or not routes:
                errors.append(f"{path}[{i}].routes must be a non-empty array when present.")
                continue
            for ri, route in enumerate(routes):
                if not isinstance(route, dict) or not isinstance(route.get("flow"), list):
                    errors.append(f"{path}[{i}].routes[{ri}].flow must be an array.")
                    continue
                _walk_flow_for_validation(
                    route["flow"], errors, seen_ids, path=f"{path}[{i}].routes[{ri}].flow"
                )
