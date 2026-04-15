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

from app.application.job.service import execute_job_extraction, get_job_for_user, mark_job_failed
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.integrations.firecrawl_client import FirecrawlExtractionError
from app.infrastructure.observability.metrics import metrics_state
from app.infrastructure.queue.broker import configure_broker
from app.infrastructure.queue.contracts import JobExtractionTask
from app.infrastructure.queue.locks import acquire_job_lock, release_job_lock

settings = get_settings()
configure_broker()


@dataclass(frozen=True)
class RetryableExtractionError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _is_last_retry(message_options: dict[str, Any]) -> bool:
    retries = int(message_options.get("retries", 0))
    max_retries = int(message_options.get("max_retries", settings.queue_max_retries))
    return retries >= max_retries


async def _run_extraction(*, task: JobExtractionTask, is_last_attempt: bool) -> None:
    started_at = perf_counter()
    redis_client = redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    lock_acquired = await acquire_job_lock(
        redis_client=redis_client,
        job_id=task.job_id,
        idempotency_key=task.idempotency_key,
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
            await execute_job_extraction(
                session=typed_session,
                user_id=task.user_id,
                job_id=task.job_id,
                retryable_errors=True,
            )
        except FirecrawlExtractionError as exc:
            if not exc.retryable:
                raise
            if not is_last_attempt:
                raise RetryableExtractionError(str(exc)) from exc

            job = await get_job_for_user(session=typed_session, user_id=task.user_id, job_id=task.job_id)
            await mark_job_failed(
                session=typed_session,
                job=job,
                message="Firecrawl failed. Please paste the job text manually.",
            )
            metrics_state.queue_failed()
            queue_failed_recorded = True
            raise RetryableExtractionError(str(exc)) from exc
        except RetryableExtractionError:
            if is_last_attempt and not queue_failed_recorded:
                metrics_state.queue_failed()
                queue_failed_recorded = True
            raise
        except Exception:
            if is_last_attempt and not queue_failed_recorded:
                metrics_state.queue_failed()
                queue_failed_recorded = True
            raise
        else:
            worker_success = True
            metrics_state.queue_completed()
        finally:
            metrics_state.record_worker_run(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=worker_success,
            )
            await release_job_lock(
                redis_client=redis_client,
                job_id=task.job_id,
                idempotency_key=task.idempotency_key,
            )
            await redis_client.aclose()


@dramatiq.actor(
    queue_name="job-extraction",
    max_retries=settings.queue_max_retries,
)
def extract_job_actor(payload: dict[str, Any]) -> None:
    task = JobExtractionTask.from_payload(payload)
    current_message_getter = getattr(dramatiq, "get_current_message", None)
    message = current_message_getter() if callable(current_message_getter) else None
    message_options = message.options if message else {}
    asyncio.run(_run_extraction(task=task, is_last_attempt=_is_last_retry(message_options)))
