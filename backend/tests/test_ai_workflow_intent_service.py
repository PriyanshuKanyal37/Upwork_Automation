from app.application.ai.workflow_intent_service import extract_workflow_intent, workflow_intent_to_context


def test_extract_workflow_intent_detects_webhook_and_apps() -> None:
    result = extract_workflow_intent(
        job_markdown=(
            "Build n8n webhook automation: capture lead form submissions, "
            "enrich data via API, then send Slack alert and update Airtable."
        ),
        notes_markdown="Need robust retries and error handling.",
    )

    intent = result.intent
    assert intent.trigger_type == "webhook"
    assert "slack" in intent.target_apps or "slack" in intent.source_apps
    assert "airtable" in intent.target_apps or "airtable" in intent.source_apps
    assert "fetch_api" in intent.operations
    assert intent.reliability_level == "high"
    assert intent.confidence in {"medium", "high"}


def test_extract_workflow_intent_detects_schedule() -> None:
    result = extract_workflow_intent(
        job_markdown="Need daily sync from Google Sheets to Hubspot using n8n.",
        notes_markdown="Run every day at 8am IST.",
    )
    intent = result.intent
    assert intent.trigger_type == "schedule"
    assert intent.schedule_hint is not None
    assert intent.confidence in {"medium", "high"}


def test_workflow_intent_to_context_has_expected_keys() -> None:
    result = extract_workflow_intent(
        job_markdown="Webhook from Stripe, notify Discord.",
        notes_markdown=None,
    )
    context = workflow_intent_to_context(result.intent)
    assert "workflow_intent_trigger_type" in context
    assert "workflow_intent_operations" in context
    assert "workflow_intent_reasoning" in context
