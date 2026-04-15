from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Any

try:
    import dramatiq
except ImportError:  # pragma: no cover - test/runtime fallback when dramatiq is unavailable
    class _DramatiqFallback:
        @staticmethod
        def actor(*args: Any, **kwargs: Any) -> Any:
            def decorator(fn: Any) -> Any:
                fn.send = lambda *a, **k: None
                return fn

            return decorator

        @staticmethod
        def get_current_message() -> None:
            return None

    dramatiq = _DramatiqFallback()
from redis.asyncio import from_url as redis_from_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.orchestrator_service import run_generation_pipeline
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.observability.metrics import metrics_state
from app.infrastructure.queue.broker import configure_broker
from app.infrastructure.queue.contracts import JobGenerationTask
from app.infrastructure.queue.locks import acquire_job_lock, release_job_lock

settings = get_settings()
configure_broker()


@dataclass(frozen=True)
class RetryableGenerationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _is_last_retry(message_options: dict[str, Any]) -> bool:
    retries = int(message_options.get("retries", 0))
    max_retries = int(message_options.get("max_retries", settings.queue_max_retries))
    return retries >= max_retries


async def _run_generation(*, task: JobGenerationTask, is_last_attempt: bool) -> None:
    started_at = perf_counter()
    redis_client = redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    lock_acquired = await acquire_job_lock(
        redis_client=redis_client,
        job_id=task.job_id,
        idempotency_key=task.idempotency_key,
        namespace="job-generate",
    )
    if not lock_acquired:
        metrics_state.record_worker_run(duration_ms=(perf_counter() - started_at) * 1000, success=True)
        metrics_state.queue_completed()
        await redis_client.aclose()
        return

    worker_success = False
    queue_failed_recorded = False
    async with SessionLocal() as session:
        typed_session: AsyncSession = session
        try:
            await run_generation_pipeline(
                session=typed_session,
                user_id=task.user_id,
                job_id=task.job_id,
                run_type=task.run_type,
                target_artifact=task.target_artifact,
                instruction=task.instruction,
                additional_context=task.additional_context,
            )
            worker_success = True
            metrics_state.queue_completed()
        except Exception as exc:
            if is_last_attempt and not queue_failed_recorded:
                metrics_state.queue_failed()
                queue_failed_recorded = True
            if not is_last_attempt:
                raise RetryableGenerationError(str(exc)) from exc
            raise
        finally:
            metrics_state.record_worker_run(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=worker_success,
            )
            await release_job_lock(
                redis_client=redis_client,
                job_id=task.job_id,
                idempotency_key=task.idempotency_key,
                namespace="job-generate",
            )
            await redis_client.aclose()


@dramatiq.actor(
    queue_name="job-generation",
    max_retries=settings.queue_max_retries,
)
def generate_job_actor(payload: dict[str, Any]) -> None:
    task = JobGenerationTask.from_payload(payload)
    current_message_getter = getattr(dramatiq, "get_current_message", None)
    message = current_message_getter() if callable(current_message_getter) else None
    message_options = message.options if message else {}
    asyncio.run(_run_generation(task=task, is_last_attempt=_is_last_retry(message_options)))
