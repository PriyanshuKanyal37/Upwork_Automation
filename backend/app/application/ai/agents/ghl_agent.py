"""GoHighLevel build-spec generator agent.

Single structured-output Claude call. Returns a human-readable workflow build
spec (trigger + ordered steps with branch pointers) that a user manually
recreates in the GHL Advanced Builder UI, since GHL has no JSON workflow import.

Also emits a markdown checklist version of the build spec for easy copy/paste
into docs, tickets, or Loom scripts.
"""
from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from app.application.ai.contracts import (
    ArtifactPayload,
    ArtifactType,
    ProviderGenerateRequest,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.prompt.ghl_workflow import (
    SYSTEM_PROMPT as GHL_SYSTEM_PROMPT,
    build_user_prompt,
)
from app.application.ai.validators.ghl_validator import validate_build_spec
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter


# JSON schema passed to Anthropic structured outputs.
# Flat (no nesting) because structured outputs don't support recursive schemas
# and branching is expressed via if_true_next_step / if_false_next_step pointers.
GHL_BUILD_SPEC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "workflow_name": {"type": "string"},
        "workflow_description": {"type": "string"},
        "trigger": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "category": {"type": "string"},
                "configuration_notes": {"type": "string"},
                "filter_conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "operator": {"type": "string"},
                            "value": {"type": "string"},
                        },
                        "required": ["field", "operator", "value"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["type", "category", "configuration_notes", "filter_conditions"],
            "additionalProperties": False,
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "step_type": {
                        "type": "string",
                        "enum": ["action", "wait", "if_else", "goal", "go_to", "end"],
                    },
                    "name": {"type": "string"},
                    "action_name": {"type": ["string", "null"]},
                    "action_category": {"type": ["string", "null"]},
                    "configuration": {
                        "type": "object",
                        "properties": {
                            "target_workflow": {"type": ["string", "null"]},
                            "goal_name": {"type": ["string", "null"]},
                            "tag": {"type": ["string", "null"]},
                            "pipeline_stage": {"type": ["string", "null"]},
                            "message_template": {"type": ["string", "null"]},
                            "wait_value": {"type": ["string", "number", "null"]},
                            "wait_unit": {"type": ["string", "null"]},
                            "custom_field": {"type": ["string", "null"]},
                            "custom_value": {"type": ["string", "number", "boolean", "null"]},
                            "raw": {"type": ["string", "null"]},
                        },
                        "additionalProperties": False,
                    },
                    "wait_duration": {"type": ["string", "null"]},
                    "branch_condition": {"type": ["string", "null"]},
                    "if_true_next_step": {"type": ["integer", "null"]},
                    "if_false_next_step": {"type": ["integer", "null"]},
                    "notes": {"type": "string"},
                },
                "required": [
                    "step_number",
                    "step_type",
                    "name",
                    "action_name",
                    "action_category",
                    "configuration",
                    "wait_duration",
                    "branch_condition",
                    "if_true_next_step",
                    "if_false_next_step",
                    "notes",
                ],
                "additionalProperties": False,
            },
        },
        "estimated_build_time_minutes": {"type": "integer"},
        "required_integrations": {"type": "array", "items": {"type": "string"}},
        "required_custom_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "workflow_name",
        "workflow_description",
        "trigger",
        "steps",
        "estimated_build_time_minutes",
        "required_integrations",
        "required_custom_fields",
    ],
    "additionalProperties": False,
}


async def run_ghl_agent(
    *,
    job_context: dict[str, Any],
    provider: AnthropicProviderAdapter,
    model_name: str,
) -> ArtifactPayload:
    """Generate one GHL workflow build spec in a single Claude call."""
    user_prompt = build_user_prompt(job_context)

    first_call_started_at = perf_counter()
    spec, usage_primary = await _single_call(
        provider=provider,
        model_name=model_name,
        system_prompt=GHL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    first_call_latency_ms = int((perf_counter() - first_call_started_at) * 1000)

    errors = validate_build_spec(spec)
    usage_retry: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    retry_latency_ms = 0
    retried = False

    if errors:
        retried = True
        retry_prompt = (
            user_prompt
            + "\n\n---\n\n"
            "Your previous attempt produced this build spec:\n"
            f"{json.dumps(spec, separators=(',', ':'))}\n\n"
            "It failed validation with these errors:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nProduce a corrected build spec. Fix ONLY the listed issues."
        )
        retry_started_at = perf_counter()
        spec_retry, usage_retry = await _single_call(
            provider=provider,
            model_name=model_name,
            system_prompt=GHL_SYSTEM_PROMPT,
            user_prompt=retry_prompt,
        )
        retry_latency_ms = int((perf_counter() - retry_started_at) * 1000)
        errors_retry = validate_build_spec(spec_retry)
        spec = spec_retry
        errors = errors_retry

    markdown_checklist = _build_markdown_checklist(spec)

    total_input = int(usage_primary["input_tokens"]) + int(usage_retry["input_tokens"])
    total_output = int(usage_primary["output_tokens"]) + int(usage_retry["output_tokens"])

    return ArtifactPayload(
        artifact_type=ArtifactType.GHL_WORKFLOW,
        content_text=markdown_checklist,
        content_json=spec,
        metadata={
            "agent_mode": "one_shot_structured",
            "retried": retried,
            "validation_errors": errors,
            "usage": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "latency_ms": first_call_latency_ms + retry_latency_ms,
            },
            "model_name": model_name,
            "note": (
                "GoHighLevel does not support JSON workflow import. This is a "
                "build spec — follow the markdown checklist in content_text to "
                "recreate the workflow manually in the GHL Advanced Builder."
            ),
        },
    )


