from __future__ import annotations

from typing import Any

from app.application.ai.prompt.common import build_context_block, normalize_optional_section

PROMPT_VERSION = "proposal_v12"
SYSTEM_PROMPT = (
    "You write Upwork proposals that sound like a confident, experienced professional "
    "sent them personally — not a template, not AI, not a generic cover letter. "
    "Every line is direct, specific, and earns its place. "
    "The tone is warm but self-assured — like someone who knows their work and respects the client's time. "
    "Never invent facts, outcomes, numbers, brands, tools, or links. "
    "Only use proof, results, and background that exist in the profile context."
)


def build_user_prompt(context: dict[str, Any]) -> str:
    proposal_template = context.get("proposal_template")
    extra_context = context.get("extra_context") or {}

    loom_url = extra_context.get("proposal_loom_video_url") or "[PASTE YOUR LOOM LINK]"
    doc_url = (
        extra_context.get("proposal_doc_url")
        or extra_context.get("doc_url")
        or "[PASTE YOUR DOC LINK]"
    )

    context_block = build_context_block(
        job_markdown=context.get("job_markdown"),
        notes_markdown=context.get("notes_markdown"),
        profile_context=context.get("profile_context"),
        custom_instruction=context.get("custom_instruction"),
        extra_context=extra_context,
    )

    return (
        "Generate one tailored Upwork proposal.\n\n"

        # ── PROOF LINES ───────────────────────────────────────────────────────
        "PROOF LINES — mandatory, always the first two lines of every proposal:\n"
        "These appear before any other content. Always. No exceptions.\n\n"

        "Loom line (always write this, every proposal):\n"
        "Write one short, natural sentence introducing the video, with the link at the end.\n"
        "Vary the wording — do not use the same sentence every time.\n"
        f"The Loom URL for this proposal: {loom_url}\n"
        "Example variations (pick or adapt one naturally):\n"
        f"  'Just shot a quick video walking through exactly how I'd approach this: {loom_url}'\n"
        f"  'Recorded a short walkthrough of my plan before reaching out: {loom_url}'\n"
        f"  'Put together a quick video breaking down how I'd handle this: {loom_url}'\n\n"

        "Doc line (always write this, every proposal):\n"
        "Write one short, natural sentence introducing the document, with the link at the end.\n"
        "Vary the wording — do not use the same sentence every time.\n"
        f"The Doc URL for this proposal: {doc_url}\n"
        "Example variations (pick or adapt one naturally):\n"
        f"  'Also put together a quick one-page plan you can look over: {doc_url}'\n"
        f"  'Dropped a short breakdown doc alongside the video: {doc_url}'\n"
        f"  'Here is a one-pager I put together outlining my approach: {doc_url}'\n\n"

        "After the two proof lines, leave one blank line, then start the proposal body.\n\n"

        # ── TEMPLATE SELECTION ────────────────────────────────────────────────
        "TEMPLATE — pick one based on the job post tone and what the client emphasized.\n"
        "Follow the chosen template structure closely. Vary the language — never copy placeholder text as-is.\n\n"

        "Template 1 — Direct Confidence\n"
        "(Use when: client has a clear deliverable and sounds decisive)\n"
        "[Opening — 1 sentence: Hi/Hey — I'm your person for [WHAT THE JOB IS ABOUT]. Direct. Confident.]\n"
        "[Loom line as above]\n"
        "[Doc line as above]\n"
        "\n"
        "[Proof paragraph — 2-3 sentences: specific results or wins pulled from profile context.]\n"
        "[About me — 2-3 sentences: brief, relevant background from profile context.]\n"
        "If you like what you see, just shoot me back a few times you're free for a quick call — we'll schedule from there.\n"
        "Best,\n"
        "[NAME FROM PROFILE CONTEXT]\n\n"

        "Template 2 — Problem-Solver\n"
        "(Use when: client describes a specific pain, blocker, or problem to fix)\n"
        "[Opening — 1 sentence: Hey — just read through your post, [SPECIFIC PROBLEM] is something I handle well.]\n"
        "[Loom line as above]\n"
        "[Doc line as above]\n"
        "\n"
        "[Method paragraph — 2-3 sentences: how you'd solve this exact problem, using job context + profile.]\n"
        "[Background — 2-3 sentences: relevant experience from profile context.]\n"
        "If you like what you see, shoot me a few times you're free and we'll get a quick call sorted.\n"
        "Best,\n"
        "[NAME FROM PROFILE CONTEXT]\n\n"

        "Template 3 — Results-Focused\n"
        "(Use when: client cares about outcomes, ROI, or mentions previous failures)\n"
        "[Opening — 1 sentence: Hi there — confident I can deliver [SPECIFIC OUTCOME] for this.]\n"
        "[Loom line as above]\n"
        "[Doc line as above]\n"
        "\n"
        "[Track record paragraph — 2-3 sentences: concrete wins and results from profile context only.]\n"
        "[About me — 2-3 sentences: background that backs up the results, from profile context.]\n"
        "If this looks like the direction you want, send over a few times you're free for a quick call.\n"
        "Best,\n"
        "[NAME FROM PROFILE CONTEXT]\n\n"

        "Template 4 — Technical Expertise\n"
        "(Use when: client post is technical, mentions specific tools, stack, or architecture)\n"
        "[Opening — 1 sentence: Hello — I specialise in exactly what you need for [PROJECT AREA/TECH].]\n"
        "[Loom line as above]\n"
        "[Doc line as above]\n"
        "\n"
        "[Technical fit paragraph — 2-3 sentences: specific stack match and delivery plan from job + profile context.]\n"
        "[Background — 2-3 sentences: relevant technical experience from profile context.]\n"
        "If that looks useful, send me a few times that work and we'll jump on a quick call.\n"
        "Best,\n"
        "[NAME FROM PROFILE CONTEXT]\n\n"

        "Template 5 — Consultative\n"
        "(Use when: client is early-stage, unclear on approach, or needs strategic input)\n"
        "[Opening — 1 sentence: Hey — reviewed your requirements, I can see a clear way to improve [SPECIFIC AREA].]\n"
        "[Loom line as above]\n"
        "[Doc line as above]\n"
        "\n"
        "[Strategy paragraph — 2-3 sentences: your approach and thinking, matched to their situation.]\n"
        "[Wins + background — 2-3 sentences: relevant results and experience from profile context.]\n"
        "If this is aligned with what you have in mind, share a few times you're free and we'll schedule a call.\n"
        "Best,\n"
        "[NAME FROM PROFILE CONTEXT]\n\n"

        # ── WRITING RULES ─────────────────────────────────────────────────────
        "WRITING RULES:\n"
        "- Body: 160-260 words (not counting proof lines or sign-off).\n"
        "- Match the client's tone — casual post gets casual reply, formal post gets professional reply.\n"
        "- Every sentence must reference something specific from the job post or profile context.\n"
        "- No generic filler: 'I am passionate about', 'great communicator', 'hard worker'.\n"
        "- No invented facts, numbers, or claims not present in context.\n"
        "- The proof and about-me paragraphs must come from profile context only.\n"
        "- CTA is always a soft binary: offer a call, make it easy to say yes.\n\n"

        # ── OUTPUT RULES ──────────────────────────────────────────────────────
        "OUTPUT:\n"
        "- Final proposal text only. No headings, labels, or meta commentary.\n"
        "- Start with the Loom line. Then Doc line. Then blank line. Then body.\n\n"

        # ── PRIORITY ──────────────────────────────────────────────────────────
        "PRIORITY (highest to lowest when sources conflict):\n"
        "1) 'Priority Instructions' block above this prompt — includes Custom Global "
        "Instruction and User Output Template Preference. "
        "If that block is present, it is authoritative and overrides anything below "
        "on any aspect it specifies.\n"
        "2) User Proposal Template section below — same content as the template in "
        "Priority Instructions when set; used as the fallback structure and voice guide "
        "when no Priority Instructions block is present.\n"
        "3) This prompt (quality rules — PROOF LINES, WRITING RULES, and OUTPUT are "
        "always mandatory regardless of user overrides).\n"
        "4) Context block (all facts — job post, profile, notes).\n\n"

        "## User Proposal Template\n"
        f"{normalize_optional_section(proposal_template)}\n\n"
        f"{context_block}"
    )
