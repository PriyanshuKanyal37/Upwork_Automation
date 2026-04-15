from __future__ import annotations

from dataclasses import dataclass
import re

from app.application.ai.contracts import ProviderGenerateRequest
from app.application.ai.guardrails import assert_safe_input, assert_safe_output
from app.application.ai.providers.base import AIProviderAdapter
from app.infrastructure.ai.providers.factory import build_provider_adapter
from app.infrastructure.ai.providers.openai_provider import OpenAIProviderAdapter

_CODE_FENCE_PATTERN = re.compile(r"^```(?:markdown)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_WHITESPACE_PATTERN = re.compile(r"\s+")

_DEFAULT_MODEL = "gpt-5.4-mini"
_TOOL_KEYWORDS = (
    "n8n",
    "make.com",
    "integromat",
    "gohighlevel",
    "ghl",
    "zapier",
    "openai",
    "python",
    "crm",
    "api",
    "webhook",
)

_SYSTEM_PROMPT = (
    "You are a senior freelancer advisor helping a user understand an Upwork job posting clearly. "
    "Your goal is not to paraphrase blindly, but to explain what the client actually needs, "
    "what work is likely required, what risks exist, and how the freelancer should respond. "
    "Keep the explanation concise and easy to scan. "
    "Use simple words, short sentences, and practical language. "
    "Use a few relevant emojis naturally to improve readability (do not overuse). "
    "Use only information from the provided job markdown and user notes. "
    "Never invent requirements, tools, budget, timeline, or client details. "
    "If something is missing, say it is not specified. "
    "Optimize for comprehension: use the format that best fits the content "
    "(paragraphs, bullets, headings, or a mix). "
    "Do not force a fixed number of paragraphs or bullets. "
    "Target roughly 140 to 220 words unless the job is unusually complex."
)


@dataclass(frozen=True)
class JobExplanationExecution:
    explanation: str
    used_fallback: bool
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _truncate_words(text: str, max_words: int) -> str:
    words = [part for part in _WHITESPACE_PATTERN.split(text.strip()) if part]
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def _normalize_text(value: str) -> str:
    stripped = _CODE_FENCE_PATTERN.sub("", value.strip()).strip()
    return _WHITESPACE_PATTERN.sub(" ", stripped).strip()


def _ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "Not clearly specified in the post."
    if stripped[-1] not in ".!?":
        stripped += "."
    return stripped


def _extract_context_snippet(job_markdown: str) -> str:
    cleaned = re.sub(r"[#`*_>\[\]\(\)]", " ", job_markdown)
    snippet = _truncate_words(_normalize_text(cleaned), 80)
    return snippet or "the client needs help with a specific project scope"


def _extract_tools(job_markdown: str, notes_markdown: str | None) -> str:
    lowered = f"{job_markdown}\n{notes_markdown or ''}".lower()
    seen: list[str] = []
    for keyword in _TOOL_KEYWORDS:
        if keyword in lowered:
            display = "Make.com" if keyword in {"make.com", "integromat"} else keyword.upper() if keyword == "api" else keyword
            if display not in seen:
                seen.append(display)
    if not seen:
        return "Not clearly specified in the post"
    return ", ".join(seen)


def _extract_budget_or_timeline(job_markdown: str, notes_markdown: str | None) -> str:
    source = f"{job_markdown}\n{notes_markdown or ''}"
    budget = re.search(r"\$[\d,]+(?:\.\d{1,2})?(?:\s*(?:-|to)\s*\$[\d,]+(?:\.\d{1,2})?)?", source, re.IGNORECASE)
    timeline = re.search(
        r"(?:\d+\s*(?:day|days|week|weeks|month|months|year|years)|as needed|less than\s+\d+\s*hrs?/week)",
        source,
        re.IGNORECASE,
    )
    parts: list[str] = []
    if budget:
        parts.append(f"Budget hint: {budget.group(0)}")
    if timeline:
        parts.append(f"Timeline or availability hint: {timeline.group(0)}")
    if not parts:
        return "Budget or timeline details are not clearly specified"
    return " | ".join(parts)


def build_fallback_job_explanation(*, job_markdown: str, notes_markdown: str | None = None) -> str:
    snippet = _extract_context_snippet(job_markdown)
    tools = _extract_tools(job_markdown, notes_markdown)
    constraints = _extract_budget_or_timeline(job_markdown, notes_markdown)
    notes_hint = _truncate_words(_normalize_text(notes_markdown or ""), 22) if notes_markdown else ""

    sections = [
        f"🧠 Quick summary: {_ensure_sentence(_truncate_words(snippet, 32))}",
        f"- 🎯 Client goal: {_ensure_sentence(_truncate_words(snippet, 20))}",
        "- 🧩 Scope: Build a practical automation workflow with clear steps and usable handoff.",
        f"- 🛠️ Likely tools/skills: {_ensure_sentence(_truncate_words(tools, 18))}",
        f"- ⏱️ Constraints: {_ensure_sentence(_truncate_words(constraints, 18))}",
        (
            "- ✅ Proposal angle: Confirm assumptions early, define milestones, "
            "and emphasize reliability plus maintainability."
        ),
    ]
    if notes_hint:
        sections.append(f"- 📝 Notes to include: {_ensure_sentence(_truncate_words(notes_hint, 16))}")
    return "\n\n".join(sections)


def _normalize_ai_explanation(raw_text: str) -> str:
    stripped = _CODE_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    if not stripped:
        raise ValueError("empty explanation")

    lines = [line.rstrip() for line in stripped.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    collapsed_lines: list[str] = []
    previous_blank = False
    for line in lines:
        normalized_line = line.strip()
        if not normalized_line:
            if not previous_blank:
                collapsed_lines.append("")
            previous_blank = True
            continue
        collapsed_lines.append(normalized_line)
        previous_blank = False

    normalized = "\n".join(collapsed_lines).strip()
    if len(normalized) < 60:
        raise ValueError("explanation too short")
    return normalized


def _build_user_prompt(*, job_markdown: str, notes_markdown: str | None) -> str:
    notes_block = notes_markdown.strip() if notes_markdown and notes_markdown.strip() else "None"
    return (
        "Explain this Upwork job so a freelancer can understand it quickly and accurately.\n"
        "Focus on practical understanding, not fluff.\n"
        "Keep it concise, easy to read, and useful for action.\n\n"
        "What to cover:\n"
        "- Core objective: what the client is truly trying to achieve.\n"
        "- Scope: what work is likely in and out of scope.\n"
        "- Deliverables: what outcomes the client likely expects.\n"
        "- Skills/tools implied by the post.\n"
        "- Constraints, unknowns, and risks.\n"
        "- Proposal strategy: what to clarify and how to position the response.\n\n"
        "Output rules:\n"
        "- Use plain text.\n"
        "- Use any structure that best explains the job (headings, bullets, paragraphs, or mixed).\n"
        "- Do not force a fixed number of paragraphs or bullet points.\n"
        "- Use simple language a non-technical freelancer can scan quickly.\n"
        "- Target around 140 to 220 words for most jobs.\n"
        "- Use 3 to 7 relevant emojis naturally for readability.\n"
        "- Stay grounded strictly in provided content. If details are missing, explicitly say not specified.\n\n"
        f"Job markdown:\n{job_markdown}\n\n"
        f"User notes:\n{notes_block}"
    )


async def explain_job_markdown(
    *,
    job_markdown: str,
    notes_markdown: str | None = None,
    provider: AIProviderAdapter | None = None,
) -> JobExplanationExecution:
    assert_safe_input(content=job_markdown, context="job_markdown_for_explanation")
    if notes_markdown:
        assert_safe_input(content=notes_markdown, context="job_notes_for_explanation")

    adapter = provider or build_provider_adapter(OpenAIProviderAdapter.provider)
    request = ProviderGenerateRequest(
        prompt=_build_user_prompt(job_markdown=job_markdown, notes_markdown=notes_markdown),
        system_prompt=_SYSTEM_PROMPT,
        model_name=_DEFAULT_MODEL,
        temperature=0.15,
        max_output_tokens=700,
        metadata={"task": "job_explanation"},
    )
    try:
        result = await adapter.generate(request)
        normalized = _normalize_ai_explanation(result.output_text or "")
        assert_safe_output(content=normalized, artifact_type="job_explanation")
        return JobExplanationExecution(
            explanation=normalized,
            used_fallback=False,
            model_name=result.model_name,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
    except Exception:
        fallback = build_fallback_job_explanation(
            job_markdown=job_markdown,
            notes_markdown=notes_markdown,
        )
        return JobExplanationExecution(
            explanation=fallback,
            used_fallback=True,
            model_name=_DEFAULT_MODEL,
        )
