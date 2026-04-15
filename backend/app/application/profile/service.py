import re
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.contracts import ProviderGenerateRequest
from app.application.ai.guardrails import assert_safe_input, assert_safe_output
from app.infrastructure.ai.providers.openai_provider import OpenAIProviderAdapter
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.models.user_profile import UserProfile
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.integrations.firecrawl_client import (
    FirecrawlExtractionError,
    extract_markdown_from_url,
)

_OPTIONAL_TEXT_FIELDS = (
    "upwork_profile_url",
    "upwork_profile_id",
    "upwork_profile_markdown",
    "proposal_template",
    "doc_template",
    "loom_template",
    "workflow_template_notes",
    "custom_global_instruction",
)
_UPWORK_PROFILE_ID_PATTERNS = (
    re.compile(r"/freelancers/~([0-9a-fA-F]{10,})"),
    re.compile(r"/~([0-9a-fA-F]{10,})"),
    re.compile(r"/o/profiles/users/([0-9a-fA-F]{10,})"),
)
_UPWORK_PROFILE_BLOCK_PATTERNS = (
    re.compile(r"this freelancer'?s profile is only available to upwork customers", re.IGNORECASE),
    re.compile(r"/ab/account-security/login\?redir=", re.IGNORECASE),
    re.compile(r"honeypot do not click", re.IGNORECASE),
    re.compile(r"honey-pot-do-not-click", re.IGNORECASE),
    re.compile(r"captcha", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"sign up to view", re.IGNORECASE),
)
_PROFILE_BEAUTIFY_SYSTEM_PROMPT = (
    "You are an expert Upwork profile editor for freelancer positioning. "
    "Transform raw freelancer notes into clean, professional markdown that can be reused globally "
    "for proposals, docs, and workflow prompts. "
    "Do not fabricate facts, metrics, client names, years, certifications, or tools that are not explicitly present. "
    "If information is missing, write 'Not provided'. "
    "Output markdown only. No code fences."
)
_PROFILE_BEAUTIFY_USER_PROMPT_TEMPLATE = (
    "Beautify and normalize this manual profile text into a reusable global profile markdown.\n\n"
    "Formatting requirements:\n"
    "1. Use these exact sections in this order:\n"
    "# Professional Profile\n"
    "## Headline\n"
    "## Summary\n"
    "## Core Skills\n"
    "## Services\n"
    "## Tools & Platforms\n"
    "## Experience Highlights\n"
    "## Domain Expertise\n"
    "## Portfolio/Case Notes\n"
    "## Communication & Working Style\n"
    "## Availability\n"
    "## Additional Notes\n"
    "2. Use concise bullets where helpful.\n"
    "3. Remove duplicates, noise, and irrelevant text.\n"
    "4. Keep tone professional and human.\n"
    "5. Do not include placeholders like TBD or lorem ipsum.\n"
    "6. If unknown, write 'Not provided'.\n\n"
    "Raw profile text:\n"
    "{raw_text}"
)


def _sanitize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = value if isinstance(value, str) else str(value)
    stripped = normalized.strip()
    return stripped if stripped else None


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = payload.copy()
    for field in _OPTIONAL_TEXT_FIELDS:
        if field in sanitized:
            sanitized[field] = _sanitize_optional_text(sanitized[field])
    return sanitized


def canonicalize_upwork_profile_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        raise AppException(
            status_code=422,
            code="invalid_upwork_profile_url",
            message="Upwork profile URL cannot be empty",
        )

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", candidate):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise AppException(
            status_code=422,
            code="invalid_upwork_profile_url",
            message="Upwork profile URL is invalid",
        )

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.endswith(":443"):
        host = host[:-4]
    if not (host == "upwork.com" or host.endswith(".upwork.com")):
        raise AppException(
            status_code=422,
            code="invalid_upwork_profile_url",
            message="Only Upwork profile URLs are supported",
        )

    path = (parsed.path or "/").rstrip("/")
    if not path:
        path = "/"
    if not (
        path.startswith("/freelancers/")
        or path.startswith("/o/profiles/users/")
        or path.startswith("/~")
    ):
        raise AppException(
            status_code=422,
            code="invalid_upwork_profile_url",
            message="URL does not look like an Upwork profile URL",
        )

    normalized = parsed._replace(
        scheme="https",
        netloc=host,
        path=path,
        params="",
        query="",
        fragment="",
    )
    return urlunparse(normalized)


def extract_upwork_profile_id(url: str) -> str | None:
    for pattern in _UPWORK_PROFILE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _sanitize_extracted_markdown(markdown: str) -> str:
    stripped = markdown.strip()
    if not stripped:
        raise AppException(
            status_code=422,
            code="upwork_profile_markdown_empty",
            message="Extracted Upwork profile markdown is empty",
        )
    return stripped


def validate_upwork_profile_markdown_quality(markdown: str) -> None:
    lowered = markdown.lower()
    for pattern in _UPWORK_PROFILE_BLOCK_PATTERNS:
        if pattern.search(markdown):
            raise AppException(
                status_code=422,
                code="upwork_profile_access_blocked",
                message=(
                    "Unable to extract full Upwork profile content (login/captcha/private access). "
                    "Please paste profile text manually from Upwork."
                ),
                details={"signal": pattern.pattern},
            )

    cat_link_count = len(re.findall(r"\]\(https://www\.upwork\.com/cat/", lowered))
    has_secondary_menu = bool(re.search(r"(?im)^secondary\s*$", markdown))
    if has_secondary_menu and cat_link_count >= 4:
        raise AppException(
            status_code=422,
            code="upwork_profile_content_unreliable",
            message=(
                "Extracted content looks like Upwork navigation shell, not profile data. "
                "Please paste profile text manually from Upwork."
            ),
            details={"signal": "secondary_navigation_shell"},
        )


