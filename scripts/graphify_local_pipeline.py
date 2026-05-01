import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.benchmark import print_benchmark, run_benchmark
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.detect import detect, save_manifest
from graphify.export import to_html, to_json
from graphify.extract import collect_files, extract
from graphify.report import generate


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "into",
    "file",
    "code",
    "backend",
    "frontend",
    "module",
    "service",
    "config",
    "index",
    "main",
    "test",
    "spec",
}


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "node"


def safe_text_read(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc, errors="ignore")
        except Exception:
            continue
    return ""


def top_terms(text: str, n: int = 6) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
    words = [w for w in words if w not in STOPWORDS]
    return [w for w, _ in Counter(words).most_common(n)]


def semantic_from_docs_and_images(
    root: Path, detect_json: dict, ast_nodes: list[dict]
) -> dict:
    code_nodes = [n for n in ast_nodes if n.get("file_type") == "code"]
    code_by_label = {}
    for n in code_nodes:
        label = (n.get("label") or "").strip()
        if len(label) >= 3:
            code_by_label.setdefault(label.lower(), n["id"])

    semantic_nodes: list[dict] = []
    semantic_edges: list[dict] = []

    doc_files = detect_json.get("files", {}).get("document", [])
    for f in doc_files:
        p = Path(f)
        rel = str(p.as_posix())
        text = safe_text_read(p)
        doc_id = f"doc_{slug(rel)}"
        doc_label = p.name
        semantic_nodes.append(
            {
                "id": doc_id,
                "label": doc_label,
                "file_type": "document",
                "source_file": rel,
                "source_location": "L1",
                "source_url": None,
                "captured_at": None,
                "author": None,
                "contributor": None,
            }
        )

        for h in re.findall(r"(?m)^#{1,3}\s+(.+?)\s*$", text)[:12]:
            h_id = f"{doc_id}_heading_{slug(h)}"
            semantic_nodes.append(
                {
                    "id": h_id,
                    "label": h.strip(),
                    "file_type": "document",
                    "source_file": rel,
                    "source_location": None,
                    "source_url": None,
                    "captured_at": None,
                    "author": None,
                    "contributor": None,
                }
            )
            semantic_edges.append(
                {
                    "source": doc_id,
                    "target": h_id,
                    "relation": "references",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                    "source_file": rel,
                    "source_location": None,
                    "weight": 1.0,
                }
            )

        low = text.lower()
        mentions = 0
        for label_low, code_id in code_by_label.items():
            if len(label_low) >= 4 and re.search(rf"\b{re.escape(label_low)}\b", low):
                semantic_edges.append(
                    {
                        "source": doc_id,
                        "target": code_id,
                        "relation": "references",
                        "confidence": "EXTRACTED",
                        "confidence_score": 1.0,
                        "source_file": rel,
                        "source_location": None,
                        "weight": 1.0,
                    }
                )
                mentions += 1
            if mentions >= 25:
                break

        rationale_hits = []
        for line in text.splitlines():
            line_s = line.strip()
            if len(line_s) < 30:
                continue
            if re.search(
                r"\b(because|so that|trade.?off|decision|why|to avoid|to ensure|rationale)\b",
                line_s.lower(),
            ):
                rationale_hits.append(line_s)
            if len(rationale_hits) >= 5:
                break

        for idx, rline in enumerate(rationale_hits, start=1):
            rid = f"{doc_id}_rationale_{idx}"
            semantic_nodes.append(
                {
                    "id": rid,
                    "label": rline[:120],
                    "file_type": "document",
                    "source_file": rel,
                    "source_location": None,
                    "source_url": None,
                    "captured_at": None,
                    "author": None,
                    "contributor": None,
                }
            )
            semantic_edges.append(
                {
                    "source": rid,
                    "target": doc_id,
                    "relation": "rationale_for",
                    "confidence": "INFERRED",
                    "confidence_score": 0.8,
                    "source_file": rel,
                    "source_location": None,
                    "weight": 1.0,
                }
            )

        terms = top_terms(text, 4)
        for term in terms:
            for label_low, code_id in code_by_label.items():
                if term in label_low and len(term) >= 4:
                    semantic_edges.append(
                        {
                            "source": doc_id,
                            "target": code_id,
                            "relation": "conceptually_related_to",
                            "confidence": "INFERRED",
                            "confidence_score": 0.65,
                            "source_file": rel,
                            "source_location": None,
                            "weight": 0.8,
                        }
                    )
                    break

    for f in detect_json.get("files", {}).get("image", []):
        p = Path(f)
        rel = str(p.as_posix())
        image_id = f"img_{slug(rel)}"
        semantic_nodes.append(
            {
                "id": image_id,
                "label": p.name,
                "file_type": "image",
                "source_file": rel,
                "source_location": None,
                "source_url": None,
                "captured_at": None,
                "author": None,
                "contributor": None,
            }
        )
        key = slug(p.stem).replace("_", " ")
        linked = 0
        for label_low, code_id in code_by_label.items():
            if any(tok in label_low for tok in key.split() if len(tok) >= 4):
                semantic_edges.append(
                    {
                        "source": image_id,
                        "target": code_id,
                        "relation": "conceptually_related_to",
                        "confidence": "AMBIGUOUS",
                        "confidence_score": 0.3,
                        "source_file": rel,
                        "source_location": None,
                        "weight": 0.6,
                    }
                )
                linked += 1
            if linked >= 8:
                break

    seen_nodes = set()
    dedup_nodes = []
    for n in semantic_nodes:
        nid = n.get("id")
        if nid and nid not in seen_nodes:
            dedup_nodes.append(n)
            seen_nodes.add(nid)

    seen_edges = set()
    dedup_edges = []
    for e in semantic_edges:
        key = (e["source"], e["target"], e["relation"], e.get("source_file"))
        if key not in seen_edges:
            dedup_edges.append(e)
            seen_edges.add(key)

    return {
        "nodes": dedup_nodes,
        "edges": dedup_edges,
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }


