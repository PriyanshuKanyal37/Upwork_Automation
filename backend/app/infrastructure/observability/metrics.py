from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock


@dataclass
class MetricsState:
    http_requests_total: int = 0
    http_requests_5xx_total: int = 0
    http_request_duration_ms_total: float = 0.0
    worker_runs_total: int = 0
    worker_failures_total: int = 0
    worker_duration_ms_total: float = 0.0
    external_api_calls_total: int = 0
    external_api_failures_total: int = 0
    external_api_duration_ms_total: float = 0.0
    queue_enqueued_total: int = 0
    queue_completed_total: int = 0
    queue_failed_total: int = 0
    queue_depth_current: int = 0
    ai_generation_runs_total: int = 0
    ai_generation_failures_total: int = 0
    ai_policy_denied_total: int = 0
    ai_guardrail_block_total: int = 0
    ai_provider_failures_total: int = 0
    ai_provider_circuit_open_total: int = 0
    ai_fallback_total: int = 0
    ai_input_tokens_total: int = 0
    ai_output_tokens_total: int = 0
    ai_estimated_cost_usd_total: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_http_request(self, *, duration_ms: float, status_code: int) -> None:
        with self._lock:
            self.http_requests_total += 1
            self.http_request_duration_ms_total += duration_ms
            if status_code >= 500:
                self.http_requests_5xx_total += 1

    def record_worker_run(self, *, duration_ms: float, success: bool) -> None:
        with self._lock:
            self.worker_runs_total += 1
            self.worker_duration_ms_total += duration_ms
            if not success:
                self.worker_failures_total += 1

    def record_external_api_call(self, *, duration_ms: float, success: bool) -> None:
        with self._lock:
            self.external_api_calls_total += 1
            self.external_api_duration_ms_total += duration_ms
            if not success:
                self.external_api_failures_total += 1

    def queue_enqueued(self) -> None:
        with self._lock:
            self.queue_enqueued_total += 1
            self.queue_depth_current += 1

    def queue_completed(self) -> None:
        with self._lock:
            self.queue_completed_total += 1
            self.queue_depth_current = max(self.queue_depth_current - 1, 0)

    def queue_failed(self) -> None:
        with self._lock:
            self.queue_failed_total += 1
            self.queue_depth_current = max(self.queue_depth_current - 1, 0)

    def record_ai_run(
        self,
        *,
        success: bool,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: Decimal | float | int,
    ) -> None:
        with self._lock:
            self.ai_generation_runs_total += 1
            if not success:
                self.ai_generation_failures_total += 1
            self.ai_input_tokens_total += max(0, int(input_tokens))
            self.ai_output_tokens_total += max(0, int(output_tokens))
            self.ai_estimated_cost_usd_total += float(estimated_cost_usd)

    def record_ai_policy_denied(self) -> None:
        with self._lock:
            self.ai_policy_denied_total += 1

    def record_ai_guardrail_block(self) -> None:
        with self._lock:
            self.ai_guardrail_block_total += 1

    def record_ai_provider_failure(self) -> None:
        with self._lock:
            self.ai_provider_failures_total += 1

    def record_ai_provider_circuit_open(self) -> None:
        with self._lock:
            self.ai_provider_circuit_open_total += 1

    def record_ai_fallback(self) -> None:
        with self._lock:
            self.ai_fallback_total += 1

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            avg_http_duration = (
                self.http_request_duration_ms_total / self.http_requests_total
                if self.http_requests_total
                else 0.0
            )
            avg_worker_duration = (
                self.worker_duration_ms_total / self.worker_runs_total
                if self.worker_runs_total
                else 0.0
            )
            avg_external_duration = (
                self.external_api_duration_ms_total / self.external_api_calls_total
                if self.external_api_calls_total
                else 0.0
            )
            return {
                "http_requests_total": self.http_requests_total,
                "http_requests_5xx_total": self.http_requests_5xx_total,
                "http_request_duration_ms_avg": round(avg_http_duration, 2),
                "worker_runs_total": self.worker_runs_total,
                "worker_failures_total": self.worker_failures_total,
                "worker_duration_ms_avg": round(avg_worker_duration, 2),
                "external_api_calls_total": self.external_api_calls_total,
                "external_api_failures_total": self.external_api_failures_total,
                "external_api_duration_ms_avg": round(avg_external_duration, 2),
                "queue_enqueued_total": self.queue_enqueued_total,
                "queue_completed_total": self.queue_completed_total,
                "queue_failed_total": self.queue_failed_total,
                "queue_depth_current": self.queue_depth_current,
                "ai_generation_runs_total": self.ai_generation_runs_total,
                "ai_generation_failures_total": self.ai_generation_failures_total,
                "ai_policy_denied_total": self.ai_policy_denied_total,
                "ai_guardrail_block_total": self.ai_guardrail_block_total,
                "ai_provider_failures_total": self.ai_provider_failures_total,
                "ai_provider_circuit_open_total": self.ai_provider_circuit_open_total,
                "ai_fallback_total": self.ai_fallback_total,
                "ai_input_tokens_total": self.ai_input_tokens_total,
                "ai_output_tokens_total": self.ai_output_tokens_total,
                "ai_estimated_cost_usd_total": round(self.ai_estimated_cost_usd_total, 6),
            }

    def clear(self) -> None:
        with self._lock:
            self.http_requests_total = 0
            self.http_requests_5xx_total = 0
            self.http_request_duration_ms_total = 0.0
            self.worker_runs_total = 0
            self.worker_failures_total = 0
            self.worker_duration_ms_total = 0.0
            self.external_api_calls_total = 0
            self.external_api_failures_total = 0
            self.external_api_duration_ms_total = 0.0
            self.queue_enqueued_total = 0
            self.queue_completed_total = 0
            self.queue_failed_total = 0
            self.queue_depth_current = 0
            self.ai_generation_runs_total = 0
            self.ai_generation_failures_total = 0
            self.ai_policy_denied_total = 0
            self.ai_guardrail_block_total = 0
            self.ai_provider_failures_total = 0
            self.ai_provider_circuit_open_total = 0
            self.ai_fallback_total = 0
            self.ai_input_tokens_total = 0
            self.ai_output_tokens_total = 0
            self.ai_estimated_cost_usd_total = 0.0


metrics_state = MetricsState()
