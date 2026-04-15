"""Structural validator for GoHighLevel build specs.

GHL does not support JSON workflow import, so the validator only checks that
the build spec is internally consistent (valid trigger/action names, step
numbers unique, branch pointers resolve, etc.). It does NOT enforce a wire
protocol — the spec is consumed by a human in the GHL UI.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_SKILLS_MD_DIR = (
    Path(__file__).resolve().parent.parent / "skills" / "gohighlevel" / "skills_md"
)


def _extract_bullet_names(markdown: str) -> set[str]:
    """Extract the canonical names from a catalog markdown file.

    Catalog lines look like: `- Contact Created — Triggers when ...`
    Returns the set of names (left of the em dash).
    """
    names: set[str] = set()
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        # Split on em dash (—) or hyphen with spaces (" - ")
        parts = re.split(r"\s[—\-]\s", body, maxsplit=1)
        name = parts[0].strip()
        if name:
            names.add(name)
    return names


def _load_catalog() -> tuple[set[str], set[str]]:
    trigger_md_path = _SKILLS_MD_DIR / "trigger_catalog.md"
    action_md_path = _SKILLS_MD_DIR / "action_catalog.md"
    trigger_text = trigger_md_path.read_text(encoding="utf-8") if trigger_md_path.exists() else ""
    action_text = action_md_path.read_text(encoding="utf-8") if action_md_path.exists() else ""
    triggers = _extract_bullet_names(trigger_text)
    actions = _extract_bullet_names(action_text)
    return triggers, actions


_KNOWN_TRIGGERS, _KNOWN_ACTIONS = _load_catalog()

_VALID_STEP_TYPES = {"action", "wait", "if_else", "goal", "go_to", "end"}


def validate_build_spec(spec: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation errors. Empty = valid."""
    errors: list[str] = []

    if not isinstance(spec, dict):
        return ["Build spec must be a JSON object."]

    name = spec.get("workflow_name")
    if not isinstance(name, str) or not name.strip():
        errors.append("Missing or empty `workflow_name`.")

    description = spec.get("workflow_description")
    if not isinstance(description, str) or not description.strip():
        errors.append("Missing or empty `workflow_description`.")

    trigger = spec.get("trigger")
    if not isinstance(trigger, dict):
        errors.append("`trigger` must be an object.")
    else:
        trigger_type = trigger.get("type")
        if not isinstance(trigger_type, str) or not trigger_type.strip():
            errors.append("`trigger.type` is missing.")
        elif _KNOWN_TRIGGERS and trigger_type not in _KNOWN_TRIGGERS:
            # Soft warning surfaced as an error — the generator is required to
            # use catalog names.
            errors.append(
                f"`trigger.type` {trigger_type!r} is not in the known GHL trigger catalog."
            )
        if not isinstance(trigger.get("category"), str):
            errors.append("`trigger.category` must be a string.")
        filter_conditions = trigger.get("filter_conditions")
        if filter_conditions is not None and not isinstance(filter_conditions, list):
            errors.append("`trigger.filter_conditions` must be an array or omitted.")

    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("`steps` must be a non-empty array.")
        return errors

    step_numbers: set[int] = set()
    if_else_pointers: list[tuple[int, int | None, int | None]] = []

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{idx}] is not an object.")
            continue

        step_number = step.get("step_number")
        if not isinstance(step_number, int) or step_number < 1:
            errors.append(f"steps[{idx}].step_number must be a positive integer.")
            continue
        if step_number in step_numbers:
            errors.append(f"Duplicate step_number {step_number}.")
        step_numbers.add(step_number)

        step_type = step.get("step_type")
        if step_type not in _VALID_STEP_TYPES:
            errors.append(
                f"steps[{idx}].step_type must be one of {sorted(_VALID_STEP_TYPES)}, got {step_type!r}."
            )
            continue

        if step_type == "action":
            action_name = step.get("action_name")
            if not isinstance(action_name, str) or not action_name.strip():
                errors.append(f"steps[{idx}] is an action but action_name is missing.")
            elif _KNOWN_ACTIONS and action_name not in _KNOWN_ACTIONS:
                errors.append(
                    f"steps[{idx}].action_name {action_name!r} is not in the known GHL action catalog."
                )
        elif step_type == "wait":
            wait_duration = step.get("wait_duration")
            if not isinstance(wait_duration, str) or not wait_duration.strip():
                errors.append(f"steps[{idx}] is a wait step but wait_duration is missing.")
        elif step_type == "if_else":
            branch_condition = step.get("branch_condition")
            if not isinstance(branch_condition, str) or not branch_condition.strip():
                errors.append(f"steps[{idx}] is an if_else but branch_condition is missing.")
            if_true = step.get("if_true_next_step")
            if_false = step.get("if_false_next_step")
            if if_true is not None and not isinstance(if_true, int):
                errors.append(f"steps[{idx}].if_true_next_step must be an integer or null.")
                if_true = None
            if if_false is not None and not isinstance(if_false, int):
                errors.append(f"steps[{idx}].if_false_next_step must be an integer or null.")
                if_false = None
            if_else_pointers.append((step_number, if_true, if_false))

        configuration = step.get("configuration")
        if configuration is not None and not isinstance(configuration, dict):
            errors.append(f"steps[{idx}].configuration must be an object or omitted.")

    # Verify if_else branch pointers resolve to real step numbers.
    for src, if_true, if_false in if_else_pointers:
        if if_true is not None and if_true not in step_numbers:
            errors.append(
                f"if_else step {src} has if_true_next_step={if_true} which is not a valid step number."
            )
        if if_false is not None and if_false not in step_numbers:
            errors.append(
                f"if_else step {src} has if_false_next_step={if_false} which is not a valid step number."
            )

    build_time = spec.get("estimated_build_time_minutes")
    if build_time is not None and (not isinstance(build_time, int) or build_time < 1):
        errors.append("`estimated_build_time_minutes` must be a positive integer or omitted.")

    integrations = spec.get("required_integrations")
    if integrations is not None and not isinstance(integrations, list):
        errors.append("`required_integrations` must be an array or omitted.")

    custom_fields = spec.get("required_custom_fields")
    if custom_fields is not None and not isinstance(custom_fields, list):
        errors.append("`required_custom_fields` must be an array or omitted.")

    return errors
