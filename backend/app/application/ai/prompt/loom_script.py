from __future__ import annotations

from typing import Any

from app.application.ai.prompt.common import build_context_block

PROMPT_VERSION = "loom_script_v4"
SYSTEM_PROMPT = (
    "You are a sales coach for Upwork Loom proposals. "
    "You do not write word-by-word scripts. You produce speaking guides with concise cues, "
    "transitions, and context-aware talking points that help a real person speak naturally. "
    "You must stay grounded in provided context and never invent facts, tools, outcomes, "
    "companies, metrics, or experience."
)


def build_user_prompt(context: dict[str, Any]) -> str:
    context_block = build_context_block(
        job_markdown=context.get("job_markdown"),
        notes_markdown=context.get("notes_markdown"),
        profile_context=context.get("profile_context"),
        custom_instruction=context.get("custom_instruction"),
        extra_context=context.get("extra_context"),
    )
    return (
        "Generate a Loom SPEAKING GUIDE for an Upwork proposal.\n"
        "Do NOT generate a word-by-word script.\n\n"
        "OBJECTIVE:\n"
        "Output a context-aware conversation blueprint that helps the user speak naturally.\n"
        "Use short cues, bullet points, and transition lines. The user should speak in their own words.\n"
        "Keep the guide lean and skimmable (avoid over-detailed narrative content).\n\n"
        "PRIORITY CONTRACT:\n"
        "If a 'Priority Instructions' block appears above this prompt, apply it in order.\n"
        "For Loom specifically, user DB loom_template has highest priority for structure/style.\n"
        "Then apply user global instruction.\n"
        "Then use system Loom defaults from this prompt.\n"
        "Non-negotiable guardrails always apply even if a user template exists.\n\n"
        "NON-NEGOTIABLE GUARDRAILS (ALWAYS ENFORCED):\n"
        "- No invented facts, tools, metrics, agency claims, client outcomes, or case-study details.\n"
        "- No robotic timestamp narration and no rigid word-by-word scripting.\n"
        "- Core conversation moments must be covered in intent.\n"
        "- No Loom/Doc duplication. Doc is a support reference, not a script source.\n\n"
        "CONTEXT PRIORITY:\n"
        "1. Job Post (real client pain, requirements, expected outcome)\n"
        "2. Extra context summaries (workflow/doc/job-type/classification)\n"
        "3. Profile Context (agency proof, similar work, Upwork profile evidence)\n\n"
        "CORE FLOW (MANDATORY IN INTENT):\n"
        "1. Opening / Hook\n"
        "2. Credibility Layer EARLY (agency website walkthrough + similar work + Upwork profile proof as available)\n"
        "3. Job Understanding\n"
        "4. Transition to Solution\n"
        "5. Solution Explanation\n"
        "6. Google Doc Reference\n"
        "7. Closing / CTA\n"
        "Use this flow by default. If user loom_template changes headings/order, still ensure all core moments exist.\n\n"
        "CREDIBILITY LAYER RULES (EARLY SECTION):\n"
        "- Agency website usage is selective: show only relevant proof sections, not full site walkthrough.\n"
        "- Include a mini website walkthrough block with: what to show, what to say, and why it matters.\n"
        "- If specific website pages are not provided in context, do not invent page names; use a generic "
        "'relevant case study/services page on our agency website' cue.\n"
        "- Include similar work proof only when context supports it.\n"
        "- Include Upwork profile proof only when context supports it.\n"
        "- Frame each proof as: client problem -> proof -> fit.\n"
        "- Tie proof back to the client's expected outcome.\n\n"
        "TRANSITION INTELLIGENCE (REQUIRED):\n"
        "Include explicit transition guidance between major moves.\n"
        "Minimum: one explicit transition cue in each of sections 1-6.\n"
        "Mandatory bridges:\n"
        "- Job -> Solution\n"
        "- Solution -> Website/Credibility proof\n"
        "- Website/Credibility -> Google Doc\n"
        "- Google Doc -> Closing CTA\n"
        "Transitions should sound conversational, not mechanical.\n\n"
        "CONTEXT-AWARE ADAPTATION:\n"
        "Adjust emphasis based on job type/problem/outcome (automation, chatbot, marketing, dev, etc.).\n"
        "If needed, add conditional extra sections (timeline, risk handling, assumptions, dependencies), "
        "but keep the core flow intact.\n\n"
        "OUTPUT STYLE RULES:\n"
        "- Use concise bullets/cues. Prefer short directional lines over long prose.\n"
        "- Keep each section compact: around 3-5 bullets max.\n"
        "- Avoid long paragraph blocks.\n"
        "- Avoid phrases that imply exact memorization (for example, 'say this exact line').\n"
        "- Encourage natural delivery and personal phrasing.\n\n"
        "OUTPUT FORMAT:\n"
        "- Markdown guide with section headers and bullets.\n"
        "- Include a dedicated 'Transition cue' bullet in every section from 1 to 6.\n"
        "- In section 2, include dedicated bullets: 'Agency website walkthrough: what to show', "
        "'Agency website walkthrough: what to say', and 'Agency website walkthrough: why it matters'.\n"
        "- Keep it practical and skimmable.\n"
        "- Do not output stage directions or screenplay formatting.\n\n"
        f"{context_block}"
    )
