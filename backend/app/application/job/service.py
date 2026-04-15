import json
import re
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.contracts import ProviderGenerateRequest, JobClassification
from app.application.ai.job_classifier_service import classify_job
from app.application.ai.job_explanation_service import explain_job_markdown
from app.application.ai.errors import AIException
from app.infrastructure.ai.providers.openai_provider import OpenAIProviderAdapter
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.user_connector import UserConnector
from app.infrastructure.audit.events import log_status_change
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.integrations.firecrawl_client import (
    FirecrawlExtractionError,
    extract_markdown_bundle_from_url,
)

_UPWORK_JOB_ID_PATTERNS = (
    re.compile(r"/~([0-9a-fA-F]{10,})"),
    re.compile(r"/jobs/[^/?#]*~([0-9a-fA-F]{10,})"),
    re.compile(r"[?&]jobId=([A-Za-z0-9_-]{4,})"),
    re.compile(r"/job/([0-9]{4,})"),
    re.compile(r"/jobs/([0-9]{4,})"),
)
_UPWORK_URL_CANDIDATE_PATTERN = re.compile(
    r"((?:https?://|www\.)[^\s<>\"]*upwork\.com[^\s<>\"]*|upwork\.com[^\s<>\"]+)",
    re.IGNORECASE,
)
_TRAILING_NOISE = ".,;:!?)\"]}'"
_FIRECRAWL_CREDENTIAL_PREFIX = "firecrawl://"
_UPWORK_APPLY_PATH_PATTERN = re.compile(
    r"^/nx/proposals/job/~?([0-9a-fA-F]{10,})/apply/?$",
    re.IGNORECASE,
)
_UPWORK_SUMMARY_HEADERS = {"summary", "**summary**", "## summary", "### summary"}
_UPWORK_TAIL_CUT_MARKERS = (
    "explore similar jobs on upwork",
    "other open jobs by this client",
    "explore upwork opportunities for free",
    "how it works",
    "about upwork",
    "find the best freelance jobs",
    "footer navigation",
)
_UPWORK_NOISE_LINE_MARKERS = (
    "honey-pot-do-not-click",
    "create your free profile",
    "work the way you want",
    "get paid securely",
    "want to get started?",
    "trusted by",
    "watch a demo",
)
_UPWORK_RESTRICTED_CONTENT_MARKERS = (
    "this job is a private listing",
    "want to browse more freelancer jobs?",
    "log in to upwork",
    "continue with google",
    "continue with apple",
    "cloudflare ray id",
    "# challenge",
    "please verify you are human",
    "captcha",
)
_UPWORK_NAVIGATION_HEAVY_MARKERS = (
    "hire freelancers",
    "find work",
    "why upwork",
    "what’s new",
    "what's new",
    "footer navigation",
    "for clients",
    "for talent",
    "resources",
    "company",
    "follow us",
    "mobile app",
)
_UPWORK_JOB_SIGNAL_MARKERS = (
    "summary",
    "skills and expertise",
    "about the client",
    "activity on this job",
    "posted",
    "hourly",
    "fixed-price",
    "duration",
    "experience level",
    "project type",
    "proposals:",
    "interviewing:",
)
_UPWORK_NON_JOB_H1_MARKERS = {
    "log in to upwork",
    "upwork",
}
_UPWORK_PRE_SUMMARY_METADATA_PATTERNS = (
    re.compile(r"^posted\b", re.IGNORECASE),
    re.compile(r"^worldwide$", re.IGNORECASE),
    re.compile(r"^hourly$", re.IGNORECASE),
    re.compile(r"^fixed-price$", re.IGNORECASE),
    re.compile(r"^\$[\d,]+(?:\.\d{2})?(?:\s*(?:-|to)\s*\$[\d,]+(?:\.\d{2})?)?$", re.IGNORECASE),
    re.compile(r"^(?:less than|more than|as needed|\d+\+?)\s+.*(?:hrs?|hours?)\s*/\s*week$", re.IGNORECASE),
    re.compile(r"^[<>]?\s*\d+\s*(?:day|days|week|weeks|month|months|year|years)$", re.IGNORECASE),
    re.compile(
        r"^\d+\s+to\s+\d+\s+(?:day|days|week|weeks|month|months|year|years)$",
        re.IGNORECASE,
    ),
    re.compile(r"^duration$", re.IGNORECASE),
    re.compile(r"^experience level$", re.IGNORECASE),
    re.compile(r"^(?:entry|intermediate|expert)\b", re.IGNORECASE),
    re.compile(r"^project type$", re.IGNORECASE),
    re.compile(r"^(?:one-time project|ongoing project|complex project)$", re.IGNORECASE),
)
_POSTED_FROM_TITLE_PATTERN = re.compile(
    r",\s*posted\s+(.+?)\s*-\s*upwork\s*$",
    re.IGNORECASE,
)
_MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\([^)]+\)")
_H1_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ExtractionQualityAssessment:
    accepted: bool
    reasons: list[str]
    score: int