async def _single_call(
    *,
    provider: AnthropicProviderAdapter,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    request = ProviderGenerateRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model_name=model_name,
        temperature=0.2,
        max_output_tokens=6000,
        response_schema=GHL_BUILD_SPEC_SCHEMA,
        metadata={"task": "ghl_workflow"},
    )
    result = await provider.generate(request)

    raw_text = result.output_text or ""
    if not raw_text.strip():
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Empty response from Claude for GHL workflow build spec",
            details={"model_name": model_name},
        )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Structured-output response was not valid JSON",
            details={"model_name": model_name, "error": str(exc)},
        ) from exc

    if not isinstance(parsed, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Structured-output response was not a JSON object",
            details={"model_name": model_name},
        )

    usage = {
        "input_tokens": int(result.input_tokens or 0),
        "output_tokens": int(result.output_tokens or 0),
    }
    return parsed, usage


def _build_markdown_checklist(spec: dict[str, Any]) -> str:
    """Convert a validated build spec into a human-readable markdown checklist."""
    lines: list[str] = []
    name = str(spec.get("workflow_name") or "Untitled workflow")
    description = str(spec.get("workflow_description") or "").strip()
    estimated = spec.get("estimated_build_time_minutes")
    integrations = spec.get("required_integrations") or []
    custom_fields = spec.get("required_custom_fields") or []

    lines.append(f"# GoHighLevel Build Spec: {name}")
    lines.append("")
    lines.append(
        "> ⚠️ GoHighLevel does not support JSON workflow import. Follow this "
        "checklist to recreate the workflow inside the GHL Advanced Builder."
    )
    lines.append("")
    if description:
        lines.append(f"**Purpose:** {description}")
        lines.append("")
    if isinstance(estimated, int):
        lines.append(f"**Estimated build time:** ~{estimated} minutes")
        lines.append("")

    if integrations:
        lines.append("## Prerequisites — Required Integrations")
        for item in integrations:
            lines.append(f"- [ ] {item}")
        lines.append("")

    if custom_fields:
        lines.append("## Prerequisites — Required Custom Fields")
        for item in custom_fields:
            lines.append(f"- [ ] Create custom field: `{item}`")
        lines.append("")

    trigger = spec.get("trigger") or {}
    lines.append("## Step 1 — Configure the Trigger")
    lines.append(f"- **Trigger type:** {trigger.get('type', '(not specified)')}")
    if trigger.get("category"):
        lines.append(f"- **Category:** {trigger['category']}")
    if trigger.get("configuration_notes"):
        lines.append(f"- **Configuration:** {trigger['configuration_notes']}")
    filter_conditions = trigger.get("filter_conditions") or []
    if filter_conditions:
        lines.append("- **Filter conditions:**")
        for cond in filter_conditions:
            if isinstance(cond, dict):
                lines.append(
                    f"  - `{cond.get('field', '?')}` {cond.get('operator', '?')} "
                    f"`{cond.get('value', '?')}`"
                )
    lines.append("")

    steps = spec.get("steps") or []
    lines.append("## Steps — Add These In Order")
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_number = step.get("step_number")
        step_type = step.get("step_type", "action")
        step_name = step.get("name") or f"Step {step_number}"
        lines.append(f"### Step {step_number}: {step_name}  _(type: {step_type})_")

        if step_type == "action":
            action_name = step.get("action_name") or "(missing action_name)"
            action_category = step.get("action_category") or "(missing category)"
            lines.append(f"- **Action:** {action_name}  _(category: {action_category})_")
        elif step_type == "wait":
            lines.append(f"- **Wait duration:** {step.get('wait_duration', '(not set)')}")
        elif step_type == "if_else":
            lines.append(f"- **Branch condition:** {step.get('branch_condition', '(not set)')}")
            if_true = step.get("if_true_next_step")
            if_false = step.get("if_false_next_step")
            lines.append(f"  - If TRUE → go to step {if_true if if_true is not None else 'END'}")
            lines.append(f"  - If FALSE → go to step {if_false if if_false is not None else 'END'}")
        elif step_type == "go_to":
            target = (step.get("configuration") or {}).get("target_workflow") or "(not set)"
            lines.append(f"- **Go to workflow:** {target}")
        elif step_type == "goal":
            goal_name = (step.get("configuration") or {}).get("goal_name") or "(not set)"
            lines.append(f"- **Goal:** {goal_name}")
        elif step_type == "end":
            lines.append("- **End of branch.**")

        configuration = step.get("configuration") or {}
        if configuration and step_type not in {"go_to", "goal"}:
            lines.append("- **Configuration:**")
            for key, value in configuration.items():
                lines.append(f"  - `{key}`: {value}")
        notes = step.get("notes")
        if notes:
            lines.append(f"- _Note:_ {notes}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
