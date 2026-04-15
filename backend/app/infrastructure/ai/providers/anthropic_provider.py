from __future__ import annotations

import asyncio
import random
from time import perf_counter
from typing import Any

import httpx

from app.application.ai.contracts import (
    ProviderAgentRequest,
    ProviderAgentTurnResult,
    ProviderGenerateRequest,
    ProviderGenerateResult,
    ProviderName,
    ToolUse,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.providers.base import AIProviderAdapter
from app.infrastructure.ai.provider_health import provider_health_manager
from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability.metrics import metrics_state

_RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}
_TOKEN_COUNTING_BETA_HEADER = "token-counting-2024-11-01"
_MAX_RETRY_BACKOFF_SECONDS = 30.0
_MIN_RETRY_ATTEMPTS = 5


class AnthropicProviderAdapter(AIProviderAdapter):
    provider = ProviderName.ANTHROPIC

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        anthropic_version: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.anthropic_api_key
        self._base_url = (base_url if base_url is not None else settings.anthropic_base_url).rstrip("/")
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.anthropic_timeout_seconds
        )
        self._max_retries = max_retries if max_retries is not None else settings.anthropic_max_retries
        self._retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else settings.anthropic_retry_backoff_seconds
        )
        self._anthropic_version = (
            anthropic_version
            if anthropic_version is not None
            else settings.anthropic_api_version
        )
        self._provided_http_client = http_client

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        self._assert_provider_available(model_name=request.model_name)

        payload = self._build_payload(request=request)
        started_at = perf_counter()
        response_json = await self._post_messages_with_retry(payload=payload)
        elapsed_ms = int((perf_counter() - started_at) * 1000)

        output_text = self._extract_output_text(response_json)
        usage = response_json.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
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

    async def generate_with_tools(
        self,
        request: ProviderAgentRequest,
    ) -> ProviderAgentTurnResult:
        self._assert_provider_available(model_name=request.model_name)

        payload = self._build_tool_payload(request=request)
        started_at = perf_counter()
        response_json = await self._post_messages_with_retry(payload=payload)
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        resolved_model = str(response_json.get("model") or request.model_name)
        provider_health_manager.record_success(provider=self.provider.value, model_name=resolved_model)

        output_text = self._extract_output_text_optional(response_json)
        tool_uses = self._extract_tool_uses(response_json)
        stop_reason = str(response_json.get("stop_reason") or "end_turn")
        usage = response_json.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        cache_read_input_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
        return ProviderAgentTurnResult(
            provider=self.provider,
            model_name=resolved_model,
            output_text=output_text,
            tool_uses=tool_uses,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            latency_ms=elapsed_ms,
            raw_response=response_json,
        )

    async def count_tokens_for_tools(self, request: ProviderAgentRequest) -> int:
        self._assert_provider_available(model_name=request.model_name)
        payload = self._build_tool_payload(request=request)
        # count_tokens does not accept generation-only fields.
        payload.pop("temperature", None)
        payload.pop("max_tokens", None)
        response_json = await self._post_count_tokens(payload=payload)
        return int(response_json.get("input_tokens", 0) or 0)

    def _assert_provider_available(self, *, model_name: str) -> None:
        if provider_health_manager.is_circuit_open(provider=self.provider.value, model_name=model_name):
            metrics_state.record_ai_provider_circuit_open()
            raise AIException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Provider circuit is open due to repeated failures",
                details={"provider": self.provider.value, "model_name": model_name},
            )
        if not self._api_key:
            raise AIException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Anthropic provider is not configured",
                details={"provider": self.provider.value, "missing": "anthropic_api_key"},
            )

    def _build_payload(self, *, request: ProviderGenerateRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or 3000,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.response_schema:
            # Anthropic structured outputs (GA on Sonnet 4.6).
            # Schema is constrained-decoded so the model cannot emit invalid JSON.
            payload["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": request.response_schema,
                }
            }
        return payload

    def _build_tool_payload(self, *, request: ProviderAgentRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": request.messages,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    **({"cache_control": tool.cache_control} if tool.cache_control else {}),
                }
                for tool in request.tools
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if request.system_prompt:
            payload["system"] = [
                {
                    "type": "text",
                    "text": request.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice.model_dump(exclude_none=True)
        return payload

    async def _post_count_tokens(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/v1/messages/count_tokens"
        headers = {
            "x-api-key": str(self._api_key),
            "anthropic-version": self._anthropic_version,
            "anthropic-beta": _TOKEN_COUNTING_BETA_HEADER,
        }

        async def _execute(client: httpx.AsyncClient) -> dict[str, Any]:
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                raise AIException(
                    code=AIErrorCode.PROVIDER_UNAVAILABLE,
                    message="Anthropic token counting request failed",
                    details={"provider": self.provider.value, "error": str(exc)},
                ) from exc

            if response.status_code >= 400:
                raise AIException(
                    code=AIErrorCode.ORCHESTRATION_FAILED,
                    message="Anthropic token counting request rejected",
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
                    message="Anthropic token counting returned non-JSON response",
                    details={"provider": self.provider.value},
                ) from exc

        if self._provided_http_client is not None:
            return await _execute(self._provided_http_client)

        timeout = httpx.Timeout(min(self._timeout_seconds, 20.0))
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await _execute(client)

    async def _post_messages_with_retry(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        def _next_retry_delay(*, attempt: int, response: httpx.Response | None = None) -> float:
            if response is not None:
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    try:
                        parsed = float(retry_after.strip())
                        if parsed > 0:
                            return min(parsed, _MAX_RETRY_BACKOFF_SECONDS)
                    except ValueError:
                        pass

            base = self._retry_backoff_seconds * (2 ** max(attempt - 1, 0))
            clamped = min(max(base, self._retry_backoff_seconds), _MAX_RETRY_BACKOFF_SECONDS)
            jittered = clamped * random.uniform(0.8, 1.2)
            return max(self._retry_backoff_seconds, min(jittered, _MAX_RETRY_BACKOFF_SECONDS))

        async def _execute(client: httpx.AsyncClient) -> dict[str, Any]:
            last_exception: Exception | None = None
            max_attempts = max(self._max_retries + 1, _MIN_RETRY_ATTEMPTS)
            model_name = str(payload.get("model") or "")
            url = f"{self._base_url}/v1/messages"
            headers = {
                "x-api-key": str(self._api_key),
                "anthropic-version": self._anthropic_version,
                "anthropic-beta": "prompt-caching-2024-07-31",
            }

            def _record_request_failure(error_code: AIErrorCode) -> None:
                metrics_state.record_ai_provider_failure()
                opened = provider_health_manager.record_failure(
                    provider=self.provider.value,
                    model_name=model_name,
                    error_code=error_code.value,
                )
                if opened:
                    metrics_state.record_ai_provider_circuit_open()

            for attempt in range(1, max_attempts + 1):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except httpx.TimeoutException as exc:
                    last_exception = exc
                    if attempt >= max_attempts:
                        _record_request_failure(AIErrorCode.PROVIDER_TIMEOUT)
                        raise AIException(
                            code=AIErrorCode.PROVIDER_TIMEOUT,
                            message="Anthropic request timed out",
                            details={"provider": self.provider.value, "attempt": attempt},
                        ) from exc
                    await asyncio.sleep(_next_retry_delay(attempt=attempt))
                    continue
                except httpx.TransportError as exc:
                    last_exception = exc
                    if attempt >= max_attempts:
                        _record_request_failure(AIErrorCode.PROVIDER_UNAVAILABLE)
                        raise AIException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message="Anthropic transport failure",
                            details={"provider": self.provider.value, "attempt": attempt},
                        ) from exc
                    await asyncio.sleep(_next_retry_delay(attempt=attempt))
                    continue

                if response.status_code == 529:
                    # Anthropic overloaded — fail fast after 1 retry (2 total attempts).
                    # Retrying many times on overload wastes money; let the agent fall back
                    # to a different model instead.
                    if attempt >= 2:
                        _record_request_failure(AIErrorCode.PROVIDER_UNAVAILABLE)
                        raise AIException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message="Anthropic provider overloaded",
                            details={"provider": self.provider.value, "status_code": 529},
                        )
                    await asyncio.sleep(2.0)
                    continue

                if response.status_code == 429:
                    if attempt >= max_attempts:
                        _record_request_failure(AIErrorCode.PROVIDER_RATE_LIMITED)
                        raise AIException(
                            code=AIErrorCode.PROVIDER_RATE_LIMITED,
                            message="Anthropic rate limit exceeded",
                            details={"provider": self.provider.value, "status_code": 429},
                        )
                    await asyncio.sleep(_next_retry_delay(attempt=attempt, response=response))
                    continue

                if response.status_code in _RETRYABLE_HTTP_STATUSES:
                    if attempt >= max_attempts:
                        _record_request_failure(AIErrorCode.PROVIDER_UNAVAILABLE)
                        raise AIException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message="Anthropic temporary provider failure",
                            details={
                                "provider": self.provider.value,
                                "status_code": response.status_code,
                            },
                        )
                    await asyncio.sleep(_next_retry_delay(attempt=attempt, response=response))
                    continue

                if response.status_code >= 400:
                    _record_request_failure(AIErrorCode.ORCHESTRATION_FAILED)
                    raise AIException(
                        code=AIErrorCode.ORCHESTRATION_FAILED,
                        message="Anthropic request rejected",
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
                        message="Anthropic returned non-JSON response",
                        details={"provider": self.provider.value},
                    ) from exc

            if last_exception:
                raise AIException(
                    code=AIErrorCode.PROVIDER_UNAVAILABLE,
                    message="Anthropic request failed after retries",
                    details={"provider": self.provider.value},
                ) from last_exception

            raise AIException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Anthropic request failed after retries",
                details={"provider": self.provider.value},
            )

        if self._provided_http_client is not None:
            return await _execute(self._provided_http_client)

        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await _execute(client)

    def _extract_output_text(self, response_json: dict[str, Any]) -> str:
        combined = self._extract_output_text_optional(response_json)
        if combined:
            return combined
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Anthropic response missing text content",
            details={"provider": self.provider.value},
        )

    def _extract_output_text_optional(self, response_json: dict[str, Any]) -> str | None:
        content = response_json.get("content")
        if not isinstance(content, list) or not content:
            raise AIException(
                code=AIErrorCode.INVALID_OUTPUT,
                message="Anthropic response missing content",
                details={"provider": self.provider.value},
            )

        text_chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                text_chunks.append(text.strip())

        combined = "\n".join(text_chunks).strip()
        return combined if combined else None

    def _extract_tool_uses(self, response_json: dict[str, Any]) -> list[ToolUse]:
        content = response_json.get("content")
        if not isinstance(content, list):
            return []

        stop_reason = str(response_json.get("stop_reason") or "")
        parsed: list[ToolUse] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use":
                continue
            tool_id = str(item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not tool_id or not name:
                continue
            input_payload = item.get("input")
            if not isinstance(input_payload, dict):
                # max_tokens truncated the tool call mid-JSON — surface it with a
                # truncated marker so the agent loop can detect and recover.
                if stop_reason == "max_tokens":
                    input_payload = {"_truncated": True, "_partial_raw": str(input_payload or "")[:200]}
                else:
                    continue
            parsed.append(ToolUse(id=tool_id, name=name, input=input_payload))
        return parsed
