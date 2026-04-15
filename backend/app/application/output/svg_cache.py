from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from redis.asyncio import Redis

from app.infrastructure.config.settings import get_settings

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "doc_flowchart:svg:v2"
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_STYLE_VERSION = "2026-04-15.a"


@dataclass(frozen=True)
class CachedSvg:
    svg: str
    model_name: str
    provider_name: str
    visual_score: int


def _compute_key(
    *,
    markdown_section: str,
    instruction: str | None,
    canvas_width: int,
    canvas_height: int,
) -> str:
    digest_source = "||".join(
        [
            _STYLE_VERSION,
            str(canvas_width),
            str(canvas_height),
            (instruction or "").strip(),
            markdown_section.strip(),
        ]
    ).encode("utf-8")
    digest = hashlib.sha256(digest_source).hexdigest()
    return f"{_CACHE_PREFIX}:{digest}"


async def _get_redis() -> Redis | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        return Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    except Exception as exc:  # pragma: no cover - config errors
        logger.warning("doc_flowchart cache: failed to create redis client: %s", exc)
        return None


async def get_cached_svg(
    *,
    markdown_section: str,
    instruction: str | None,
    canvas_width: int,
    canvas_height: int,
) -> CachedSvg | None:
    client = await _get_redis()
    if client is None:
        return None
    key = _compute_key(
        markdown_section=markdown_section,
        instruction=instruction,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    try:
        try:
            payload = await client.get(key)
        finally:
            await client.aclose()
    except Exception as exc:
        logger.warning("doc_flowchart cache: GET failed: %s", exc)
        return None
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    svg = parsed.get("svg")
    if not isinstance(svg, str) or not svg.strip():
        return None
    return CachedSvg(
        svg=svg,
        model_name=str(parsed.get("model_name") or ""),
        provider_name=str(parsed.get("provider_name") or ""),
        visual_score=int(parsed.get("visual_score") or 0),
    )


async def set_cached_svg(
    *,
    markdown_section: str,
    instruction: str | None,
    canvas_width: int,
    canvas_height: int,
    svg: str,
    model_name: str,
    provider_name: str,
    visual_score: int,
) -> None:
    client = await _get_redis()
    if client is None:
        return
    key = _compute_key(
        markdown_section=markdown_section,
        instruction=instruction,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    payload = json.dumps(
        {
            "svg": svg,
            "model_name": model_name,
            "provider_name": provider_name,
            "visual_score": visual_score,
        }
    )
    try:
        try:
            await client.set(key, payload, ex=_CACHE_TTL_SECONDS)
        finally:
            await client.aclose()
    except Exception as exc:
        logger.warning("doc_flowchart cache: SET failed: %s", exc)
