from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "n8n-nodes-technical.json"

_HARDCODED_CORE_NODES: dict[str, dict[str, Any]] = {
    "n8n-nodes-base.webhook": {"typeVersion": 2.1, "displayName": "Webhook", "category": "trigger"},
    "n8n-nodes-base.scheduleTrigger": {"typeVersion": 1.2, "displayName": "Schedule Trigger", "category": "trigger"},
    "n8n-nodes-base.httpRequest": {"typeVersion": 4.4, "displayName": "HTTP Request", "category": "core"},
    "n8n-nodes-base.set": {"typeVersion": 3.4, "displayName": "Set", "category": "transform"},
    "n8n-nodes-base.if": {"typeVersion": 2.3, "displayName": "If", "category": "logic"},
    "n8n-nodes-base.code": {"typeVersion": 2, "displayName": "Code", "category": "logic"},
    "n8n-nodes-base.merge": {"typeVersion": 2, "displayName": "Merge", "category": "logic"},
    "n8n-nodes-base.splitInBatches": {"typeVersion": 3, "displayName": "Split In Batches", "category": "logic"},
    "n8n-nodes-base.respondToWebhook": {"typeVersion": 1, "displayName": "Respond to Webhook", "category": "trigger"},
    "n8n-nodes-base.gmail": {"typeVersion": 2, "displayName": "Gmail", "category": "app"},
    "n8n-nodes-base.slack": {"typeVersion": 2, "displayName": "Slack", "category": "app"},
    "n8n-nodes-base.airtable": {"typeVersion": 2, "displayName": "Airtable", "category": "app"},
    "n8n-nodes-base.notion": {"typeVersion": 2, "displayName": "Notion", "category": "app"},
    "n8n-nodes-base.postgres": {"typeVersion": 2.5, "displayName": "Postgres", "category": "database"},
    "n8n-nodes-base.mysql": {"typeVersion": 2.4, "displayName": "MySQL", "category": "database"},
    "n8n-nodes-base.googleSheets": {"typeVersion": 4.3, "displayName": "Google Sheets", "category": "app"},
    "n8n-nodes-base.telegram": {"typeVersion": 1.2, "displayName": "Telegram", "category": "app"},
    "n8n-nodes-base.wait": {"typeVersion": 1.1, "displayName": "Wait", "category": "control"},
    "n8n-nodes-base.errorTrigger": {"typeVersion": 1, "displayName": "Error Trigger", "category": "trigger"},
    "n8n-nodes-base.stickyNote": {"typeVersion": 1, "displayName": "Sticky Note", "category": "utility"},
}

_NODE_CATALOG: dict[str, dict[str, Any]] = {}
_NODES_BY_CATEGORY: dict[str, list[dict[str, Any]]] = {}


def _category_from_node(node: dict[str, Any]) -> str:
    group = node.get("group")
    if isinstance(group, list) and group:
        value = str(group[0]).strip().lower()
        return value or "other"
    category = str(node.get("category") or "").strip().lower()
    return category or "other"


def _normalize_node(node: dict[str, Any]) -> dict[str, Any] | None:
    type_string = str(node.get("type") or node.get("name") or "").strip()
    if not type_string:
        return None

    def _resolve_type_version(value: Any) -> int | float:
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, list):
            numeric_values = [item for item in value if isinstance(item, (int, float))]
            if numeric_values:
                return max(numeric_values)
        return 1

    type_version = _resolve_type_version(node.get("typeVersion"))
    if type_version == 1:
        type_version = _resolve_type_version(node.get("version"))

    schema = node.get("schema")
    schema_properties = []
    schema_credentials = []
    if isinstance(schema, dict):
        if isinstance(schema.get("properties"), list):
            schema_properties = schema["properties"]
        if isinstance(schema.get("credentials"), list):
            schema_credentials = schema["credentials"]

    metadata = node.get("metadata")
    metadata_credentials = []
    if isinstance(metadata, dict) and isinstance(metadata.get("credentials"), list):
        metadata_credentials = metadata["credentials"]

    credentials = node.get("credentials")
    if not isinstance(credentials, list):
        credentials = schema_credentials or metadata_credentials

    properties = node.get("properties")
    if not isinstance(properties, list):
        properties = schema_properties

    normalized = {
        "type": type_string,
        "typeVersion": type_version,
        "displayName": str(node.get("displayName") or type_string),
        "description": str(node.get("description") or ""),
        "credentials": credentials if isinstance(credentials, list) else [],
        "properties": properties if isinstance(properties, list) else [],
        "category": _category_from_node(node),
    }
    return normalized


def _load_from_json_file(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_nodes: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        nodes_payload = payload.get("nodes")
        if isinstance(nodes_payload, list):
            raw_nodes = [n for n in payload["nodes"] if isinstance(n, dict)]
        elif isinstance(nodes_payload, dict):
            raw_nodes = [n for n in nodes_payload.values() if isinstance(n, dict)]
        else:
            for value in payload.values():
                if isinstance(value, dict):
                    raw_nodes.append(value)
                elif isinstance(value, list):
                    raw_nodes.extend([item for item in value if isinstance(item, dict)])
    elif isinstance(payload, list):
        raw_nodes = [n for n in payload if isinstance(n, dict)]

    catalog: dict[str, dict[str, Any]] = {}
    for raw in raw_nodes:
        normalized = _normalize_node(raw)
        if normalized is None:
            continue
        catalog[normalized["type"]] = normalized
    return catalog


def _build_category_index(catalog: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_category: dict[str, list[dict[str, Any]]] = {}
    for node in catalog.values():
        category = str(node.get("category") or "other")
        by_category.setdefault(category, []).append(node)
    for entries in by_category.values():
        entries.sort(key=lambda item: str(item.get("displayName") or item["type"]).lower())
    return by_category


def _initialize() -> None:
    global _NODE_CATALOG, _NODES_BY_CATEGORY

    catalog: dict[str, dict[str, Any]] = {}
    if _DATA_PATH.exists():
        try:
            catalog = _load_from_json_file(_DATA_PATH)
        except Exception:
            catalog = {}
    if not catalog:
        catalog = {
            node_type: {
                "type": node_type,
                "typeVersion": node["typeVersion"],
                "displayName": node["displayName"],
                "description": "",
                "credentials": [],
                "properties": [],
                "category": node["category"],
            }
            for node_type, node in _HARDCODED_CORE_NODES.items()
        }
    _NODE_CATALOG = catalog
    _NODES_BY_CATEGORY = _build_category_index(catalog)


def node_count() -> int:
    return len(_NODE_CATALOG)


def get_node_schema(type_string: str) -> dict[str, Any] | None:
    return _NODE_CATALOG.get(type_string)


def list_nodes_by_category(category: str) -> list[dict[str, Any]]:
    return list(_NODES_BY_CATEGORY.get(category.strip().lower(), []))


def get_top_nodes(limit: int = 20) -> list[dict[str, Any]]:
    top: list[dict[str, Any]] = []
    for node_type in _HARDCODED_CORE_NODES:
        schema = _NODE_CATALOG.get(node_type)
        if schema:
            top.append(schema)
    if len(top) < limit:
        remainder = [node for node_type, node in _NODE_CATALOG.items() if node_type not in _HARDCODED_CORE_NODES]
        remainder.sort(key=lambda item: str(item.get("displayName") or item["type"]).lower())
        top.extend(remainder[: max(0, limit - len(top))])
    return top[:limit]


_initialize()
