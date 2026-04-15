from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.infrastructure.config.settings import get_settings


@dataclass
class _ProviderHealthState:
    failure_streak: int = 0
    open_until: datetime | None = None
    last_error: str | None = None


class ProviderHealthManager:
    def __init__(self) -> None:
        self._state: dict[str, _ProviderHealthState] = {}
        self._lock = Lock()

    def _key(self, provider: str, model_name: str | None) -> str:
        return f"{provider}:{model_name or '*'}"

    def is_circuit_open(self, *, provider: str, model_name: str | None) -> bool:
        with self._lock:
            key = self._key(provider, model_name)
            item = self._state.get(key)
            if not item or not item.open_until:
                return False
            if datetime.now(UTC) >= item.open_until:
                item.open_until = None
                item.failure_streak = 0
                item.last_error = None
                return False
            return True

    def record_success(self, *, provider: str, model_name: str | None) -> None:
        with self._lock:
            key = self._key(provider, model_name)
            self._state[key] = _ProviderHealthState()

    def record_failure(self, *, provider: str, model_name: str | None, error_code: str) -> bool:
        settings = get_settings()
        with self._lock:
            key = self._key(provider, model_name)
            item = self._state.get(key) or _ProviderHealthState()
            item.failure_streak += 1
            item.last_error = error_code
            opened = False
            if item.failure_streak >= settings.ai_provider_failure_threshold:
                item.open_until = datetime.now(UTC) + timedelta(
                    seconds=settings.ai_provider_circuit_open_seconds
                )
                opened = True
            self._state[key] = item
            return opened

    def snapshot(self) -> dict[str, dict[str, str | int | None]]:
        with self._lock:
            out: dict[str, dict[str, str | int | None]] = {}
            for key, item in self._state.items():
                out[key] = {
                    "failure_streak": item.failure_streak,
                    "open_until": item.open_until.isoformat() if item.open_until else None,
                    "last_error": item.last_error,
                }
            return out


provider_health_manager = ProviderHealthManager()

