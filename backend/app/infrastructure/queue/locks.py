from __future__ import annotations

import inspect
from uuid import UUID

from redis.asyncio import Redis

_LOCK_TTL_SECONDS = 600


def _lock_key(job_id: UUID, namespace: str = "job-extract") -> str:
    return f"queue:{namespace}:lock:{job_id}"


async def acquire_job_lock(
    *, redis_client: Redis, job_id: UUID, idempotency_key: str, namespace: str = "job-extract"
) -> bool:
    return bool(
        await redis_client.set(
            _lock_key(job_id, namespace),
            idempotency_key,
            ex=_LOCK_TTL_SECONDS,
            nx=True,
        )
    )


async def release_job_lock(
    *, redis_client: Redis, job_id: UUID, idempotency_key: str, namespace: str = "job-extract"
) -> None:
    # Delete only when this worker still owns the lock token.
    delete_script = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""
    result = redis_client.eval(delete_script, 1, _lock_key(job_id, namespace), idempotency_key)
    if inspect.isawaitable(result):
        await result
