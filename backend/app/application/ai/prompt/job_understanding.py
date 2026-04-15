"""Universal job understanding prompt.

This prompt is the single extraction pass that runs on every incoming Upwork
job, across automation, AI/ML, web dev, mobile, data, design, writing,
marketing, and other categories. It is deliberately platform-agnostic in
structure: the same JSON schema is returned for every job, only the field
values differ.

The downstream planner consumes `automation_platform_preference` to decide
which workflow generator (if any) to invoke:
- "n8n" → n8n agent
- "make" → Make.com agent
- "ghl"  → GoHighLevel build-spec agent
- "both" / "unknown" → n8n (default) with user confirmation
- anything else → workflow generation is skipped

Schema note: we keep the exact field names used by JobUnderstandingContract
so existing code, tests, and DB persistence continue to work unchanged. The
universal-ness is expressed through the DECISION RULES, not new fields.
"""
from __future__ import annotations

from app.application.ai.prompt.common import normalize_optional_section

PROMPT_VERSION = "job_understanding_v3"
SYSTEM_PROMPT = (
    "You are a senior Upwork job analyst. Your job is to read any incoming "
    "Upwork post — regardless of category — and extract a precise, structured "
    "understanding of what the client wants. You work across automation, AI/ML, "
    "web development, mobile development, data engineering, design, writing, "
    "marketing, and other categories. "
    "You return STRICT JSON ONLY — no markdown, no prose, no code fences, no "
    "commentary outside the JSON object. "
    "You prefer factual extraction over interpretation. You never invent "
    "constraints, deliverables, or platform preferences that are not supported "
    "by the job text."
)


def build_user_prompt(
    *,
    job_markdown: str,
    notes_markdown: str | None = None,
    profile_context: str | None = None,
) -> str:
    notes_section = normalize_optional_section(notes_markdown)
    profile_section = normalize_optional_section(profile_context)

    return (
        "# TASK\n"
        "Analyze the Upwork job post below and return ONE JSON object matching "
        "the schema. This is a universal extraction — it must work for any job "
        "category, not just automation.\n\n"
        "# OUTPUT SCHEMA (return exactly these keys, nothing else)\n"
        "{\n"
        '  "summary_short": "string (<= 90 words, factual summary of what the client wants)",\n'
        '  "deliverables_required": ["proposal" | "cover_letter" | "loom_script" | "workflow" | "doc"],\n'
        '  "screening_questions": ["string"],\n'
        '  "automation_platform_preference": "n8n" | "make" | "ghl" | "both" | "unknown",\n'
        '  "constraints": {\n'
        '    "tone": "string or null",\n'
        '    "budget": "string or null",\n'
        '    "deadline": "string or null",\n'
        '    "tools": ["string"],\n'
        '    "must_haves": ["string"],\n'
        '    "disallowed": ["string"],\n'
        '    "experience_level": "string or null"\n'
        "  },\n"
        '  "extraction_confidence": "high" | "medium" | "low",\n'
        '  "missing_fields": ["string"]\n'
        "}\n\n"
        "# DECISION RULES (apply in order; first match wins)\n\n"
        "## Platform preference detection\n"
        "The `automation_platform_preference` field is OPTIONAL SIGNAL — it "
        "only applies when the job involves building an automation / workflow. "
        "For non-automation jobs (AI/ML, web dev, mobile, data, design, "
        "writing, marketing, other) set it to `unknown`.\n\n"
        "When the job IS about building an automation:\n"
        '1. If the post explicitly names BOTH "n8n" AND "Make.com" (or '
        '"Integromat") → set `automation_platform_preference = "both"`.\n'
        '2. If the post explicitly names "n8n" (and not Make/GHL) → set '
        '`"n8n"`.\n'
        '3. If the post explicitly names "Make.com" or "Integromat" (and not '
        'n8n/GHL) → set `"make"`.\n'
        '4. If the post explicitly names "GoHighLevel", "GHL", "HighLevel", or '
        '"High Level" (and not n8n/Make) → set `"ghl"`.\n'
        "5. Any other automation platform (Zapier, Pipedream, Activepieces, "
        'Airtable Automations, n8n competitor) or no platform named → set '
        '`"unknown"`. Do NOT guess a platform that is not in the allowed set.\n\n'
        "## Deliverables detection\n"
        "Include an item in `deliverables_required` ONLY when the job "
        "explicitly requests it OR when the client strongly implies a format:\n"
        '- `"proposal"` — when the client is evaluating freelancers; assume '
        "present by default unless the post forbids proposals.\n"
        '- `"cover_letter"` — when the client explicitly asks for one.\n'
        '- `"loom_script"` — when the client asks for a Loom video, '
        "walkthrough, intro video, or recorded explanation.\n"
        '- `"workflow"` — ONLY when the job is about building an automation / '
        "workflow / scenario / zap / pipeline / trigger-action sequence. For "
        "AI/ML, web dev, mobile, data eng, design, writing, marketing jobs "
        "DO NOT include `workflow`.\n"
        '- `"doc"` — when the client asks for documentation, a technical '
        "write-up, a scope doc, a spec, or similar written artifact.\n"
        "If the post does not explicitly request any of these, include the "
        "subset that a professional would normally deliver when bidding "
        "(usually just `proposal`).\n\n"
        "## Screening questions\n"
        "Extract EVERY client-posed question as exact text. Do not paraphrase. "
        "Include questions embedded in bullet points or requirements sections. "
        "Leave the array empty only if there are truly no questions.\n\n"
        "## Constraints\n"
        "Extract only facts stated in the job post or user notes. Set a field "
        "to null / empty array when the information is not present — do NOT "
        "invent values. `tools` should list any technology, framework, or "
        "service the client mentions (e.g. React, FastAPI, Postgres, Stripe, "
        "OpenAI API, Google Sheets). `must_haves` are hard requirements the "
        "client explicitly calls out. `disallowed` are anything the client "
        "says NOT to use.\n\n"
        "## Confidence and missing fields\n"
        '- `extraction_confidence = "high"` when the scope, deliverables, and '
        "platform (if applicable) are all clear.\n"
        '- `"medium"` when the core intent is clear but 1-2 important details '
        "are ambiguous.\n"
        '- `"low"` when the post is too short, too vague, or conflicting. Low '
        "confidence blocks generation downstream, so only use it when the "
        "extraction would be unsafe.\n"
        "- `missing_fields` lists what is missing that would block a confident "
        "generation. Budget alone is NOT a blocker unless the client asks for "
        "a priced quote. Common blockers: unclear target platform for an "
        "automation job, undefined scope, conflicting requirements.\n\n"
        "# HARD OUTPUT RULES\n"
        "1. Return JSON only. No surrounding text, no markdown, no code fences.\n"
        "2. Use exactly the schema keys shown above, in any order.\n"
        "3. Never invent deliverables, platforms, constraints, or screening "
        "questions that are not grounded in the job text or user notes.\n"
        "4. Prefer factual extraction over interpretation.\n"
        "5. Every string must be valid UTF-8 JSON (escape quotes and newlines).\n\n"
        "# INPUT DATA\n\n"
        f"## Profile context\n{profile_section}\n\n"
        f"## User notes\n{notes_section}\n\n"
        f"## Job markdown\n{job_markdown}"
    )
