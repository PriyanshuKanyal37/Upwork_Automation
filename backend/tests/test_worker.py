import asyncio
from dataclasses import dataclass
from types import TracebackType
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.infrastructure.integrations.firecrawl_client import FirecrawlExtractionError
from app.infrastructure.observability.metrics import metrics_state
from app.infrastructure.queue.contracts import JobExtractionTask
from app.workers import job_extraction_worker as worker


class _FakeRedisClient:
    async def aclose(self) -> None:
        return None


class _FakeSessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


@dataclass
class _FakeJob:
    id: UUID
    user_id: UUID
    status: str = "processing"


@pytest.mark.parametrize("is_last_attempt", [False, True])
def test_worker_run_extraction_success(monkeypatch: pytest.MonkeyPatch, is_last_attempt: bool) -> None:
    task = JobExtractionTask.create(user_id=uuid4(), job_id=uuid4())

    async def fake_acquire_job_lock(**kwargs: Any) -> bool:  # noqa: ARG001
        return True

    async def fake_release_job_lock(**kwargs: Any) -> None:  # noqa: ARG001
        return None

    async def fake_execute_job_extraction(**kwargs: Any) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(worker, "redis_from_url", lambda *args, **kwargs: _FakeRedisClient())
    monkeypatch.setattr(worker, "acquire_job_lock", fake_acquire_job_lock)
    monkeypatch.setattr(worker, "release_job_lock", fake_release_job_lock)
    monkeypatch.setattr(worker, "SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(worker, "execute_job_extraction", fake_execute_job_extraction)

    asyncio.run(worker._run_extraction(task=task, is_last_attempt=is_last_attempt))

    snapshot = metrics_state.snapshot()
    assert snapshot["worker_runs_total"] == 1
    assert snapshot["worker_failures_total"] == 0
    assert snapshot["queue_completed_total"] == 1
    assert snapshot["queue_failed_total"] == 0


def test_worker_final_retry_records_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    task = JobExtractionTask.create(user_id=uuid4(), job_id=uuid4())
    fake_job = _FakeJob(id=task.job_id, user_id=task.user_id)

    async def fake_acquire_job_lock(**kwargs: Any) -> bool:  # noqa: ARG001
        return True

    async def fake_release_job_lock(**kwargs: Any) -> None:  # noqa: ARG001
        return None

    async def fake_execute_job_extraction(**kwargs: Any) -> None:  # noqa: ARG001
        raise FirecrawlExtractionError(message="transient", code="firecrawl_timeout", retryable=True)

    async def fake_get_job_for_user(**kwargs: Any) -> _FakeJob:  # noqa: ARG001
        return fake_job

    async def fake_mark_job_failed(**kwargs: Any) -> _FakeJob:  # noqa: ARG001
        return fake_job

    monkeypatch.setattr(worker, "redis_from_url", lambda *args, **kwargs: _FakeRedisClient())
    monkeypatch.setattr(worker, "acquire_job_lock", fake_acquire_job_lock)
    monkeypatch.setattr(worker, "release_job_lock", fake_release_job_lock)
    monkeypatch.setattr(worker, "SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(worker, "execute_job_extraction", fake_execute_job_extraction)
    monkeypatch.setattr(worker, "get_job_for_user", fake_get_job_for_user)
    monkeypatch.setattr(worker, "mark_job_failed", fake_mark_job_failed)

    with pytest.raises(worker.RetryableExtractionError):
        asyncio.run(worker._run_extraction(task=task, is_last_attempt=True))

    snapshot = metrics_state.snapshot()
    assert snapshot["worker_runs_total"] == 1
    assert snapshot["worker_failures_total"] == 1
    assert snapshot["queue_failed_total"] == 1
