import asyncio
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.application.ai.run_tracking_service import (
    append_artifact_version,
    create_generation_run,
    mark_generation_run_failed,
    mark_generation_run_success,
)
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import SessionLocal


async def _seed_user_and_job() -> tuple[User, Job]:
    async with SessionLocal() as session:
        user = User(
            display_name="AI Run User",
            email=f"ai-run-{uuid4().hex[:10]}@example.com",
            password_hash="hash",
        )
        session.add(user)
        await session.flush()

        job = Job(
            user_id=user.id,
            job_url=f"https://www.upwork.com/jobs/~{uuid4().hex}",
            status="ready",
        )
        session.add(job)
        await session.commit()
        await session.refresh(user)
        await session.refresh(job)
        return user, job


def test_run_tracking_success_updates_usage_summary() -> None:
    user, job = asyncio.run(_seed_user_and_job())

    async def _run() -> None:
        async with SessionLocal() as session:
            run = await create_generation_run(
                session=session,
                job_id=job.id,
                user_id=user.id,
                run_type="generate",
                artifact_type="proposal",
                provider="openai",
                model_name="gpt-5.4-mini",
                routing_mode="fixed_per_artifact",
                prompt_version="proposal_v1",
                prompt_hash="abc123",
            )
            await mark_generation_run_success(
                session=session,
                run_id=run.id,
                input_tokens=100,
                output_tokens=50,
                estimated_cost_usd=Decimal("0.012300"),
                latency_ms=400,
                retry_count=1,
            )

            output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job.id))
            assert output is not None
            assert output.ai_usage_summary_json["total_calls"] == 1
            assert output.ai_usage_summary_json["successful_calls"] == 1
            assert output.ai_usage_summary_json["failed_calls"] == 0
            assert output.ai_usage_summary_json["total_input_tokens"] == 100
            assert output.ai_usage_summary_json["total_output_tokens"] == 50
            assert output.ai_usage_summary_json["total_estimated_cost_usd"] > 0

    asyncio.run(_run())


def test_run_tracking_failure_and_version_append() -> None:
    user, job = asyncio.run(_seed_user_and_job())

    async def _run() -> None:
        async with SessionLocal() as session:
            run = await create_generation_run(
                session=session,
                job_id=job.id,
                user_id=user.id,
                run_type="regenerate",
                artifact_type="proposal",
            )
            await mark_generation_run_failed(
                session=session,
                run_id=run.id,
                failure_code="provider_unavailable",
                failure_message="Primary and fallback failed",
                retry_count=2,
            )
            first = await append_artifact_version(
                session=session,
                job_id=job.id,
                artifact_type="proposal",
                content_text="Version 1",
                generation_run_id=run.id,
            )
            second = await append_artifact_version(
                session=session,
                job_id=job.id,
                artifact_type="proposal",
                content_text="Version 2",
                generation_run_id=run.id,
            )

            output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job.id))
            assert output is not None
            assert output.ai_usage_summary_json["failed_calls"] == 1
            assert first["version_number"] == 1
            assert second["version_number"] == 2
            assert len(output.artifact_versions_json) == 2

    asyncio.run(_run())

