from __future__ import annotations

from uuid import UUID

from app.infrastructure.queue.contracts import JobExtractionTask, JobGenerationTask
from app.infrastructure.queue.broker import is_dramatiq_enabled
from app.infrastructure.observability.metrics import metrics_state


def enqueue_job_extraction(*, user_id: UUID, job_id: UUID) -> bool:
    if not is_dramatiq_enabled():
        return False
    from app.workers.job_extraction_worker import extract_job_actor

    task = JobExtractionTask.create(user_id=user_id, job_id=job_id)
    extract_job_actor.send(task.to_payload())
    metrics_state.queue_enqueued()
    return True


def enqueue_job_generation(
    *,
    user_id: UUID,
    job_id: UUID,
    run_type: str,
    target_artifact: str | None = None,
    instruction: str | None = None,
    additional_context: dict[str, object] | None = None,
) -> bool:
    if not is_dramatiq_enabled():
        return False
    from app.workers.job_generation_worker import generate_job_actor

    task = JobGenerationTask.create(
        user_id=user_id,
        job_id=job_id,
        run_type=run_type,
        target_artifact=target_artifact,
        instruction=instruction,
        additional_context=additional_context,
    )
    generate_job_actor.send(task.to_payload())
    metrics_state.queue_enqueued()
    return True
