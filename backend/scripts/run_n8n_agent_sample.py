from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.application.ai.agents.n8n_agent import run_n8n_agent
from app.application.ai.contracts import ProviderName
from app.application.ai.errors import AIException
from app.application.ai.workflow_intent_service import extract_workflow_intent, workflow_intent_to_context
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter
from app.infrastructure.ai.providers.factory import build_provider_adapter
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.session import SessionLocal


def _load_job_from_json(*, jobs_json_path: Path, job_id: str | None) -> dict[str, Any]:
    payload = json.loads(jobs_json_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = [payload]
    elif isinstance(payload, list):
        records = [item for item in payload if isinstance(item, dict)]
    else:
        raise ValueError("jobs.json must be a JSON object or array")

    if not records:
        raise ValueError("No job records found in jobs.json")

    if job_id:
        for item in records:
            if str(item.get("id") or "") == job_id:
                return item
        raise ValueError(f"Job id {job_id} not found in jobs.json")
    return records[0]


async def _load_job_from_db(*, job_id: str) -> dict[str, Any]:
    parsed_id = UUID(job_id)
    async with SessionLocal() as session:
        job = await session.scalar(select(Job).where(Job.id == parsed_id))
        if job is None:
            raise ValueError(f"Job {job_id} not found in database")
        return {
            "id": str(job.id),
            "job_markdown": job.job_markdown,
            "notes_markdown": job.notes_markdown,
            "job_url": job.job_url,
            "platform_detected": job.platform_detected,
            "status": job.status,
        }


def _required_input_columns() -> dict[str, str]:
    return {
        "id": "Optional for selection; required when multiple job records exist.",
        "job_markdown": "Required. Full job description/context.",
        "notes_markdown": "Optional. Extra user notes from intake.",
        "platform_detected": "Optional. Helps sanity-check n8n targeting.",
        "status": "Optional. Usually should be 'ready'.",
    }


def _build_job_context(record: dict[str, Any], *, custom_instruction: str | None) -> dict[str, Any]:
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


async def _run(args: argparse.Namespace) -> int:
    if args.db_job_id:
        record = await _load_job_from_db(job_id=args.db_job_id)
    else:
        if not args.jobs_json:
            raise ValueError("Provide --jobs-json when --db-job-id is not used")
        record = _load_job_from_json(jobs_json_path=Path(args.jobs_json), job_id=args.job_id)

    if args.print_input_columns:
        print("Required input columns for n8n workflow generation:")
        for key, description in _required_input_columns().items():
            print(f"- {key}: {description}")
        print()

    if not str(record.get("job_markdown") or "").strip():
        raise ValueError("job_markdown is required and was empty")

    provider = build_provider_adapter(ProviderName.ANTHROPIC)
    if not isinstance(provider, AnthropicProviderAdapter):
        raise RuntimeError("Anthropic provider adapter is required for n8n agent execution")

    job_context = _build_job_context(record, custom_instruction=args.custom_instruction)

    try:
        artifact = await run_n8n_agent(
            job_context=job_context,
            provider=provider,
            model_name=args.model_name,
            max_iterations=args.max_iterations,
        )
    except AIException as exc:
        print("n8n agent failed:")
        print(f"- code: {exc.code}")
        print(f"- message: {exc.message}")
        if exc.details:
            print(f"- details: {json.dumps(exc.details, indent=2, ensure_ascii=True)}")
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    job_identifier = str(record.get("id") or "job")
    workflow_path = output_dir / f"{job_identifier}_workflow.json"
    trace_path = output_dir / f"{job_identifier}_agent_trace.json"
    plan_path = output_dir / f"{job_identifier}_written_plan.txt"

    workflow_json = artifact.content_json if isinstance(artifact.content_json, dict) else {}
    workflow_path.write_text(json.dumps(workflow_json, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    trace_path.write_text(
        json.dumps(artifact.metadata, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    plan_text = artifact.content_text or ""
    plan_path.write_text(plan_text + ("\n" if plan_text else ""), encoding="utf-8")

    print("n8n agent generation completed")
    print(f"- job_id: {job_identifier}")
    print(f"- model: {args.model_name}")
    print(f"- workflow file: {workflow_path}")
    print(f"- written plan file: {plan_path}")
    print(f"- agent metadata file: {trace_path}")
    print(f"- workflow nodes: {len(workflow_json.get('nodes', []))}")

    usage = artifact.metadata.get("usage", {}) if isinstance(artifact.metadata, dict) else {}
    if isinstance(usage, dict) and usage:
        print("- usage:")
        print(f"  - input_tokens: {usage.get('input_tokens', 0)}")
        print(f"  - output_tokens: {usage.get('output_tokens', 0)}")
        print(f"  - latency_ms: {usage.get('latency_ms', 0)}")
        print(f"  - estimated_cost_usd: {usage.get('estimated_cost_usd', 0)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run n8n agent pipeline sample from jobs JSON or DB.")
    parser.add_argument("--jobs-json", type=str, help="Path to jobs.json export.")
    parser.add_argument("--job-id", type=str, default=None, help="Select one job id from jobs.json.")
    parser.add_argument("--db-job-id", type=str, default=None, help="Fetch one job directly from database by UUID.")
    parser.add_argument("--custom-instruction", type=str, default=None, help="Optional instruction override.")
    parser.add_argument("--model-name", type=str, default="claude-sonnet-4-6", help="Anthropic model name.")
    parser.add_argument("--max-iterations", type=int, default=3, help="Tool-loop iteration cap.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/n8n-agent-sample",
        help="Directory where generated files are written.",
    )
    parser.add_argument(
        "--print-input-columns",
        action="store_true",
        help="Print required input columns before running.",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(_run(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
