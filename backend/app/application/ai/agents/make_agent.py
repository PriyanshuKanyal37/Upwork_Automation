"""Make.com scenario generator agent.

Deliberately simple compared to n8n_agent.py:
- One structured-output Claude call (no multi-turn tool loop).
- Model emits a FLAT module list (because Anthropic structured outputs
  cannot express recursive schemas, and Make.com routers are recursive).
- Python post-processor converts the flat list into the nested Make.com
  blueprint JSON that can be imported via UI or POST /api/v2/scenarios.
- One optional self-correction retry if the flat output fails validation.
  No iteration loop. If the retry fails too, return the payload with an
  error flag in metadata — the caller decides what to do.
"""
from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

from app.application.ai.contracts import (
    ArtifactPayload,
    ArtifactType,
    ProviderGenerateRequest,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.prompt.make_workflow import (
    SYSTEM_PROMPT as MAKE_SYSTEM_PROMPT,
    build_user_prompt,
)
from app.application.ai.validators.make_validator import (
    validate_flat_modules,
    validate_nested_blueprint,
)
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


# JSON schema passed to Anthropic structured outputs.
# Notes on the schema shape:
# - Structured outputs do NOT support recursive schemas, so we flatten.
# - `additionalProperties: false` is required on every object.
# - `required` must list every property (pattern used by Anthropic examples).
# - Numerical/string constraints (minLength, minimum, etc.) are unsupported;
#   we enforce them in validate_flat_modules() instead.
MAKE_FLAT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plan_text": {"type": "string"},
        "blueprint": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "zone": {"type": "string"},
                "instant": {"type": "boolean"},
                "modules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "parent_id": {"type": ["integer", "null"]},
                            "route_index": {"type": ["integer", "null"]},
                            "module": {"type": "string"},
                            "version": {"type": "integer"},
                            "mapper": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "destination": {"type": "string"},
                                    "text": {"type": "string"},
                                    "value": {"type": "string"},
                                    "raw": {"type": "string"},
                                },
                                "additionalProperties": False,
                            },
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "url": {"type": "string"},
                                    "method": {"type": "string"},
                                    "resource": {"type": "string"},
                                    "operation": {"type": "string"},
                                    "record_id": {"type": "string"},
                                    "table": {"type": "string"},
                                    "channel": {"type": "string"},
                                    "message": {"type": "string"},
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "phone": {"type": "string"},
                                    "raw": {"type": "string"},
                                },
                                "additionalProperties": False,
                            },
                            "filter": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "condition": {"type": "string"},
                                    "left": {"type": "string"},
                                    "operator": {"type": "string"},
                                    "right": {"type": "string"},
                                    "raw": {"type": "string"},
                                },
                                "additionalProperties": False,
                            },
                            "position_x": {"type": "integer"},
                            "position_y": {"type": "integer"},
                            "is_router": {"type": "boolean"},
                            "route_count": {"type": "integer"},
                        },
                        "required": [
                            "id",
                            "parent_id",
                            "route_index",
                            "module",
                            "version",
                            "mapper",
                            "parameters",
                            "filter",
                            "position_x",
                            "position_y",
                            "is_router",
                            "route_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["name", "zone", "instant", "modules"],
            "additionalProperties": False,
        },
    },
    "required": ["plan_text", "blueprint"],
    "additionalProperties": False,
}


_DEFAULT_SCENARIO_METADATA: dict[str, Any] = {
    "instant": False,
    "version": 1,
    "scenario": {
        "roundtrips": 1,
        "maxErrors": 3,
        "autoCommit": True,
        "autoCommitTriggerLast": True,
        "sequential": False,
        "confidential": False,
        "dataloss": False,
        "dlq": False,
        "freshVariables": False,
    },
    "designer": {"orphans": []},
    "zone": "us1.make.com",
}


async def run_make_agent(
    *,
    job_context: dict[str, Any],
    provider: AnthropicProviderAdapter,
    model_name: str,
) -> ArtifactPayload:
    """Generate one Make.com scenario blueprint in a single Claude call."""
    user_prompt = build_user_prompt(job_context)

    first_call_started_at = perf_counter()
    flat, plan_text, usage_primary = await _single_call(
        provider=provider,
        model_name=model_name,
        system_prompt=MAKE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    first_call_latency_ms = int((perf_counter() - first_call_started_at) * 1000)

    errors = validate_flat_modules(flat)
    usage_retry: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    retry_latency_ms = 0
    retried = False

    if errors:
        retried = True
        retry_prompt = (
            user_prompt
            + "\n\n---\n\n"
            "Your previous attempt produced the following flat module list:\n"
            f"{json.dumps(flat, separators=(',', ':'))}\n\n"
            "It failed validation with these errors:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nProduce a corrected flat module list. Fix ONLY the listed issues. "
              "Do not change anything else."
        )
        retry_started_at = perf_counter()
        flat_retry, plan_text_retry, usage_retry = await _single_call(
            provider=provider,
            model_name=model_name,
            system_prompt=MAKE_SYSTEM_PROMPT,
            user_prompt=retry_prompt,
        )
        retry_latency_ms = int((perf_counter() - retry_started_at) * 1000)
        errors_retry = validate_flat_modules(flat_retry)
        if not errors_retry:
            flat = flat_retry
            plan_text = plan_text_retry
            errors = []
        else:
            # Accept the retry output but surface the remaining errors.
            flat = flat_retry
            plan_text = plan_text_retry
            errors = errors_retry

    blueprint_json = _flat_to_nested_blueprint(flat)
    nested_errors = validate_nested_blueprint(blueprint_json)

    total_input = int(usage_primary["input_tokens"]) + int(usage_retry["input_tokens"])
    total_output = int(usage_primary["output_tokens"]) + int(usage_retry["output_tokens"])

    return ArtifactPayload(
        artifact_type=ArtifactType.MAKE_WORKFLOW,
        content_text=plan_text or None,
        content_json=blueprint_json,
        metadata={
            "agent_mode": "one_shot_structured",
            "retried": retried,
            "flat_validation_errors": errors,
            "nested_validation_errors": nested_errors,
            "usage": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "latency_ms": first_call_latency_ms + retry_latency_ms,
            },
            "model_name": model_name,
        },
    )


