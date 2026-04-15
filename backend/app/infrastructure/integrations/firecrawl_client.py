from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability.metrics import metrics_state

settings = get_settings()


@dataclass(frozen=True)
class FirecrawlExtractionError(Exception):
    message: str
    code: str = "firecrawl_extraction_failed"
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class FirecrawlExtractResult:
    markdown: str
    metadata: dict[str, Any] | None


def _extract_markdown(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("markdown", "content", "text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload.get("markdown"), str) and payload["markdown"].strip():
        return payload["markdown"].strip()
    return None


def _extract_metadata(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if isinstance(data, dict):
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            return metadata
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return None


async def extract_markdown_from_url(url: str, api_key: str | None = None) -> str:
    result = await extract_markdown_bundle_from_url(url=url, api_key=api_key)
    return result.markdown


async def extract_markdown_bundle_from_url(url: str, api_key: str | None = None) -> FirecrawlExtractResult:
    started_at = perf_counter()
    resolved_api_key = (api_key or "").strip()
    if not resolved_api_key:
        metrics_state.record_external_api_call(
            duration_ms=(perf_counter() - started_at) * 1000,
            success=False,
        )
        raise FirecrawlExtractionError(
            message="Firecrawl is not configured. Missing API key.",
            code="firecrawl_not_configured",
            retryable=False,
        )

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"url": url, "formats": ["markdown", "html"]}
    endpoint = f"{settings.firecrawl_base_url.rstrip('/')}/v1/scrape"

    max_retries = max(settings.firecrawl_max_retries, 0)
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.firecrawl_timeout_seconds) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            if attempt < max_retries:
                await asyncio.sleep(settings.firecrawl_retry_backoff_seconds * (attempt + 1))
                continue
            metrics_state.record_external_api_call(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=False,
            )
            raise FirecrawlExtractionError(
                message="Firecrawl timed out while extracting this URL.",
                code="firecrawl_timeout",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            if attempt < max_retries:
                await asyncio.sleep(settings.firecrawl_retry_backoff_seconds * (attempt + 1))
                continue
            metrics_state.record_external_api_call(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=False,
            )
            raise FirecrawlExtractionError(
                message="Firecrawl request failed due to network error.",
                code="firecrawl_network_error",
                retryable=True,
            ) from exc

        if response.status_code >= 500 and attempt < max_retries:
            await asyncio.sleep(settings.firecrawl_retry_backoff_seconds * (attempt + 1))
            continue

        if response.status_code >= 400:
            metrics_state.record_external_api_call(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=False,
            )
            raise FirecrawlExtractionError(
                message=f"Firecrawl request failed with status {response.status_code}.",
                code="firecrawl_http_error",
                retryable=response.status_code >= 500,
            )

        try:
            body = response.json()
        except ValueError as exc:
            metrics_state.record_external_api_call(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=False,
            )
            raise FirecrawlExtractionError(
                message="Firecrawl returned invalid JSON.",
                code="firecrawl_invalid_response",
                retryable=False,
            ) from exc

        markdown = _extract_markdown(body)
        if markdown:
            metrics_state.record_external_api_call(
                duration_ms=(perf_counter() - started_at) * 1000,
                success=True,
            )
            return FirecrawlExtractResult(markdown=markdown, metadata=_extract_metadata(body))

        metrics_state.record_external_api_call(
            duration_ms=(perf_counter() - started_at) * 1000,
            success=False,
        )
        raise FirecrawlExtractionError(
            message="Firecrawl did not return markdown content.",
            code="firecrawl_empty_response",
            retryable=False,
        )

    metrics_state.record_external_api_call(
        duration_ms=(perf_counter() - started_at) * 1000,
        success=False,
    )
    raise FirecrawlExtractionError(message="Firecrawl extraction failed after retries.")