def canonicalize_job_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        raise AppException(status_code=422, code="invalid_job_url", message="Job URL cannot be empty")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", candidate):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise AppException(status_code=422, code="invalid_job_url", message="Job URL is invalid")

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.endswith(":443"):
        host = host[:-4]
    if not (host == "upwork.com" or host.endswith(".upwork.com")):
        raise AppException(
            status_code=422,
            code="invalid_job_url",
            message="Only Upwork job URLs are supported",
        )

    path = parsed.path or "/"
    apply_match = _UPWORK_APPLY_PATH_PATTERN.match(path)
    if apply_match:
        upwork_job_id = apply_match.group(1)
        path = f"/jobs/~{upwork_job_id}"
    if path != "/":
        path = path.rstrip("/")
    normalized = parsed._replace(scheme="https", netloc=host, path=path, params="", query="", fragment="")
    return urlunparse(normalized)


def extract_upwork_job_id(url: str) -> str | None:
    for pattern in _UPWORK_JOB_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _parse_json_dict(raw_text: str) -> dict[str, Any] | None:
    content = raw_text.strip()
    if not content:
        return None
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _candidate_url_inputs(raw_input: str) -> list[str]:
    cleaned = raw_input.strip()
    if not cleaned:
        return []

    candidates = [cleaned]
    for match in _UPWORK_URL_CANDIDATE_PATTERN.finditer(raw_input):
        candidate = match.group(1).strip().rstrip(_TRAILING_NOISE)
        if candidate:
            candidates.append(candidate)
    return list(dict.fromkeys(candidates))


def _looks_like_standalone_url(raw_input: str) -> bool:
    stripped = raw_input.strip()
    if not stripped or " " in stripped:
        return False
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", stripped):
        return True
    if stripped.startswith("www."):
        return True
    parsed = urlparse(f"https://{stripped}")
    return bool(parsed.netloc and "." in parsed.netloc)


async def _resolve_job_url_with_llm(raw_input: str) -> str | None:
    settings = get_settings()
    if not settings.ai_enable_job_url_llm_fallback:
        return None
    if not settings.openai_api_key:
        return None

    provider = OpenAIProviderAdapter()
    request = ProviderGenerateRequest(
        model_name=settings.ai_job_url_parser_model,
        system_prompt=(
            "You extract only valid Upwork job URLs. Return strict JSON with keys: "
            "normalized_url, upwork_job_id, confidence. No extra text."
        ),
        prompt=(
            "Input from user:\n"
            f"{raw_input}\n\n"
            "Rules:\n"
            "- Find one Upwork job URL.\n"
            "- normalized_url must be full https URL.\n"
            "- confidence must be high|medium|low.\n"
            "- If unsure, return empty normalized_url and confidence=low.\n"
            "Return JSON only."
        ),
        temperature=0.0,
        max_output_tokens=settings.ai_job_url_parser_max_output_tokens,
    )
    try:
        result = await provider.generate(request)
    except AIException:
        return None
    parsed = _parse_json_dict(result.output_text or "")
    if not parsed:
        return None

    normalized_url = str(parsed.get("normalized_url") or "").strip()
    confidence = str(parsed.get("confidence") or "").strip().lower()
    if not normalized_url or confidence not in {"high", "medium"}:
        return None

    try:
        return canonicalize_job_url(normalized_url)
    except AppException:
        return None


