import json

from app.application.ai.skills.n8n import (
    N8N_SYSTEM_PROMPT,
    example_count,
    get_node_schema,
    get_workflow_example,
    node_count,
    pick_example,
)


def test_n8n_source_pack_loads_with_fallback_or_file() -> None:
    assert node_count() > 0
    assert example_count() > 0
    assert len(N8N_SYSTEM_PROMPT) > 100


def test_get_node_schema_returns_core_node() -> None:
    webhook = get_node_schema("n8n-nodes-base.webhook")
    assert webhook is not None
    assert webhook["type"] == "n8n-nodes-base.webhook"


def test_pick_example_returns_valid_json_workflow() -> None:
    raw = pick_example({"job_markdown": "Need webhook automation with API call"})
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    assert "nodes" in parsed
    assert "connections" in parsed


def test_get_workflow_example_known_category() -> None:
    raw = get_workflow_example("webhook_http")
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
