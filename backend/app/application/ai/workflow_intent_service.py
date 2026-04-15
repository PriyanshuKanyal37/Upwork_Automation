from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.application.ai.contracts import WorkflowIntent


class WorkflowIntentExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: WorkflowIntent
    source: str = Field(default="rules", min_length=1, max_length=32)


_APP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gmail": ("gmail", "google mail"),
    "google_sheets": ("google sheets", "gsheet", "sheet"),
    "slack": ("slack",),
    "notion": ("notion",),
    "airtable": ("airtable",),
    "hubspot": ("hubspot",),
    "salesforce": ("salesforce",),
    "postgres": ("postgres", "postgresql"),
    "mysql": ("mysql",),
    "stripe": ("stripe",),
    "shopify": ("shopify",),
    "telegram": ("telegram",),
    "discord": ("discord",),
}

_OPERATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "create_record": ("create", "insert", "add"),
    "update_record": ("update", "upsert", "modify"),
    "send_notification": ("notify", "notification", "alert", "message"),
    "fetch_api": ("api", "http request", "fetch", "call endpoint"),
    "sync_data": ("sync", "mirror", "replicate"),
    "enrich_data": ("enrich", "transform", "clean"),
    "route_logic": ("if ", "condition", "branch", "routing"),
}

_SCHEDULE_PATTERNS = (
    r"\bdaily\b",
    r"\bweekly\b",
    r"\bmonthly\b",
    r"\bevery\s+\d+\s+(minute|minutes|hour|hours|day|days)\b",
    r"\bcron\b",
    r"\bschedule\b",
)


def _find_apps(text: str) -> list[str]:
    found: list[str] = []
    for app, keywords in _APP_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            found.append(app)
    return found


def _find_operations(text: str) -> list[str]:
    operations: list[str] = []
    for operation, keywords in _OPERATION_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            operations.append(operation)
    return operations


def _extract_schedule_hint(text: str) -> str | None:
    for pattern in _SCHEDULE_PATTERNS:
        matched = re.search(pattern, text)
        if matched:
            return matched.group(0)
    return None


def _trigger_type(text: str, schedule_hint: str | None) -> str:
    if "webhook" in text or "callback" in text:
        return "webhook"
    if schedule_hint is not None:
        return "schedule"
    if "email" in text or "inbox" in text:
        return "email"
    if "manual" in text:
        return "manual"
    return "unknown"


def _reliability_level(text: str) -> str:
    high_keywords = ("retry", "idempotent", "production", "failover", "error handling", "monitor")
    medium_keywords = ("reliable", "stable", "robust", "handle errors")
    if any(keyword in text for keyword in high_keywords):
        return "high"
    if any(keyword in text for keyword in medium_keywords):
        return "medium"
    return "low"


def _confidence(trigger_type: str, apps: list[str], operations: list[str]) -> str:
    score = 0
    if trigger_type != "unknown":
        score += 1
    if apps:
        score += 1
    if operations:
        score += 1
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


def _reasoning(trigger_type: str, apps: list[str], operations: list[str]) -> str:
    app_part = ", ".join(apps[:3]) if apps else "no explicit app"
    operation_part = ", ".join(operations[:3]) if operations else "generic automation steps"
    return (
        f"Detected trigger '{trigger_type}' with {app_part}; inferred operations: {operation_part}."
    )


def extract_workflow_intent(
    *,
    job_markdown: str,
    notes_markdown: str | None = None,
    custom_instruction: str | None = None,
) -> WorkflowIntentExecution:
    text = " ".join(
        segment.strip()
        for segment in (job_markdown, notes_markdown or "", custom_instruction or "")
        if segment and segment.strip()
    ).lower()

    schedule_hint = _extract_schedule_hint(text)
    trigger = _trigger_type(text, schedule_hint)
    apps = _find_apps(text)
    operations = _find_operations(text)
    reliability = _reliability_level(text)
    confidence = _confidence(trigger, apps, operations)

    # v1 heuristic source/target split:
    # first app is source, rest are targets when available.
    source_apps: list[str] = apps[:1]
    target_apps: list[str] = apps[1:]

    intent = WorkflowIntent(
        trigger_type=trigger,  # type: ignore[arg-type]
        source_apps=source_apps,
        target_apps=target_apps,
        operations=operations,
        schedule_hint=schedule_hint,
        reliability_level=reliability,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        reasoning=_reasoning(trigger, apps, operations),
    )
    return WorkflowIntentExecution(intent=intent, source="rules")


def workflow_intent_to_context(intent: WorkflowIntent) -> dict[str, Any]:
    return {
        "workflow_intent_trigger_type": intent.trigger_type,
        "workflow_intent_source_apps": ", ".join(intent.source_apps) if intent.source_apps else "None",
        "workflow_intent_target_apps": ", ".join(intent.target_apps) if intent.target_apps else "None",
        "workflow_intent_operations": ", ".join(intent.operations) if intent.operations else "None",
        "workflow_intent_schedule_hint": intent.schedule_hint or "None",
        "workflow_intent_reliability_level": intent.reliability_level,
        "workflow_intent_confidence": intent.confidence,
        "workflow_intent_reasoning": intent.reasoning,
    }