async def resolve_job_url_for_intake(raw_input: str) -> str:
    first_error: AppException | None = None
    for candidate in _candidate_url_inputs(raw_input):
        try:
            return canonicalize_job_url(candidate)
        except AppException as exc:
            first_error = exc

    if first_error and _looks_like_standalone_url(raw_input):
        raise first_error

    llm_url = await _resolve_job_url_with_llm(raw_input)
    if llm_url:
        return llm_url

    if first_error:
        raise first_error
    raise AppException(status_code=422, code="invalid_job_url", message="Job URL is invalid")


def _base_duplicate_query(*, current_user_id: UUID) -> Select[tuple[Job]]:
    return select(Job).where(Job.user_id != current_user_id)


async def find_duplicates(
    *,
    session: AsyncSession,
    current_user_id: UUID,
    upwork_job_id: str | None,
    canonical_url: str,
) -> list[Job]:
    query = _base_duplicate_query(current_user_id=current_user_id)
    if upwork_job_id:
        query = query.where(Job.upwork_job_id == upwork_job_id)
    else:
        query = query.where(Job.job_url == canonical_url)
    results = await session.scalars(query.order_by(Job.created_at.desc()))
    return list(results)


async def find_duplicate_names(
    *,
    session: AsyncSession,
    current_user_id: UUID,
    upwork_job_id: str | None,
    canonical_url: str,
) -> list[str]:
    query = select(User.display_name).join(Job, Job.user_id == User.id).where(Job.user_id != current_user_id)
    if upwork_job_id:
        query = query.where(Job.upwork_job_id == upwork_job_id)
    else:
        query = query.where(Job.job_url == canonical_url)
    results = await session.scalars(query.distinct())
    return list(results)


def _sanitize_notes(notes_markdown: str | None) -> str | None:
    if notes_markdown is None:
        return None
    stripped = notes_markdown.strip()
    return stripped if stripped else None


def _sanitize_markdown(markdown: str) -> str:
    stripped = markdown.strip()
    if not stripped:
        raise AppException(
            status_code=422,
            code="invalid_job_markdown",
            message="Job markdown cannot be empty",
        )
    return stripped


def _derive_job_title_from_metadata(metadata: dict[str, Any]) -> str | None:
    title_candidates = (
        metadata.get("og:title"),
        metadata.get("ogTitle"),
        metadata.get("twitter:title"),
        metadata.get("title"),
    )
    for value in title_candidates:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not candidate:
            continue
        posted_match = _POSTED_FROM_TITLE_PATTERN.search(candidate)
        if posted_match:
            candidate = candidate[: posted_match.start()].strip()
        for marker in (" - Freelance Job in ", " - Upwork"):
            if marker.lower() in candidate.lower():
                split_idx = candidate.lower().find(marker.lower())
                candidate = candidate[:split_idx].strip()
                break
        if candidate:
            return candidate
    return None


def _derive_posted_from_metadata(metadata: dict[str, Any]) -> str | None:
    title_candidates = (
        metadata.get("og:title"),
        metadata.get("ogTitle"),
        metadata.get("twitter:title"),
        metadata.get("title"),
    )
    for value in title_candidates:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not candidate:
            continue
        match = _POSTED_FROM_TITLE_PATTERN.search(candidate)
        if match:
            posted_value = match.group(1).strip().rstrip(".,;")
            if posted_value:
                return posted_value
    return None


