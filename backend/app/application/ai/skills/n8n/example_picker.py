from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
_INDEX_PATH = _EXAMPLES_DIR / "index.json"

_EXAMPLE_INDEX: dict[str, dict[str, Any]] = {}
_EXAMPLE_CACHE: dict[str, str] = {}

_FALLBACK_EXAMPLE = json.dumps(
    {
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2.1,
                "position": [260, 280],
                "parameters": {},
            },
            {
                "id": "2",
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.4,
                "position": [520, 280],
                "parameters": {"url": "https://example.com"},
            },
            {
                "id": "3",
                "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [780, 280],
                "parameters": {"respondWith": "allIncomingItems"},
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]},
            "HTTP Request": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
        },
    },
    indent=2,
)


def _load_examples() -> None:
    global _EXAMPLE_INDEX, _EXAMPLE_CACHE
    index: dict[str, dict[str, Any]] = {}
    cache: dict[str, str] = {}
    if _INDEX_PATH.exists():
        try:
            payload = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                index = {
                    str(k): v for k, v in payload.items()
                    if isinstance(v, dict) and isinstance(v.get("file"), str)
                }
        except Exception:
            index = {}

    for category, entry in index.items():
        file_name = str(entry.get("file") or "").strip()
        if not file_name:
            continue
        path = _EXAMPLES_DIR / file_name
        if not path.exists():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            cache[category] = json.dumps(parsed, indent=2)
        except Exception:
            continue
    _EXAMPLE_INDEX = index
    _EXAMPLE_CACHE = cache


def example_count() -> int:
    return len(_EXAMPLE_CACHE)


def get_workflow_example(category: str) -> str:
    value = _EXAMPLE_CACHE.get(category.strip().lower())
    return value if value else _FALLBACK_EXAMPLE


def _score_category(category: str, text: str) -> int:
    entry = _EXAMPLE_INDEX.get(category, {})
    tags = entry.get("tags")
    if not isinstance(tags, list):
        return 0
    score = 0
    for tag in tags:
        token = str(tag).strip().lower()
        if token and token in text:
            score += 1
    return score


def pick_example(job_context: dict[str, Any]) -> str:
    haystack = " ".join(
        str(job_context.get(key) or "")
        for key in ("job_markdown", "notes_markdown", "custom_instruction", "profile_context")
    ).lower()
    if not _EXAMPLE_CACHE:
        return _FALLBACK_EXAMPLE
    best_category = None
    best_score = -1
    for category in _EXAMPLE_CACHE:
        score = _score_category(category, haystack)
        if score > best_score:
            best_score = score
            best_category = category
    if best_category is None:
        return _FALLBACK_EXAMPLE
    return _EXAMPLE_CACHE[best_category]


_load_examples()