def auto_labels(G, communities: dict[int, list[str]]) -> dict[int, str]:
    labels: dict[int, str] = {}
    for cid, nids in communities.items():
        bag = []
        for nid in nids[:120]:
            l = (G.nodes[nid].get("label") or "").lower()
            l = re.sub(r"\.[a-z0-9]+$", "", l)
            bag.extend([w for w in re.findall(r"[a-z][a-z0-9_]{2,}", l) if w not in STOPWORDS])
        top = [w for w, _ in Counter(bag).most_common(2)]
        if top:
            labels[cid] = " ".join(t.capitalize() for t in top)
        else:
            labels[cid] = f"Community {cid}"
    return labels


def run_pipeline(target: Path, out_dir: Path) -> dict:
    target = target.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    detect_json = detect(target)
    code_files: list[Path] = []
    for f in detect_json.get("files", {}).get("code", []):
        p = Path(f)
        code_files.extend(collect_files(p) if p.is_dir() else [p])

    if code_files:
        ast = extract(code_files)
    else:
        ast = {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}

    semantic = semantic_from_docs_and_images(target, detect_json, ast["nodes"])

    seen = {n["id"] for n in ast["nodes"]}
    merged_nodes = list(ast["nodes"])
    for n in semantic["nodes"]:
        if n["id"] not in seen:
            merged_nodes.append(n)
            seen.add(n["id"])
    merged_edges = list(ast["edges"]) + list(semantic["edges"])
    extraction = {
        "nodes": merged_nodes,
        "edges": merged_edges,
        "hyperedges": semantic.get("hyperedges", []),
        "input_tokens": 0,
        "output_tokens": 0,
    }

    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = auto_labels(G, communities)
    questions = suggest_questions(G, communities, labels)
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detect_json,
        {"input": 0, "output": 0},
        str(target),
        suggested_questions=questions,
    )

    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(out_dir / "graph.json"))
    if G.number_of_nodes() <= 5000:
        to_html(G, communities, str(out_dir / "graph.html"), community_labels=labels or None)

    if detect_json.get("total_words", 0) > 5000:
        try:
            result = run_benchmark(str(out_dir / "graph.json"), corpus_words=detect_json.get("total_words"))
            print_benchmark(result)
        except Exception:
            pass

    cost = {"runs": [], "total_input_tokens": 0, "total_output_tokens": 0}
    (out_dir / "cost.json").write_text(json.dumps(cost, indent=2), encoding="utf-8")
    save_manifest(detect_json.get("files", {}))

    return {
        "target": str(target),
        "out_dir": str(out_dir.resolve()),
        "detect": detect_json,
        "extraction": extraction,
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
        "graph_nodes": G.number_of_nodes(),
        "graph_edges": G.number_of_edges(),
        "communities": len(communities),
    }