def _derive_hero_image_from_metadata(metadata: dict[str, Any]) -> str | None:
    image_candidates = (
        metadata.get("og:image"),
        metadata.get("ogImage"),
        metadata.get("twitter:image"),
    )
    for value in image_candidates:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate
    return None


def _enrich_markdown_with_metadata(markdown: str, metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict) or not markdown.strip():
        return markdown.strip()

    lines = markdown.splitlines()
    has_h1 = any(line.strip().startswith("# ") for line in lines)
    has_posted = any(line.strip().lower().startswith("posted ") for line in lines)
    has_hero = any(line.strip().lower().startswith("hero image: ") for line in lines)

    prefix: list[str] = []
    if not has_h1:
        title = _derive_job_title_from_metadata(metadata)
        if title:
            prefix.append(f"# {title}")
    if not has_posted:
        posted = _derive_posted_from_metadata(metadata)
        if posted:
            prefix.append(f"Posted {posted}")
    if not has_hero:
        hero = _derive_hero_image_from_metadata(metadata)
        if hero:
            prefix.append(f"Hero image: {hero}")

    if not prefix:
        return markdown.strip()

    return "\n".join(prefix + ["", markdown.strip()]).strip()


def _clean_firecrawl_job_markdown(markdown: str, metadata: dict[str, Any] | None = None) -> str:
    # Keep extraction deterministic and lightweight: trim known boilerplate blocks and
    # preserve the core job payload (summary, budget, skills, activity, client).
    lines = markdown.splitlines()
    normalized = [line.rstrip() for line in lines]

    summary_idx: int | None = None
    for idx, line in enumerate(normalized):
        candidate = line.strip().lower()
        if candidate in _UPWORK_SUMMARY_HEADERS:
            summary_idx = idx
            break

    title_idx: int | None = None
    title_search_limit = summary_idx if summary_idx is not None else min(len(normalized), 200)
    for idx, line in enumerate(normalized[:title_search_limit]):
        stripped = line.strip()
        if not stripped.startswith("# "):
            continue
        heading = stripped[2:].strip().lower()
        if not heading:
            continue
        if heading in _UPWORK_NON_JOB_H1_MARKERS:
            continue
        title_idx = idx
        break

    if title_idx is not None:
        normalized = normalized[title_idx:]
    elif summary_idx is not None and summary_idx > 0:
        window_start = max(0, summary_idx - 40)
        window = normalized[window_start:summary_idx]

        preserved_preamble: list[str] = []
        for idx, line in enumerate(window):
            stripped = line.strip()
            lowered = stripped.lower()
            compact = stripped.lstrip("-* ").strip().strip("*").strip()
            if not stripped:
                continue
            if any(
                pattern.match(candidate)
                for candidate in (stripped, compact)
                for pattern in _UPWORK_PRE_SUMMARY_METADATA_PATTERNS
            ):
                # If line is "Posted ...", also preserve a likely title right above it.
                if (lowered.startswith("posted") or compact.lower().startswith("posted")) and idx > 0:
                    candidate_title = window[idx - 1].strip()
                    if (
                        candidate_title
                        and "http" not in candidate_title.lower()
                        and not candidate_title.startswith(("-", "["))
                        and len(candidate_title) <= 180
                    ):
                        preserved_preamble.append(candidate_title)
                preserved_preamble.append(stripped)

        if preserved_preamble:
            deduped: list[str] = []
            for item in preserved_preamble:
                if not deduped or deduped[-1] != item:
                    deduped.append(item)
            normalized = deduped + [""] + normalized[summary_idx:]
        else:
            normalized = normalized[summary_idx:]

    tail_idx: int | None = None
    for idx, line in enumerate(normalized):
        candidate = line.strip().lower()
        if any(marker in candidate for marker in _UPWORK_TAIL_CUT_MARKERS):
            tail_idx = idx
            break
    if tail_idx is not None:
        normalized = normalized[:tail_idx]

    filtered: list[str] = []
    for line in normalized:
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith("!["):
            continue
        if any(marker in lowered for marker in _UPWORK_NOISE_LINE_MARKERS):
            continue
        filtered.append(line)

    collapsed: list[str] = []
    previous_blank = False
    for line in filtered:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = is_blank

    cleaned = "\n".join(collapsed).strip()
    return _enrich_markdown_with_metadata(cleaned, metadata)


