import json
from pathlib import Path


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "app" / "application" / "ai" / "skills" / "n8n" / "examples"
INDEX_PATH = EXAMPLES_DIR / "index.json"


def test_n8n_examples_index_points_to_existing_files() -> None:
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert len(payload) >= 20

    for category, item in payload.items():
        assert isinstance(category, str) and category.strip()
        assert isinstance(item, dict)
        file_name = item.get("file")
        tags = item.get("tags")
        assert isinstance(file_name, str) and file_name.endswith(".json")
        assert (EXAMPLES_DIR / file_name).exists()
        assert isinstance(tags, list)


def test_n8n_examples_have_import_ready_minimum_shape() -> None:
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        workflow = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(workflow, dict), path.name
        nodes = workflow.get("nodes")
        connections = workflow.get("connections")
        settings = workflow.get("settings")
        assert isinstance(nodes, list) and len(nodes) >= 3, path.name
        assert isinstance(connections, dict), path.name
        assert isinstance(settings, dict), path.name
        assert isinstance(settings.get("executionOrder"), str) and settings.get("executionOrder"), path.name
        for node in nodes:
            assert isinstance(node, dict), path.name
            assert isinstance(node.get("id"), str) and node["id"].strip(), path.name
            assert isinstance(node.get("name"), str) and node["name"].strip(), path.name
            assert isinstance(node.get("type"), str) and node["type"].strip(), path.name
            assert isinstance(node.get("typeVersion"), (int, float)), path.name
            position = node.get("position")
            assert isinstance(position, list) and len(position) == 2, path.name