async def _extract_upwork_profile_markdown(*, canonical_url: str) -> str:
    settings = get_settings()
    try:
        markdown = await extract_markdown_from_url(
            canonical_url,
            api_key=(settings.firecrawl_api_key or "").strip(),
        )
    except FirecrawlExtractionError as exc:
        raise AppException(
            status_code=502,
            code="upwork_profile_extraction_failed",
            message="Failed to extract Upwork profile markdown",
            details={"source_error_code": exc.code, "source_message": exc.message},
        ) from exc
    normalized = _sanitize_extracted_markdown(markdown)
    validate_upwork_profile_markdown_quality(normalized)
    return normalized


async def extract_and_upsert_upwork_profile(
    *,
    session: AsyncSession,
    user_id: UUID,
    upwork_profile_url: str,
    require_existing_profile: bool = False,
) -> UserProfile:
    canonical_url = canonicalize_upwork_profile_url(upwork_profile_url)
    profile = await get_profile_by_user_id(session=session, user_id=user_id)

    if profile is None:
        if require_existing_profile:
            raise AppException(status_code=404, code="profile_not_found", message="User profile not found")
        profile = UserProfile(user_id=user_id)
        session.add(profile)

    profile.upwork_profile_url = canonical_url
    profile.upwork_profile_id = extract_upwork_profile_id(canonical_url)
    await session.commit()
    await session.refresh(profile)

    markdown = await _extract_upwork_profile_markdown(canonical_url=canonical_url)
    profile.upwork_profile_markdown = markdown

    await session.commit()
    await session.refresh(profile)
    return profile


def _sanitize_manual_profile_text(raw_text: str) -> str:
    normalized = raw_text.strip()
    if not normalized:
        raise AppException(
            status_code=422,
            code="invalid_manual_profile_text",
            message="Manual profile text cannot be empty",
        )
    return normalized


async def _beautify_profile_markdown_with_ai(raw_text: str) -> tuple[str, int, int]:
    sanitized = _sanitize_manual_profile_text(raw_text)
    assert_safe_input(content=sanitized, context="profile_manual_text")
    provider = OpenAIProviderAdapter()
    request = ProviderGenerateRequest(
        prompt=_PROFILE_BEAUTIFY_USER_PROMPT_TEMPLATE.format(raw_text=sanitized),
        system_prompt=_PROFILE_BEAUTIFY_SYSTEM_PROMPT,
        model_name="gpt-5.4-mini",
        temperature=0.2,
        max_output_tokens=2200,
        metadata={"task": "profile_beautify_manual"},
    )
    try:
        result = await provider.generate(request)
    except Exception as exc:  # pragma: no cover - provider-level details tested separately
        raise AppException(
            status_code=502,
            code="profile_beautify_failed",
            message="AI profile beautification failed",
            details={"reason": str(exc)},
        ) from exc

    output_text = (result.output_text or "").strip()
    if not output_text:
        raise AppException(
            status_code=422,
            code="profile_beautify_empty_output",
            message="AI returned empty profile markdown",
        )
    assert_safe_output(content=output_text, artifact_type="profile_markdown")
    return output_text, result.input_tokens, result.output_tokens


async def beautify_and_upsert_manual_profile_text(
    *,
    session: AsyncSession,
    user_id: UUID,
    raw_profile_text: str,
) -> tuple[UserProfile, dict[str, int | str]]:
    beautified_markdown, input_tokens, output_tokens = await _beautify_profile_markdown_with_ai(
        raw_profile_text
    )
    profile = await get_profile_by_user_id(session=session, user_id=user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        session.add(profile)

    profile.upwork_profile_markdown = beautified_markdown
    await session.commit()
    await session.refresh(profile)
    return profile, {
        "model_name": "gpt-5.4-mini",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def get_profile_by_user_id(*, session: AsyncSession, user_id: UUID) -> UserProfile | None:
    return await session.scalar(select(UserProfile).where(UserProfile.user_id == user_id))


async def create_profile(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: dict[str, Any],
) -> UserProfile:
    existing_profile = await get_profile_by_user_id(session=session, user_id=user_id)
    if existing_profile:
        raise AppException(
            status_code=409,
            code="profile_already_exists",
            message="User profile already exists",
        )

    sanitized_payload = _sanitize_payload(payload)
    profile = UserProfile(user_id=user_id, **sanitized_payload)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def update_profile(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: dict[str, Any],
) -> UserProfile:
    profile = await get_profile_by_user_id(session=session, user_id=user_id)
    if not profile:
        raise AppException(status_code=404, code="profile_not_found", message="User profile not found")

    sanitized_payload = _sanitize_payload(payload)
    for key, value in sanitized_payload.items():
        setattr(profile, key, value)

    await session.commit()
    await session.refresh(profile)
    return profile


def serialize_profile(profile: UserProfile) -> dict[str, Any]:
    return {
        "id": str(profile.id),
        "user_id": str(profile.user_id),
        "upwork_profile_url": profile.upwork_profile_url,
        "upwork_profile_id": profile.upwork_profile_id,
        "upwork_profile_markdown": profile.upwork_profile_markdown,
        "proposal_template": profile.proposal_template,
        "doc_template": profile.doc_template,
        "loom_template": profile.loom_template,
        "workflow_template_notes": profile.workflow_template_notes,
        "custom_global_instruction": profile.custom_global_instruction,
        "custom_prompt_blocks": profile.custom_prompt_blocks,
    }
