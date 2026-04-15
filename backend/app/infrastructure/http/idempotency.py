from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.infrastructure.config.settings import get_settings

settings = get_settings()


@dataclass(frozen=True)
class IdempotencyRecord:
    created_at: datetime
    status_code: int
    media_type: str | None
    body: bytes
    headers: dict[str, str]


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: OrderedDict[str, IdempotencyRecord] = OrderedDict()
        self._lock = Lock()
        self._ttl = timedelta(seconds=settings.idempotency_ttl_seconds)
        self._max_entries = settings.idempotency_max_entries

    def _cleanup(self, *, now: datetime) -> None:
        expired = [key for key, value in self._records.items() if now - value.created_at > self._ttl]
        for key in expired:
            self._records.pop(key, None)
        while len(self._records) > self._max_entries:
            self._records.popitem(last=False)

    def get(self, key: str) -> IdempotencyRecord | None:
        now = datetime.now(UTC)
        with self._lock:
            self._cleanup(now=now)
            record = self._records.get(key)
            if not record:
                return None
            self._records.move_to_end(key)
            return record

    def set(self, key: str, value: IdempotencyRecord) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._cleanup(now=now)
            self._records[key] = value
            self._records.move_to_end(key)
            while len(self._records) > self._max_entries:
                self._records.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


idempotency_store = InMemoryIdempotencyStore()
