from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.infrastructure.config.settings import get_settings

settings = get_settings()


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class InMemoryGlobalRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)
        self._window = timedelta(seconds=settings.global_rate_limit_window_seconds)
        self._max_attempts = settings.global_rate_limit_requests

    def _cleanup(self, key: str, now: datetime) -> None:
        threshold = now - self._window
        bucket = self._attempts[key]
        while bucket and bucket[0] < threshold:
            bucket.popleft()

    def check_and_record(self, key: str) -> RateLimitResult:
        now = datetime.now(UTC)
        with self._lock:
            self._cleanup(key, now)
            bucket = self._attempts[key]
            if len(bucket) >= self._max_attempts:
                retry_after = int((bucket[0] + self._window - now).total_seconds())
                return RateLimitResult(allowed=False, retry_after_seconds=max(retry_after, 1))
            bucket.append(now)
            return RateLimitResult(allowed=True, retry_after_seconds=0)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()


global_rate_limiter = InMemoryGlobalRateLimiter()
