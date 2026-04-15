"""n8n source-pack loaders and prompt helpers."""

from app.application.ai.skills.n8n.example_picker import example_count, get_workflow_example, pick_example
from app.application.ai.skills.n8n.node_catalog import (
    get_node_schema,
    get_top_nodes,
    list_nodes_by_category,
    node_count,
)
from app.application.ai.skills.n8n.skill_loader import N8N_SYSTEM_PROMPT

__all__ = [
    "N8N_SYSTEM_PROMPT",
    "example_count",
    "get_node_schema",
    "get_top_nodes",
    "get_workflow_example",
    "list_nodes_by_category",
    "node_count",
    "pick_example",
]

