from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.infrastructure.config.settings import get_settings

_VISION_MODEL = "gpt-5.4-mini"
_MAX_PNG_BYTES_FOR_VISION = 3_500_000
_PASS_THRESHOLD = 70

_SYSTEM_PROMPT = (
    "You are a strict visual QA reviewer for business flowcharts rendered as PNG images. "
    "Score the image's visual quality as a client-facing diagram. "
    "Return ONLY compact JSON matching this schema: "
    '{"score": 0-100, "pass": boolean, "issues": [string]} . '
    "Mark pass=true only if score >= 70 AND there are no critical issues."
)

_USER_PROMPT = (
    "Review this flowchart image for the following issues:\n"
    "- Text truncated with ellipsis (e.g., 'Webhook Receives SK...')\n"
    "- Text overflowing outside its container/card\n"
    "- Overlapping nodes, arrows, or labels\n"
    "- Arrows that do not clearly connect source to target\n"
    "- Unreadable font sizes (too small) or text cut off by edges\n"
    "- Disproportionate spacing (cards crammed, empty canvas areas)\n"
    "- Cards positioned outside the visible canvas\n"
    "Critical issues (must fail): truncated text, overlapping nodes, missing arrows, "
    "text out of canvas. Minor issues are acceptable. Be honest and strict. "
    "Respond with JSON only, no prose."
)


@dataclass
class SvgVisualResult:
    passed: bool
    score: int
    issues: list[str] = field(default_factory=list)
    raw_response: str | None = None
    error: str | None = None


def _parse_vision_payload(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def validate_svg_visual(*, png_bytes: bytes) -> SvgVisualResult:
    """Vision-based quality check via gpt-5.4-mini.

    Returns pass=True if the image is clean enough to ship to a client.
    On API error or malformed response returns a neutral result (passed=True,
    score=0) so the pipeline does not block on validator outages; the caller
    may still choose to short-circuit on error.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return SvgVisualResult(passed=True, score=0, error="openai_not_configured")

    if len(png_bytes) > _MAX_PNG_BYTES_FOR_VISION:
        return SvgVisualResult(passed=True, score=0, error="png_too_large_for_vision")
    if not png_bytes.startswith(b"\x89PNG"):
        return SvgVisualResult(passed=False, score=0, error="not_a_png")

    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    payload = {
        "model": _VISION_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.0,
        "max_completion_tokens": 400,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        return SvgVisualResult(passed=True, score=0, error=f"transport:{exc}")

    if response.status_code >= 400:
        return SvgVisualResult(
            passed=True,
            score=0,
            error=f"http_{response.status_code}",
            raw_response=response.text[:500],
        )

    try:
        body = response.json()
    except ValueError:
        return SvgVisualResult(passed=True, score=0, error="non_json_response")

    choices = body.get("choices") or []
    if not choices:
        return SvgVisualResult(passed=True, score=0, error="no_choices")
    message = choices[0].get("message", {})
    text = (message.get("content") or "").strip()
    parsed = _parse_vision_payload(text)
    if not parsed:
        return SvgVisualResult(passed=True, score=0, error="unparseable", raw_response=text[:500])

    raw_score = parsed.get("score")
    try:
        score = int(raw_score) if raw_score is not None else 0
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))

    raw_issues = parsed.get("issues") or []
    issues = [str(item)[:200] for item in raw_issues if item] if isinstance(raw_issues, list) else []

    declared_pass = bool(parsed.get("pass"))
    passed = declared_pass and score >= _PASS_THRESHOLD

    return SvgVisualResult(passed=passed, score=score, issues=issues, raw_response=text[:500])
