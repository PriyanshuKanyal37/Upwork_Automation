from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT = REPO_ROOT / "app" / "application" / "ai"
SKILLS_MD_DIR = AI_ROOT / "skills" / "n8n" / "skills_md"
EXAMPLES_DIR = AI_ROOT / "skills" / "n8n" / "examples"
NODE_CATALOG_PATH = AI_ROOT / "data" / "n8n-nodes-technical.json"

SKILL_SOURCES: dict[str, str] = {
    "expression_syntax.md": (
        "https://raw.githubusercontent.com/czlonkowski/n8n-skills/main/"
        "skills/n8n-expression-syntax/SKILL.md"
    ),
    "workflow_patterns.md": (
        "https://raw.githubusercontent.com/czlonkowski/n8n-skills/main/"
        "skills/n8n-workflow-patterns/SKILL.md"
    ),
    "node_configuration.md": (
        "https://raw.githubusercontent.com/czlonkowski/n8n-skills/main/"
        "skills/n8n-node-configuration/SKILL.md"
    ),
    "validation_expert.md": (
        "https://raw.githubusercontent.com/czlonkowski/n8n-skills/main/"
        "skills/n8n-validation-expert/SKILL.md"
    ),
}

NODE_CATALOG_SOURCE = (
    "https://raw.githubusercontent.com/EtienneLescot/n8n-as-code/main/"
    "packages/skills/src/assets/n8n-nodes-technical.json"
)

EXAMPLES_TREE_API = "https://api.github.com/repos/Zie619/n8n-workflows/git/trees/main?recursive=1"


def _download_text(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def _download_bytes(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:
        return response.read()


def _ascii_normalize(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return normalized.encode("ascii", "ignore").decode("ascii").strip() + "\n"


def refresh_skills_md() -> None:
    SKILLS_MD_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, url in SKILL_SOURCES.items():
        raw = _download_text(url)
        cleaned = _ascii_normalize(raw)
        (SKILLS_MD_DIR / file_name).write_text(cleaned, encoding="utf-8")
        print(f"skills_md: updated {file_name} ({len(cleaned)} chars)")


def refresh_node_catalog() -> None:
    NODE_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = _download_bytes(NODE_CATALOG_SOURCE)
    NODE_CATALOG_PATH.write_bytes(payload)
    print(f"node_catalog: updated n8n-nodes-technical.json ({len(payload)} bytes)")


def _valid_workflow_shape(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        nodes = payload.get("nodes")
        connections = payload.get("connections")
        if isinstance(nodes, list) and isinstance(connections, dict):
            return payload
        return None
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                nodes = item.get("nodes")
                connections = item.get("connections")
                if isinstance(nodes, list) and isinstance(connections, dict):
                    return item
    return None


def _build_tags(path: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", path.lower())
    blacklist = {
        "workflows",
        "templates",
        "json",
        "automation",
        "automate",
        "create",
        "triggered",
        "scheduled",
        "send",
        "workflow",
    }
    tags = [token for token in tokens if token not in blacklist and len(token) > 2]
    if "webhook" in path.lower():
        tags = ["webhook", "api"] + tags
    if "schedule" in path.lower() or "scheduled" in path.lower() or "cron" in path.lower():
        tags = ["schedule", "cron"] + tags
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:12]


def refresh_examples(*, max_examples: int) -> None:
    with urlopen(EXAMPLES_TREE_API, timeout=30) as response:
        tree_payload = json.loads(response.read().decode("utf-8"))

    raw_paths = []
    for item in tree_payload.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = str(item.get("path") or "")
        lower = path.lower()
        if not lower.endswith(".json"):
            continue
        if lower.startswith("workflows/") or lower.startswith("templates/"):
            raw_paths.append(path)
    raw_paths.sort(key=lambda p: (0 if p.startswith("workflows/") else 1, p))

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        selected: list[dict[str, Any]] = []
        seen_by_folder: dict[str, int] = {}

        for path in raw_paths:
            if len(selected) >= max_examples:
                break
            folder = path.split("/")[1] if "/" in path else "misc"
            if seen_by_folder.get(folder, 0) >= 2:
                continue

            source_url = f"https://raw.githubusercontent.com/Zie619/n8n-workflows/main/{path}"
            try:
                raw = _download_text(source_url)
            except URLError:
                continue
            if len(raw) > 24000:
                continue

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue

            workflow = _valid_workflow_shape(parsed)
            if workflow is None:
                continue
            nodes = workflow.get("nodes") if isinstance(workflow, dict) else None
            if not isinstance(nodes, list) or not (3 <= len(nodes) <= 8):
                continue
            settings = workflow.get("settings")
            if not isinstance(settings, dict):
                workflow["settings"] = {"executionOrder": "v1"}
            elif not settings.get("executionOrder"):
                settings["executionOrder"] = "v1"

            base = path.split("/")[-1].replace(".json", "").lower()
            slug = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
            if not slug:
                slug = f"example_{len(selected) + 1}"
            file_name = f"{slug}.json"
            file_path = temp_path / file_name
            sequence = 2
            while file_path.exists():
                file_name = f"{slug}_{sequence}.json"
                file_path = temp_path / file_name
                sequence += 1
            file_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            selected.append(
                {
                    "category": slug,
                    "file": file_name,
                    "tags": _build_tags(path),
                }
            )
            seen_by_folder[folder] = seen_by_folder.get(folder, 0) + 1

        if not selected:
            raise RuntimeError("No valid examples were selected from Zie619/n8n-workflows.")

        EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        for old_file in EXAMPLES_DIR.glob("*.json"):
            old_file.unlink()
        for item in selected:
            shutil.copy2(temp_path / item["file"], EXAMPLES_DIR / item["file"])

        index_payload = {
            item["category"]: {"file": item["file"], "tags": item["tags"]}
            for item in selected
        }
        (EXAMPLES_DIR / "index.json").write_text(
            json.dumps(index_payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        print(f"examples: updated {len(selected)} workflow examples")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh n8n source-pack files from upstream repositories.")
    parser.add_argument(
        "--max-examples",
        type=int,
        default=28,
        help="Maximum number of curated workflow examples to pull from Zie619/n8n-workflows.",
    )
    parser.add_argument("--skip-skills", action="store_true", help="Skip refreshing skills_md files.")
    parser.add_argument("--skip-catalog", action="store_true", help="Skip refreshing n8n node catalog JSON.")
    parser.add_argument("--skip-examples", action="store_true", help="Skip refreshing curated examples.")
    args = parser.parse_args()

    if not args.skip_skills:
        refresh_skills_md()
    if not args.skip_catalog:
        refresh_node_catalog()
    if not args.skip_examples:
        refresh_examples(max_examples=max(1, args.max_examples))

    print("source-pack refresh complete")


if __name__ == "__main__":
    main()
