from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

import httpx

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.providers.base import AIProviderAdapter
from app.infrastructure.config.settings import get_settings
from app.infrastructure.ai.provider_health import provider_health_manager
from app.infrastructure.observability.metrics import metrics_state

_RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}


class OpenAIProviderAdapter(AIProviderAdapter):
    provider = ProviderName.OPENAI

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._base_url = (base_url if base_url is not None else settings.openai_base_url).rstrip("/")
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.openai_timeout_seconds
        )
        self._max_retries = max_retries if max_retries is not None else settings.openai_max_retries
        self._retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else settings.openai_retry_backoff_seconds
        )
        self._provided_http_client = http_client

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        if provider_health_manager.is_circuit_open(provider=self.provider.value, model_name=request.model_name):
            metrics_state.record_ai_provider_circuit_open()
            raise AIException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Provider circuit is open due to repeated failures",
                details={"provider": self.provider.value, "model_name": request.model_name},
            )

        if not self._api_key:
            raise AIException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="OpenAI provider is not configured",
                details={"provider": self.provider.value, "missing": "openai_api_key"},
            )

        payload = self._build_payload(request=request)
        started_at = perf_counter()
        response_json = await self._post_chat_completions_with_retry(payload=payload)
        elapsed_ms = int((perf_counter() - started_at) * 1000)

        output_text = self._extract_output_text(response_json)
        usage = response_json.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        resolved_model = str(response_json.get("model") or request.model_name)
        provider_health_manager.record_success(provider=self.provider.value, model_name=resolved_model)

        return ProviderGenerateResult(
            provider=self.provider,
            model_name=resolved_model,
            output_text=output_text,
            output_json=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed_ms,
            raw_response=response_json,
        )

    def _build_payload(self, *, request: ProviderGenerateRequest) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_output_tokens is not None:
            # GPT-5 chat-completions expects max_completion_tokens.
            payload["max_completion_tokens"] = request.max_output_tokens
        return payload

    async def _post_chat_completions_with_retry(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        async def _execute(client: httpx.AsyncClient) -> dict[str, Any]:
            last_exception: Exception | None = None
            max_attempts = self._max_retries + 1
            url = f"{self._base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {self._api_key}"}

            for attempt in range(1, max_attempts + 1):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except httpx.TimeoutException as exc:
                    metrics_state.record_ai_provider_failure()
                    opened = provider_health_manager.record_failure(
                        provider=self.provider.value,
                        model_name=str(payload.get("model") or ""),
                        error_code=AIErrorCode.PROVIDER_TIMEOUT.value,
                    )
                    if opened:
                        metrics_state.record_ai_provider_circuit_open()
                    last_exception = exc
                    if attempt >= max_attempts:
                        raise AIException(
                            code=AIErrorCode.PROVIDER_TIMEOUT,
                            message="OpenAI request timed out",
                            details={"provider": self.provider.value, "attempt": attempt},
                        ) from exc
                    await asyncio.sleep(self._retry_backoff_seconds * attempt)
                    continue
                except httpx.TransportError as exc:
                    metrics_state.record_ai_provider_failure()
                    opened = provider_health_manager.record_failure(
                        provider=self.provider.value,
                        model_name=str(payload.get("model") or ""),
                        error_code=AIErrorCode.PROVIDER_UNAVAILABLE.value,
                    )
                    if opened:
                        metrics_state.record_ai_provider_circuit_open()
                    last_exception = exc
                    if attempt >= max_attempts:
                        raise AIException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message="OpenAI transport failure",
                            details={"provider": self.provider.value, "attempt": attempt},
                        ) from exc
                    await asyncio.sleep(self._retry_backoff_seconds * attempt)
                    continue

                if response.status_code == 429:
                    metrics_state.record_ai_provider_failure()
                    opened = provider_health_manager.record_failure(
                        provider=self.provider.value,
                        model_name=str(payload.get("model") or ""),
                        error_code=AIErrorCode.PROVIDER_RATE_LIMITED.value,
                    )
                    if opened:
                        metrics_state.record_ai_provider_circuit_open()
                    if attempt >= max_attempts:
                        raise AIException(
                            code=AIErrorCode.PROVIDER_RATE_LIMITED,
                            message="OpenAI rate limit exceeded",
                            details={"provider": self.provider.value, "status_code": 429},
                        )
                    await asyncio.sleep(self._retry_backoff_seconds * attempt)
                    continue

                if response.status_code in _RETRYABLE_HTTP_STATUSES:
                    metrics_state.record_ai_provider_failure()
                    opened = provider_health_manager.record_failure(
                        provider=self.provider.value,
                        model_name=str(payload.get("model") or ""),
                        error_code=AIErrorCode.PROVIDER_UNAVAILABLE.value,
                    )
                    if opened:
                        metrics_state.record_ai_provider_circuit_open()
                    if attempt >= max_attempts:
                        raise AIException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message="OpenAI temporary provider failure",
                            details={
                                "provider": self.provider.value,
                                "status_code": response.status_code,
                            },
                        )
                    await asyncio.sleep(self._retry_backoff_seconds * attempt)
                    continue

                if response.status_code >= 400:
                    metrics_state.record_ai_provider_failure()
                    opened = provider_health_manager.record_failure(
                        provider=self.provider.value,
                        model_name=str(payload.get("model") or ""),
                        error_code=AIErrorCode.ORCHESTRATION_FAILED.value,
                    )
                    if opened:
                        metrics_state.record_ai_provider_circuit_open()
                    raise AIException(
                        code=AIErrorCode.ORCHESTRATION_FAILED,
                        message="OpenAI request rejected",
                        details={
                            "provider": self.provider.value,
                            "status_code": response.status_code,
                            "response_text": response.text,
                        },
                    )

                try:
                    return response.json()
                except ValueError as exc:
                    raise AIException(
                        code=AIErrorCode.INVALID_OUTPUT,
                        message="OpenAI returned non-JSON response",
                        details={"provider": self.provider.value},
                    ) from exc

            if last_exception:
                raise AIException(
                    code=AIErrorCode.PROVIDER_UNAVAILABLE,
                    message="OpenAI request failed after retries",
                    details={"provider": self.provider.value},
                ) from last_exception

            raise AIException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="OpenAI request failed after retries",
                details={"provider": self.provider.value},
            )

        if self._provided_http_client is not None:
            return await _execute(self._provided_http_client)

        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await _execute(client)

    def _extract_output_text(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIException(
                code=AIErrorCode.INVALID_OUTPUT,
                message="OpenAI response missing choices",
                details={"provider": self.provider.value},
            )

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            stripped = content.strip()
            if stripped:
                return stripped

        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="OpenAI response missing text content",
            details={"provider": self.provider.value},
        )
