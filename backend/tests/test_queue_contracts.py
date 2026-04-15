from uuid import uuid4

from app.infrastructure.queue.contracts import JobExtractionTask, JobGenerationTask


def test_job_extraction_task_payload_roundtrip() -> None:
    user_id = uuid4()
    job_id = uuid4()

    task = JobExtractionTask.create(user_id=user_id, job_id=job_id)
    payload = task.to_payload()
    restored = JobExtractionTask.from_payload(payload)

    assert restored.user_id == user_id
    assert restored.job_id == job_id
    assert restored.idempotency_key == task.idempotency_key
    assert restored.requested_at == task.requested_at


def test_job_generation_task_payload_roundtrip() -> None:
    user_id = uuid4()
    job_id = uuid4()

    task = JobGenerationTask.create(
        user_id=user_id,
        job_id=job_id,
        run_type="regenerate",
        target_artifact="proposal",
        instruction="Make it shorter.",
    )
    payload = task.to_payload()
    restored = JobGenerationTask.from_payload(payload)

    assert restored.user_id == user_id
    assert restored.job_id == job_id
    assert restored.run_type == "regenerate"
    assert restored.target_artifact == "proposal"
    assert restored.instruction == "Make it shorter."
    assert restored.idempotency_key == task.idempotency_key
