from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.application.ai.agents import n8n_agent
from app.application.ai.agents.n8n_agent import run_n8n_agent
from app.application.ai.contracts import ArtifactPayload
from app.application.ai.errors import AIException
from app.application.ai.workflow_intent_service import extract_workflow_intent, workflow_intent_to_context
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter


def _load_job_from_json(*, jobs_json_path: Path, job_id: str | None) -> dict[str, Any]:
    payload = json.loads(jobs_json_path.read_text(encoding="utf-8"))
    records = payload if isinstance(payload, list) else [payload]
    if not records:
        raise ValueError("No records found")
    if job_id:
        for record in records:
            if str(record.get("id") or "") == job_id:
                return record
        raise ValueError(f"Job id {job_id} not found")
    return records[0]


def _build_job_context(record: dict[str, Any], custom_instruction: str) -> dict[str, Any]:
    intent_execution = extract_workflow_intent(
        job_markdown=str(record.get("job_markdown") or ""),
        notes_markdown=record.get("notes_markdown"),
        custom_instruction=custom_instruction,
    )
    extra_context = workflow_intent_to_context(intent_execution.intent)
    return {
        "job_markdown": record.get("job_markdown"),
        "notes_markdown": record.get("notes_markdown"),
        "profile_context": None,
        "custom_instruction": custom_instruction,
        "extra_context": extra_context,
    }


def _write_outputs(*, artifact: ArtifactPayload, job_id: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = output_dir / f"{job_id}_workflow.json"
    plan_path = output_dir / f"{job_id}_written_plan.txt"
    trace_path = output_dir / f"{job_id}_agent_trace.json"
    workflow_json = artifact.content_json if isinstance(artifact.content_json, dict) else {}
    workflow_path.write_text(json.dumps(workflow_json, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    plan_path.write_text((artifact.content_text or "") + "\n", encoding="utf-8")
    trace_path.write_text(
        json.dumps(artifact.metadata if isinstance(artifact.metadata, dict) else {}, indent=2, ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"workflow_file={workflow_path}")
    print(f"written_plan_file={plan_path}")
    print(f"agent_trace_file={trace_path}")
    usage = artifact.metadata.get("usage", {}) if isinstance(artifact.metadata, dict) else {}
    if isinstance(usage, dict):
        print(f"usage_input_tokens={usage.get('input_tokens', 0)}")
        print(f"usage_output_tokens={usage.get('output_tokens', 0)}")
        print(f"usage_latency_ms={usage.get('latency_ms', 0)}")
        print(f"usage_estimated_cost_usd={usage.get('estimated_cost_usd', 0)}")


async def _run(args: argparse.Namespace) -> int:
    record = _load_job_from_json(jobs_json_path=Path(args.jobs_json), job_id=args.job_id)
    job_id = str(record.get("id") or "job")

    custom_instruction = (
        "Generate a demo workflow where node count is chosen by job complexity. "
        "Simple jobs: 5-8 nodes, medium jobs: 8-14 nodes, complex jobs: 12-20 nodes. "
        "Prefer fewer nodes when possible. Avoid verbose comments in code nodes. "
        "Keep JSON concise and importable."
    )
    job_context = _build_job_context(record, custom_instruction=custom_instruction)

    # Test-only runtime overrides (no main pipeline changes).
    n8n_agent._MAX_OUTPUT_TOKENS = args.max_output_tokens
    if args.disable_token_precheck:
        async def _noop_precheck(*, provider: AnthropicProviderAdapter, request: Any, usage_totals: dict[str, Any], trace_entry: dict[str, Any]) -> None:
            trace_entry["precheck_status"] = "skipped"
            return
        n8n_agent._token_precheck_or_raise = _noop_precheck  # type: ignore[assignment]

    provider = AnthropicProviderAdapter(max_retries=args.provider_retries)

    try:
        artifact = await run_n8n_agent(
            job_context=job_context,
            provider=provider,
            model_name=args.model_name,
            max_iterations=args.max_iterations,
        )
    except AIException as exc:
        print("n8n_compact_test_failed")
        print(f"code={exc.code}")
        print(f"message={exc.message}")
        if exc.details:
            print(f"details={json.dumps(exc.details, ensure_ascii=True)}")
        return 2

    _write_outputs(
        artifact=artifact,
        job_id=job_id,
        output_dir=Path(args.output_dir),
    )
    print("n8n_compact_test_success=true")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="One-off compact n8n agent test runner (does not change main pipeline).")
    parser.add_argument("--jobs-json", required=True, type=str)
    parser.add_argument("--job-id", default=None, type=str)
    parser.add_argument("--output-dir", default="output/n8n-agent-sample", type=str)
    parser.add_argument("--model-name", default="claude-sonnet-4-6", type=str)
    parser.add_argument("--max-iterations", default=2, type=int)
    parser.add_argument("--max-output-tokens", default=3200, type=int)
    parser.add_argument("--provider-retries", default=1, type=int, help="1 means one retry (2 attempts total).")
    parser.add_argument("--disable-token-precheck", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()