def _is_restricted_or_non_job_markdown(markdown: str) -> bool:
    lowered = markdown.lower()
    return any(marker in lowered for marker in _UPWORK_RESTRICTED_CONTENT_MARKERS)


def _assess_extracted_job_markdown_quality(markdown: str) -> ExtractionQualityAssessment:
    text = markdown.strip()
    lowered = text.lower()
    reasons: list[str] = []

    if not text:
        return ExtractionQualityAssessment(accepted=False, reasons=["empty_markdown"], score=-99)

    if _is_restricted_or_non_job_markdown(text):
        reasons.append("restricted_or_challenge_page")
        return ExtractionQualityAssessment(accepted=False, reasons=reasons, score=-50)

    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    link_count = len(_MARKDOWN_LINK_PATTERN.findall(text))
    nav_hits = sum(1 for marker in _UPWORK_NAVIGATION_HEAVY_MARKERS if marker in lowered)
    signal_hits = sum(1 for marker in _UPWORK_JOB_SIGNAL_MARKERS if marker in lowered)

    score = 0
    h1_matches = _H1_PATTERN.findall(text)
    if h1_matches:
        first_h1 = h1_matches[0].strip().lower()
        if first_h1 and first_h1 not in _UPWORK_NON_JOB_H1_MARKERS:
            score += 2
        else:
            score -= 1
    else:
        score -= 1
        reasons.append("missing_h1")

    if signal_hits >= 2:
        score += 3
    elif signal_hits == 1:
        score += 1
    else:
        reasons.append("missing_job_sections")

    if word_count >= 80:
        score += 2
    elif word_count >= 15:
        score += 1
    else:
        score -= 2
        reasons.append("too_short")

    if nav_hits >= 3:
        score -= 3
        reasons.append("navigation_heavy_content")
    elif nav_hits == 2:
        score -= 1

    if link_count >= 20:
        score -= 2
        reasons.append("link_heavy_content")
    elif link_count >= 12:
        score -= 1

    if word_count < 240 and link_count >= 12 and signal_hits < 2:
        reasons.append("mostly_navigation_links")
        return ExtractionQualityAssessment(accepted=False, reasons=reasons, score=score - 3)

    accepted = score >= 2
    if not accepted and not reasons:
        reasons.append("low_quality_score")
    return ExtractionQualityAssessment(accepted=accepted, reasons=reasons, score=score)


def _extract_firecrawl_api_key(credential_ref: str) -> str | None:
    value = credential_ref.strip()
    if not value.lower().startswith(_FIRECRAWL_CREDENTIAL_PREFIX):
        return None
    api_key = value[len(_FIRECRAWL_CREDENTIAL_PREFIX) :].strip()
    return api_key or None


async def _resolve_firecrawl_api_key_for_user(*, session: AsyncSession, user_id: UUID) -> str | None:
    connector_ref = await session.scalar(
        select(UserConnector.credential_ref).where(
            UserConnector.user_id == user_id,
            UserConnector.connector_name == "firecrawl",
            UserConnector.status == "connected",
        )
    )
    if isinstance(connector_ref, str):
        parsed = _extract_firecrawl_api_key(connector_ref)
        if parsed:
            return parsed

    return None


