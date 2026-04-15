"""Universal Upwork proposal document prompt (doc_v8).

Design intent
-------------
Freelancers publish the generated markdown to Google Docs and screen-share it
during a short Loom walkthrough. They narrate only lightly — "okay, this is
the plan" — while scrolling. The doc itself has to carry the information.

The doc is WORK-FOCUSED, not sale-focused. A client reading 10+ proposals
cares about one thing: "will this person actually solve my problem well?".
So the two largest sections by word budget are `How I'll solve it` and
`How I'll handle the tricky parts` — together ~50% of the total. Timeline is
a single closing sentence and pricing is NEVER mentioned (the Upwork proposal
card already shows the bid).

GPT-5.4-mini norms (OpenAI 2026 guidance)
-----------------------------------------
- Rules-first ordering (instructions before context before example)
- Explicit execution order (model is literal, makes fewer assumptions)
- Hard length caps over soft targets
- ONE example at the END, not multiple
- Positive framing over negative constraints
- Scoped output boundaries ("begin directly with H1, end after last section")

Sources:
- https://developers.openai.com/api/docs/guides/prompt-guidance
- https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.application.ai.prompt.common import build_context_block

PROMPT_VERSION = "doc_v8"

_EXAMPLE_PATH = Path(__file__).resolve().parent / "skills_md" / "doc_example.md"


def _load_example() -> str:
    try:
        text = _EXAMPLE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    return text


_EXAMPLE_DOC = _load_example()


SYSTEM_PROMPT = (
    "You write one-page Upwork proposal documents for freelancers applying to jobs. "
    "The freelancer publishes the doc to Google Docs and screen-shares it in a short "
    "Loom walkthrough, narrating only lightly (\"okay, this is the plan\") while the "
    "doc carries the real information. The client reading it wants ONE answer: will "
    "this freelancer solve my problem well? You dominate the doc with HOW the work "
    "gets done and HOW the tricky parts are handled. You never mention dollar amounts "
    "— the Upwork proposal card already shows the bid. Every bullet is a short "
    "self-sufficient thought that stands alone when read silently."
)


def build_user_prompt(context: dict[str, Any]) -> str:
    context_block = build_context_block(
        job_markdown=context.get("job_markdown"),
        notes_markdown=context.get("notes_markdown"),
        profile_context=context.get("profile_context"),
        custom_instruction=context.get("custom_instruction"),
        extra_context=context.get("extra_context"),
    )

    example_block = (
        "<example>\n"
        "Below is a complete, correct Lean PRD produced for a DIFFERENT job. "
        "Match its structure, tone, level of specificity, and length discipline "
        "exactly. Do NOT copy its content — it is for a different client, in a "
        "different domain. Treat it as a shape reference, not a template.\n\n"
        "<ideal_output>\n"
        f"{_EXAMPLE_DOC}\n"
        "</ideal_output>\n"
        "</example>\n"
    ) if _EXAMPLE_DOC else ""

    return (
        # ─── TASK ──────────────────────────────────────────────────────────
        "<task>\n"
        "Write one Upwork proposal document for the job described in "
        "<provided_context>. The document will be published to Google Docs and "
        "screen-shared during a short Loom walkthrough.\n"
        "</task>\n\n"

        # ─── INSTRUCTION PRECEDENCE ────────────────────────────────────────
        # User-level doc_template (if present above) overrides doc_v6 defaults.
        "<instruction_precedence>\n"
        "If a section titled 'Priority Instructions' or 'User Output Template "
        "Preference' appears ABOVE this prompt, it is AUTHORITATIVE and overrides "
        "the defaults in this prompt on any aspect it specifies.\n\n"
        "Precedence, from highest to lowest:\n"
        "1. User Global Instruction and User Output Template Preference (if present above)\n"
        "2. <output_contract>, <length_limits>, <emoji_discipline> in this prompt "
        "(fallback defaults only)\n\n"
        "How to apply:\n"
        "- If the user template specifies section names, section order, or "
        "headings → use the user template's structure and IGNORE <output_contract> "
        "in this prompt.\n"
        "- If the user template specifies length or word count → use the user "
        "template's numbers and IGNORE <length_limits> in this prompt.\n"
        "- If the user template specifies tone, emoji usage, or formatting style "
        "→ use the user template and IGNORE <emoji_discipline> in this prompt.\n"
        "- If the user template is silent on an aspect → use the matching "
        "<output_contract> / <length_limits> / <emoji_discipline> rule as the default.\n\n"
        "ALWAYS mandatory regardless of user template:\n"
        "- <style_rules> (grounding, specificity, no invention, no dollar amounts)\n"
        "- <ambiguity_handling> (TBD placeholders, no fabricated facts)\n"
        "- <output_boundary> (no preamble, no postamble)\n"
        "When in doubt, prefer the user's template shape, but never fabricate "
        "facts to fill it.\n"
        "</instruction_precedence>\n\n"

        # ─── EXECUTION ORDER ────────────────────────────────────────────────
        # GPT-5.4-mini is literal; an explicit sequence improves adherence.
        "<execution_order>\n"
        "0. Check for a user template block above this prompt. If present, adopt "
        "its section structure, section names, tone, and length targets.\n"
        "1. Read <provided_context> carefully. Extract the client's real pain "
        "point (not just the ask), the tools they mentioned, any deadlines, and "
        "any edge cases or constraints they hinted at.\n"
        "2. Identify the job's primary category from the 8 in "
        "<adaptation_by_category>.\n"
        "3. Restate the client's ACTUAL PROBLEM in '🎯 The problem you're "
        "solving' (3 bullets). Focus on the pain they feel today, not the "
        "deliverable they named.\n"
        "4. Build 5-7 approach phases in '🧭 How I'll solve it' — this is the "
        "centerpiece of the doc. Each bullet names specific tools, decisions, "
        "tradeoffs, or outcomes tied to the job category.\n"
        "5. Fill '📦 What you'll end up with' as a 2-column markdown table: "
        "Deliverable | Why it matters. 4-6 rows. NO price column.\n"
        "6. Write '🛡 How I'll handle the tricky parts' (3-4 bullets) — edge "
        "cases, quality safeguards, known gotchas. Prove depth of thinking.\n"
        "7. Write '⚡ Why me' using profile_context; include ONE blockquote "
        "callout (> ...) with a credibility number or differentiator.\n"
        "8. Write '👉 Timeline & next step' as 1-2 sentences: rough duration "
        "(\"~3 weeks\", \"by Friday\", etc.) plus one clear call to action. "
        "NEVER mention money — the Upwork proposal card already shows the bid.\n"
        "9. Stop immediately. Output nothing after the last sentence.\n"
        "</execution_order>\n\n"

        # ─── SOURCE PRIORITY ────────────────────────────────────────────────
        "<source_priority>\n"
        "When two sources conflict, follow this order from highest to lowest:\n"
        "1. `## Job Post` — authoritative source of what the client wants.\n"
        "2. `## Custom Instruction` and `## User Notes` — your team's private "
        "direction; can override Job Post when explicitly stated.\n"
        "3. `## Profile Context` — freelancer background; use for '⚡ Why me' "
        "and tone framing only.\n"
        "4. `## Extra context` → `workflow_summary` and `workflow_explanation` "
        "— prior artifacts; use only to ground the technical sections when this "
        "is an automation job.\n"
        "When in doubt, defer to `## Job Post`.\n"
        "</source_priority>\n\n"

        # ─── AMBIGUITY HANDLING ─────────────────────────────────────────────
        "<ambiguity_handling>\n"
        "When a fact is missing from <provided_context>:\n"
        "- Required detail missing (tool, timeline, deliverable scope, stakeholder): "
        "write `[TBD — confirm with client]` inline and continue writing.\n"
        "- Optional flavor missing (exact email copy, specific color, minor UI "
        "choice): omit it silently. Do not invent.\n"
        "- An entire section cannot be written because its source is empty: "
        "write one sentence naming what is missing, then move on. Do not pad.\n"
        "Every tool, integration, timeline, credential, URL, and case study you "
        "mention must appear in <provided_context>. This is a hard rule.\n"
        "</ambiguity_handling>\n\n"

        # ─── CROSS-CATEGORY ADAPTATION ──────────────────────────────────────
        "<adaptation_by_category>\n"
        "Each line: category → phases for '🧭 How I'll solve it' | deliverables "
        "for '📦 What you'll end up with'\n\n"
        "- automation (n8n / Make / Zapier / GHL): workflow phases | nodes, "
        "triggers, credentials, run history\n"
        "- web_dev (React / Next.js / Vue / full-stack): build phases | pages, "
        "components, APIs, CI/CD\n"
        "- ai_ml (chatbot / RAG / fine-tune / agent): model & data phases | "
        "models, endpoints, dashboards, accuracy benchmarks\n"
        "- design (brand / UI / landing / logo): design phases | files, formats, "
        "revision rounds, brand guide\n"
        "- writing (blog / copy / SEO / ghostwriting): research/draft/polish "
        "phases | word count, pieces, keywords, meta tags\n"
        "- marketing (ads / funnel / email / growth): campaign phases | "
        "campaigns, assets, reports, dashboards\n"
        "- mobile_dev (iOS / Android / React Native): feature phases | screens, "
        "builds, store listing, TestFlight\n"
        "- data (ETL / analytics / dashboards): pipeline phases | datasets, "
        "reports, dashboards, docs\n\n"
        "Use the category that best matches the Job Post. Mix categories when "
        "the job clearly spans both (e.g. ai_ml + web_dev for a chatbot with a "
        "dashboard).\n"
        "</adaptation_by_category>\n\n"

        # ─── OUTPUT CONTRACT ────────────────────────────────────────────────
        "<output_contract>\n"
        "DEFAULT section structure to use ONLY when no user template is "
        "provided above. If a 'User Output Template Preference' block appears "
        "above, follow its structure instead and ignore this block.\n\n"
        "Default sections, in exact order, with exact H2 headers and emojis:\n\n"
        "# <Project title — the client's problem in their own words>\n"
        "## 🎯 The problem you're solving\n"
        "## 🧭 How I'll solve it\n"
        "## 📦 What you'll end up with    (markdown table, 2 columns)\n"
        "## 🛡 How I'll handle the tricky parts\n"
        "## ⚡ Why me    (one blockquote allowed here)\n"
        "## 👉 Timeline & next step    (1-2 sentences, NO pricing)\n\n"
        "The doc is weighted toward the work. 'How I'll solve it' + 'How I'll "
        "handle the tricky parts' together are roughly HALF the total word "
        "budget.\n"
        "</output_contract>\n\n"

        # ─── LENGTH LIMITS ──────────────────────────────────────────────────
        "<length_limits>\n"
        "DEFAULT length discipline to use ONLY when the user template is "
        "silent on length. If the user template specifies word counts, follow "
        "those instead and ignore this block.\n\n"
        "Total document: 380-570 words. Target ~460.\n"
        "Absolute ceiling: 650 words.\n\n"
        "Per section (soft caps unless marked ABSOLUTE):\n"
        "- Title: 1 line\n"
        "- 🎯 The problem you're solving: 50-70 words, 3 bullets\n"
        "- 🧭 How I'll solve it: 140-200 words, 5-7 bullets (phase-based, "
        "technical depth) ← CENTERPIECE\n"
        "- 📦 What you'll end up with: 4-6 table rows, ~15 words per row "
        "(two columns: Deliverable / Why it matters)\n"
        "- 🛡 How I'll handle the tricky parts: 60-90 words, 3-4 bullets "
        "(edge cases, quality safeguards)\n"
        "- ⚡ Why me: 50-70 words, 2-3 bullets + one blockquote\n"
        "- 👉 Timeline & next step: 1-2 sentences, under 50 words, NO dollar amounts\n\n"
        "If total exceeds ceiling: tighten '⚡ Why me' first, then '🎯 The "
        "problem you're solving'. NEVER cut '🧭 How I'll solve it' or '🛡 How "
        "I'll handle the tricky parts' — they are the whole point of the doc.\n\n"
        "Word budgets exist because the client reads this on a phone between "
        "meetings. Overly long docs do not get read.\n"
        "</length_limits>\n\n"

        # ─── STYLE RULES (positive framing only) ────────────────────────────
        "<style_rules>\n"
        "Two-tier bullet density:\n"
        "- 'Sell' sections (🎯 The problem, 📦 What you'll end up with, ⚡ Why "
        "me): 10-18 words per bullet. Tight and scannable.\n"
        "- 'Work' sections (🧭 How I'll solve it, 🛡 How I'll handle the "
        "tricky parts): 20-35 words per bullet. Each bullet names a specific "
        "tool, decision, tradeoff, or safeguard. These bullets are where the "
        "client evaluates depth of thinking — short bullets here look shallow.\n\n"
        "Grounding rules:\n"
        "- Every bullet is a short complete thought that stands alone when "
        "read silently. Has a subject and a verb.\n"
        "- Each bullet names a specific tool, integration, deliverable, "
        "number, or technical decision from <provided_context>. If a bullet "
        "could apply to any project, rewrite it or delete it.\n"
        "- Use plain professional English. No jargon the client did not use first.\n"
        "- Prefer concrete nouns over vague verbs ('React dashboard with "
        "Stripe checkout' beats 'modern web solution').\n"
        "- Short paragraphs, tight bullets, no walls of text.\n"
        "- Quote only tools, names, URLs, and numbers present in "
        "<provided_context>. When a placeholder is needed, use "
        "`[TBD — confirm with client]`.\n"
        "- State assumptions explicitly by prefixing with *Assumption:* in "
        "italics inside the relevant bullet.\n\n"
        "Money rules (absolute):\n"
        "- NEVER write a dollar amount, an hourly rate, or a fixed-price "
        "figure anywhere in the doc. The Upwork proposal card already shows "
        "the bid.\n"
        "- Timeline mentions are allowed only in '👉 Timeline & next step' "
        "and only as a rough duration ('~3 weeks', 'by Friday of next week'). "
        "No line-itemized phase timeline.\n"
        "</style_rules>\n\n"

        # ─── EMOJI DISCIPLINE ───────────────────────────────────────────────
        "<emoji_discipline>\n"
        "Use exactly ONE emoji per H2 section header. Use ZERO emojis "
        "anywhere else (body, bullets, the H1 title, inline text).\n\n"
        "Default emojis (exact, do not substitute):\n"
        "- 🎯 The problem you're solving\n"
        "- 🧭 How I'll solve it\n"
        "- 📦 What you'll end up with\n"
        "- 🛡 How I'll handle the tricky parts\n"
        "- ⚡ Why me\n"
        "- 👉 Timeline & next step\n"
        "</emoji_discipline>\n\n"

        # ─── VISUAL POLISH ──────────────────────────────────────────────────
        "<visual_polish>\n"
        "- '📦 What you'll end up with' MUST be a markdown table with columns "
        "`Deliverable | Why it matters`. Not prose, not bullets. NO price "
        "column. NO cost anywhere.\n"
        "- Put a --- horizontal rule divider between each H2 section for "
        "slide-deck feel on screen share.\n"
        "- You MAY use exactly ONE blockquote (`> ...`) in the '⚡ Why me' "
        "section to highlight a credibility stat or differentiator. No other "
        "blockquotes anywhere in the doc.\n"
        "- Use **bold** only for phase names in '🧭 How I'll solve it' "
        "bullets, for row labels in the deliverables table, and for 3-5 "
        "scannable keywords per section.\n"
        "- NO mermaid code blocks. NO raw image references. NO HTML. NO "
        "code fences around the document output.\n"
        "- NO dollar amounts anywhere in the doc body.\n"
        "- NO line-itemized timeline table.\n"
        "</visual_polish>\n\n"

        # ─── OUTPUT BOUNDARY ────────────────────────────────────────────────
        "<output_boundary>\n"
        "Begin your response on the first line with the H1 title "
        "(`# <project title>`). Do not write 'Here is the document', 'Based "
        "on the context', or any preamble. After the last sentence of '👉 "
        "Timeline & next step', output nothing further — no summary, no "
        "signoff, no closing remark, no code fences.\n"
        "</output_boundary>\n\n"

        # ─── PROVIDED CONTEXT ───────────────────────────────────────────────
        "<provided_context>\n"
        f"{context_block}\n"
        "</provided_context>\n\n"

        # ─── ONE REFERENCE EXAMPLE (at the END per OpenAI GPT-5.4-mini guidance) ─
        f"{example_block}"
    )