def merge_extractions(extractions: Iterable[dict]) -> dict:
    all_nodes = []
    all_edges = []
    all_hyperedges = []
    seen = set()
    for ex in extractions:
        for n in ex.get("nodes", []):
            if n["id"] not in seen:
                all_nodes.append(n)
                seen.add(n["id"])
        all_edges.extend(ex.get("edges", []))
        all_hyperedges.extend(ex.get("hyperedges", []))
    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "hyperedges": all_hyperedges,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--out-backend", default="backend/graphify-out")
    ap.add_argument("--out-frontend", default="frontend/graphify-out")
    ap.add_argument("--out-combined", default="graphify-out")
    args = ap.parse_args()

    backend_res = run_pipeline(Path(args.backend), Path(args.out_backend))
    frontend_res = run_pipeline(Path(args.frontend), Path(args.out_frontend))

    combined_out = Path(args.out_combined).resolve()
    combined_out.mkdir(parents=True, exist_ok=True)
    combined_extract = merge_extractions([backend_res["extraction"], frontend_res["extraction"]])
    combined_detect = {
        "total_files": backend_res["detect"].get("total_files", 0)
        + frontend_res["detect"].get("total_files", 0),
        "total_words": backend_res["detect"].get("total_words", 0)
        + frontend_res["detect"].get("total_words", 0),
        "files": {
            "code": backend_res["detect"].get("files", {}).get("code", [])
            + frontend_res["detect"].get("files", {}).get("code", []),
            "document": backend_res["detect"].get("files", {}).get("document", [])
            + frontend_res["detect"].get("files", {}).get("document", []),
            "paper": [],
            "image": backend_res["detect"].get("files", {}).get("image", [])
            + frontend_res["detect"].get("files", {}).get("image", []),
            "video": [],
        },
        "skipped_sensitive": backend_res["detect"].get("skipped_sensitive", [])
        + frontend_res["detect"].get("skipped_sensitive", []),
    }

    G = build_from_json(combined_extract)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = auto_labels(G, communities)
    questions = suggest_questions(G, communities, labels)

    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        combined_detect,
        {"input": 0, "output": 0},
        str(Path(".").resolve()),
        suggested_questions=questions,
    )
    (combined_out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(combined_out / "graph.json"))
    if G.number_of_nodes() <= 5000:
        to_html(G, communities, str(combined_out / "graph.html"), community_labels=labels or None)

    if combined_detect["total_words"] > 5000:
        try:
            result = run_benchmark(str(combined_out / "graph.json"), corpus_words=combined_detect["total_words"])
            print_benchmark(result)
        except Exception:
            pass

    (combined_out / "cost.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "date": datetime.now(timezone.utc).isoformat(),
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "files": combined_detect["total_files"],
                    }
                ],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = {
        "backend": {
            "out_dir": backend_res["out_dir"],
            "nodes": backend_res["graph_nodes"],
            "edges": backend_res["graph_edges"],
            "communities": backend_res["communities"],
        },
        "frontend": {
            "out_dir": frontend_res["out_dir"],
            "nodes": frontend_res["graph_nodes"],
            "edges": frontend_res["graph_edges"],
            "communities": frontend_res["communities"],
        },
        "combined": {
            "out_dir": str(combined_out),
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "communities": len(communities),
            "questions": questions,
            "gods": gods,
            "surprises": surprises,
        },
    }
    Path("graphify_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