async def create_job_intake(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_url: str,
    notes_markdown: str | None,
    project_id: UUID | None = None,
) -> tuple[Job, list[Job], list[str]]:
    canonical_url = await resolve_job_url_for_intake(job_url)
    upwork_job_id = extract_upwork_job_id(canonical_url)

    duplicates = await find_duplicates(
        session=session,
        current_user_id=user_id,
        upwork_job_id=upwork_job_id,
        canonical_url=canonical_url,
    )

    status = "duplicate_notified" if duplicates else "draft"
    job = Job(
        user_id=user_id,
        project_id=project_id,
        job_url=canonical_url,
        upwork_job_id=upwork_job_id,
        notes_markdown=_sanitize_notes(notes_markdown),
        requires_manual_markdown=False,
        extraction_error=None,
        status=status,
    )

    duplicate_names = []
    if duplicates:
        duplicate_names = await find_duplicate_names(
            session=session,
            current_user_id=user_id,
            upwork_job_id=upwork_job_id,
            canonical_url=canonical_url,
        )

    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job, duplicates, duplicate_names


async def get_job_for_user(*, session: AsyncSession, user_id: UUID, job_id: UUID) -> Job:
    job = await session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise AppException(status_code=404, code="job_not_found", message="Job not found")
    return job


async def mark_job_processing(*, session: AsyncSession, job: Job) -> Job:
    previous_status = job.status
    job.status = "processing"
    job.requires_manual_markdown = False
    job.extraction_error = None
    await session.commit()
    await session.refresh(job)
    log_status_change(
        entity="job",
        entity_id=job.id,
        user_id=job.user_id,
        previous_status=previous_status,
        next_status=job.status,
        source="mark_job_processing",
    )
    return job


def _persist_job_classification_attributes(job: Job, classification: JobClassification) -> None:
    job.job_type = classification.job_type.value
    automation_platform_value = (
        classification.automation_platform.value
        if classification.automation_platform is not None
        else None
    )
    job.automation_platform = automation_platform_value
    # Keep platform_detected in sync with the classification result so the
    # indexed column reflects the actual detected platform instead of the
    # hardcoded "n8n" server default it was created with.
    job.platform_detected = automation_platform_value or "none"
    job.classification_confidence = classification.confidence
    job.classification_reasoning = classification.reasoning
    job.classified_at = datetime.now(UTC)


async def mark_job_ready(*, session: AsyncSession, job: Job, job_markdown: str) -> Job:
    previous_status = job.status
    sanitized_markdown = _sanitize_markdown(job_markdown)
    job.job_markdown = sanitized_markdown
    job.status = "ready"
    job.requires_manual_markdown = False
    job.extraction_error = None

    classification_exec = await classify_job(
        job_markdown=sanitized_markdown,
        notes_markdown=job.notes_markdown,
    )
    _persist_job_classification_attributes(job, classification_exec.classification)
    explanation_exec = await explain_job_markdown(
        job_markdown=sanitized_markdown,
        notes_markdown=job.notes_markdown,
    )
    job.job_explanation = explanation_exec.explanation

    await session.commit()
    await session.refresh(job)
    log_status_change(
        entity="job",
        entity_id=job.id,
        user_id=job.user_id,
        previous_status=previous_status,
        next_status=job.status,
        source="mark_job_ready",
    )
    return job


async def mark_job_failed(*, session: AsyncSession, job: Job, message: str) -> Job:
    previous_status = job.status
    job.status = "failed"
    job.requires_manual_markdown = True
    job.extraction_error = message
    await session.commit()
    await session.refresh(job)
    log_status_change(
        entity="job",
        entity_id=job.id,
        user_id=job.user_id,
        previous_status=previous_status,
        next_status=job.status,
        source="mark_job_failed",
        metadata={"reason": message},
    )
    return job


async def save_manual_job_markdown(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    job_markdown: str,
) -> Job:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    if job.status == "duplicate_notified":
        raise AppException(
            status_code=409,
            code="duplicate_decision_required",
            message="Please take duplicate decision before updating job markdown",
        )
    return await mark_job_ready(session=session, job=job, job_markdown=job_markdown)


