import asyncio
from types import TracebackType
from typing import Any
from uuid import uuid4

import pytest

from app.infrastructure.observability.metrics import metrics_state
from app.infrastructure.queue.contracts import JobGenerationTask
from app.workers import job_generation_worker as worker


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


def test_generation_worker_success(monkeypatch: pytest.MonkeyPatch) -> None:
    task = JobGenerationTask.create(user_id=uuid4(), job_id=uuid4(), run_type="generate")

    async def fake_acquire_job_lock(**kwargs: Any) -> bool:  # noqa: ARG001
        return True

    async def fake_release_job_lock(**kwargs: Any) -> None:  # noqa: ARG001
        return None

    async def fake_run_generation_pipeline(**kwargs: Any) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(worker, "redis_from_url", lambda *args, **kwargs: _FakeRedisClient())
    monkeypatch.setattr(worker, "acquire_job_lock", fake_acquire_job_lock)
    monkeypatch.setattr(worker, "release_job_lock", fake_release_job_lock)
    monkeypatch.setattr(worker, "SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(worker, "run_generation_pipeline", fake_run_generation_pipeline)

    asyncio.run(worker._run_generation(task=task, is_last_attempt=True))

    snapshot = metrics_state.snapshot()
    assert snapshot["worker_runs_total"] == 1
    assert snapshot["worker_failures_total"] == 0
    assert snapshot["queue_completed_total"] == 1


def test_generation_worker_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    task = JobGenerationTask.create(user_id=uuid4(), job_id=uuid4(), run_type="generate")

    async def fake_acquire_job_lock(**kwargs: Any) -> bool:  # noqa: ARG001
        return True

    async def fake_release_job_lock(**kwargs: Any) -> None:  # noqa: ARG001
        return None

    async def fake_run_generation_pipeline(**kwargs: Any) -> None:  # noqa: ARG001
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(worker, "redis_from_url", lambda *args, **kwargs: _FakeRedisClient())
    monkeypatch.setattr(worker, "acquire_job_lock", fake_acquire_job_lock)
    monkeypatch.setattr(worker, "release_job_lock", fake_release_job_lock)
    monkeypatch.setattr(worker, "SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(worker, "run_generation_pipeline", fake_run_generation_pipeline)

    with pytest.raises(worker.RetryableGenerationError):
        asyncio.run(worker._run_generation(task=task, is_last_attempt=False))

