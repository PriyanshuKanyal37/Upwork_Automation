from app.application.ai.contracts import RouteTask
from app.application.ai.prompt_builder import build_prompt


def test_prompt_builder_hash_is_deterministic_for_same_input() -> None:
    context = {
        "job_markdown": "Need n8n automation for CRM.",
        "notes_markdown": "Please keep concise.",
        "profile_context": "Experienced automation consultant.",
    }
    first = build_prompt(task=RouteTask.JOB_UNDERSTANDING, context=context)
    second = build_prompt(task=RouteTask.JOB_UNDERSTANDING, context=context)

    assert first.prompt_version == "job_understanding_v3"
    assert second.prompt_version == "job_understanding_v3"
    assert first.prompt_hash == second.prompt_hash


def test_prompt_builder_hash_changes_when_context_changes() -> None:
    base = build_prompt(
        task=RouteTask.PROPOSAL,
        context={"job_markdown": "Build workflow", "notes_markdown": "short"},
    )
    changed = build_prompt(
        task=RouteTask.PROPOSAL,
        context={"job_markdown": "Build workflow", "notes_markdown": "long and detailed"},
    )
    assert base.prompt_hash != changed.prompt_hash


def test_prompt_builder_appends_user_personalization_layer() -> None:
    built = build_prompt(
        task=RouteTask.PROPOSAL,
        context={
            "job_markdown": "Build workflow",
            "notes_markdown": "short",
            "custom_global_instruction": "Always keep tone concise and practical.",
            "proposal_template": "Use this proposal structure: intro, plan, proof, CTA.",
            "custom_prompt_blocks": [
                {"title": "Tone", "content": "Use direct language", "enabled": True},
                {"title": "Disabled", "content": "Should not appear", "enabled": False},
            ],
        },
    )
    assert "Priority Instructions" in built.user_prompt
    assert "User Global Instruction" in built.user_prompt
    assert "Always keep tone concise and practical." in built.user_prompt
    assert "User Output Template Preference" in built.user_prompt
    assert "Use this proposal structure" in built.user_prompt
    assert "Enabled User Prompt Blocks" in built.user_prompt
    assert "Tone" in built.user_prompt
    assert "Should not appear" not in built.user_prompt
    assert built.user_prompt.index("Priority Instructions") < built.user_prompt.index(
        "Base Generation Guidance"
    )


def test_loom_prompt_prioritizes_user_template_before_global_instruction() -> None:
    built = build_prompt(
        task=RouteTask.LOOM_SCRIPT,
        context={
            "job_markdown": "Need an automation consultant to clean up CRM lead flow.",
            "notes_markdown": "Keep it practical.",
            "loom_template": "Use my custom Loom guide shape with an early proof stack.",
            "custom_global_instruction": "Keep tone concise and grounded.",
        },
    )
    assert "from DB loom_template, highest priority for Loom structure/style" in built.user_prompt
    assert "User Global Instruction (secondary to artifact template when both are present)" in built.user_prompt
    assert built.user_prompt.index("from DB loom_template") < built.user_prompt.index(
        "User Global Instruction (secondary to artifact template when both are present)"
    )


def test_loom_prompt_enforces_core_flow_and_guardrails() -> None:
    built = build_prompt(
        task=RouteTask.LOOM_SCRIPT,
        context={"job_markdown": "Need chatbot + CRM integration support."},
    )
    prompt = built.user_prompt
    assert built.prompt_version == "loom_script_v4"
    assert "Generate a Loom SPEAKING GUIDE" in prompt
    assert "Do NOT generate a word-by-word script." in prompt
    assert "CORE FLOW (MANDATORY IN INTENT)" in prompt
    assert "1. Opening / Hook" in prompt
    assert "2. Credibility Layer EARLY" in prompt
    assert "7. Closing / CTA" in prompt
    assert "TRANSITION INTELLIGENCE (REQUIRED)" in prompt
    assert "Minimum: one explicit transition cue in each of sections 1-6." in prompt
    assert "Include a dedicated 'Transition cue' bullet in every section from 1 to 6." in prompt
    assert "agency website walkthrough" in prompt.lower()
    assert "Agency website walkthrough: what to show" in prompt
    assert "No Loom/Doc duplication" in prompt