async def regenerate_job_explanation(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
) -> tuple[Job, bool]:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    if not job.job_markdown or not job.job_markdown.strip():
        raise AppException(
            status_code=422,
            code="job_markdown_missing",
            message="Job markdown is required before generating explanation",
        )

    explanation_exec = await explain_job_markdown(
        job_markdown=job.job_markdown.strip(),
        notes_markdown=job.notes_markdown,
    )
    job.job_explanation = explanation_exec.explanation
    await session.commit()
    await session.refresh(job)
    return job, explanation_exec.used_fallback


async def prepare_job_extraction(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
) -> Job:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    if job.status == "duplicate_notified":
        raise AppException(
            status_code=409,
            code="duplicate_decision_required",
            message="Please take duplicate decision before extraction",
        )
    if job.status == "processing":
        raise AppException(
            status_code=409,
            code="job_already_processing",
            message="Job extraction is already running",
        )
    return await mark_job_processing(session=session, job=job)


async def execute_job_extraction(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    retryable_errors: bool = False,
) -> Job:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    if job.status != "processing":
        job = await mark_job_processing(session=session, job=job)

    firecrawl_api_key = await _resolve_firecrawl_api_key_for_user(session=session, user_id=user_id)
    try:
        extracted = await extract_markdown_bundle_from_url(job.job_url, api_key=firecrawl_api_key)
    except FirecrawlExtractionError as exc:
        if retryable_errors and exc.retryable:
            raise
        message = "Firecrawl failed. Please paste the job text manually."
        return await mark_job_failed(session=session, job=job, message=message)

    cleaned_markdown = _clean_firecrawl_job_markdown(
        extracted.markdown,
        metadata=extracted.metadata,
    )
    quality = _assess_extracted_job_markdown_quality(cleaned_markdown)
    if not quality.accepted:
        reason_text = ", ".join(quality.reasons) if quality.reasons else "low_quality_extraction"
        return await mark_job_failed(
            session=session,
            job=job,
            message=(
                "Firecrawl extraction quality check failed "
                f"({reason_text}). Please paste the job text manually."
            ),
        )
    return await mark_job_ready(session=session, job=job, job_markdown=cleaned_markdown)


async def update_duplicate_decision(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    action: str,
) -> Job:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    if job.status != "duplicate_notified":
        raise AppException(
            status_code=409,
            code="duplicate_decision_not_required",
            message="Duplicate decision is not required for this job",
        )

    if action == "continue":
        previous_status = job.status
        job.status = "draft"
    elif action == "stop":
        previous_status = job.status
        job.status = "closed"
        job.outcome = "not_sent"
    else:
        raise AppException(status_code=422, code="invalid_duplicate_action", message="Invalid action")

    await session.commit()
    await session.refresh(job)
    log_status_change(
        entity="job",
        entity_id=job.id,
        user_id=job.user_id,
        previous_status=previous_status,
        next_status=job.status,
        source="update_duplicate_decision",
        metadata={"action": action},
    )
    return job


def serialize_job(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "user_id": str(job.user_id),
        "project_id": str(job.project_id) if job.project_id else None,
        "job_url": job.job_url,
        "upwork_job_id": job.upwork_job_id,
        "notes_markdown": job.notes_markdown,
        "job_markdown": job.job_markdown,
        "job_explanation": job.job_explanation,
        "extraction_error": job.extraction_error,
        "requires_manual_markdown": job.requires_manual_markdown,
        "status": job.status,
        "plan_approved": job.plan_approved,
        "is_submitted_to_upwork": job.is_submitted_to_upwork,
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
        "outcome": job.outcome,
        "job_type": job.job_type,
        "automation_platform": job.automation_platform,
        "classification_confidence": job.classification_confidence,
        "classification_reasoning": job.classification_reasoning,
        "classified_at": job.classified_at.isoformat() if job.classified_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