async def _single_call(
    *,
    provider: AnthropicProviderAdapter,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[dict[str, Any], str, dict[str, int]]:
    """Run one structured-output Claude call and return (flat, plan_text, usage)."""
    request = ProviderGenerateRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model_name=model_name,
        temperature=0.2,
        max_output_tokens=8000,
        metadata={"task": "make_workflow"},
    )
    result = await provider.generate(request)

    raw_text = result.output_text or ""
    if not raw_text.strip():
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Empty response from Claude for Make workflow generation",
            details={"model_name": model_name},
        )

    cleaned = _CODE_FENCE_PATTERN.sub("", raw_text).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                raise AIException(
                    code=AIErrorCode.INVALID_OUTPUT,
                    message="Model response was not valid JSON",
                    details={"model_name": model_name, "error": str(exc)},
                ) from exc
        else:
            raise AIException(
                code=AIErrorCode.INVALID_OUTPUT,
                message="Model response was not valid JSON",
                details={"model_name": model_name, "error": str(exc)},
            ) from exc

    if not isinstance(parsed, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Structured-output response was not a JSON object",
            details={"model_name": model_name},
        )

    flat = parsed.get("blueprint")
    plan_text = str(parsed.get("plan_text") or "").strip()
    if not isinstance(flat, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Structured-output response missing `blueprint` object",
            details={"model_name": model_name},
        )

    usage = {
        "input_tokens": int(result.input_tokens or 0),
        "output_tokens": int(result.output_tokens or 0),
    }
    return flat, plan_text, usage


def _flat_to_nested_blueprint(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert the agent's flat module list into a nested Make.com blueprint.

    Algorithm:
    1. Walk `modules` in order, building each module's nested JSON shape.
    2. Top-level modules (parent_id=null) go into `flow`.
    3. Non-top-level modules attach to their parent router's routes[route_index].flow.
    4. A router module is built with a `routes` array of length `route_count`,
       initialized with empty `flow` arrays that children then append to.
    """
    name = str(flat.get("name") or "Untitled scenario")
    zone = str(flat.get("zone") or "us1.make.com")
    instant = bool(flat.get("instant", False))
    flat_modules = flat.get("modules") or []

    # Build each nested module and an index of router children buckets.
    built: dict[int, dict[str, Any]] = {}
    router_children: dict[int, list[list[dict[str, Any]]]] = {}
    top_level: list[dict[str, Any]] = []

    for mod in flat_modules:
        mod_id = int(mod["id"])
        module_type = str(mod["module"])
        version = int(mod["version"])
        is_router = bool(mod.get("is_router"))
        mapper = mod.get("mapper")
        parameters = mod.get("parameters") or {}
        module_filter = mod.get("filter")
        pos_x = int(mod.get("position_x") or 0)
        pos_y = int(mod.get("position_y") or 0)

        nested: dict[str, Any] = {
            "id": mod_id,
            "module": module_type,
            "version": version,
            "parameters": parameters,
            "mapper": None if is_router else (mapper if isinstance(mapper, dict) else {}),
            "metadata": {"designer": {"x": pos_x, "y": pos_y}},
        }
        if module_filter:
            nested["filter"] = module_filter

        if is_router:
            route_count = int(mod.get("route_count") or 1)
            route_count = max(route_count, 1)
            routes: list[dict[str, Any]] = [{"flow": []} for _ in range(route_count)]
            nested["routes"] = routes
            router_children[mod_id] = [r["flow"] for r in routes]

        built[mod_id] = nested

        parent_id = mod.get("parent_id")
        route_index = mod.get("route_index")
        if parent_id is None:
            top_level.append(nested)
        else:
            parent_buckets = router_children.get(int(parent_id))
            if parent_buckets is None:
                # Orphaned child — fall back to appending at top level so the
                # blueprint is still importable and the validator flags it.
                top_level.append(nested)
                continue
            ri = int(route_index or 0)
            if ri < 0 or ri >= len(parent_buckets):
                top_level.append(nested)
                continue
            parent_buckets[ri].append(nested)

    # Assemble final blueprint with scenario metadata defaults.
    metadata = json.loads(json.dumps(_DEFAULT_SCENARIO_METADATA))  # deep copy
    metadata["instant"] = instant
    metadata["zone"] = zone

    return {
        "name": name,
        "flow": top_level,
        "metadata": metadata,
    }
