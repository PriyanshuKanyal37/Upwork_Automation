from app.application.ai.contracts import ArtifactPayload, ArtifactType
from app.application.ai.validators import validate_artifact_payload


def test_text_validator_accepts_valid_proposal() -> None:
    artifact = ArtifactPayload(
        artifact_type=ArtifactType.PROPOSAL,
        content_text="This proposal explains execution approach, milestones, and expected outcomes.",
    )
    result = validate_artifact_payload(artifact)
    assert result.is_valid is True
    assert result.issues == []


def test_text_validator_rejects_too_short_text() -> None:
    artifact = ArtifactPayload(artifact_type=ArtifactType.PROPOSAL, content_text="Too short")
    result = validate_artifact_payload(artifact)
    assert result.is_valid is False
    assert result.issues[0].code == "text_too_short"


def test_workflow_validator_accepts_import_ready_shape() -> None:
    artifact = ArtifactPayload(
        artifact_type=ArtifactType.WORKFLOW,
        content_json={
            "nodes": [
                {
                    "id": "1",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [260, 260],
                },
                {
                    "id": "2",
                    "name": "Set Data",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "position": [520, 260],
                },
            ],
            "connections": {
                "Manual Trigger": {
                    "main": [
                        [
                            {
                                "node": "Set Data",
                                "type": "main",
                                "index": 0,
                            }
                        ]
                    ]
                }
            },
            "settings": {"executionOrder": "v1"},
        },
    )
    result = validate_artifact_payload(artifact)
    assert result.is_valid is True


def test_workflow_validator_rejects_missing_node_fields() -> None:
    artifact = ArtifactPayload(
        artifact_type=ArtifactType.WORKFLOW,
        content_json={"nodes": [{"id": "1"}], "connections": {}},
    )
    result = validate_artifact_payload(artifact)
    assert result.is_valid is False
    assert result.issues[0].code == "missing_node_fields"


def test_workflow_validator_rejects_missing_execution_order() -> None:
    artifact = ArtifactPayload(
        artifact_type=ArtifactType.WORKFLOW,
        content_json={
            "nodes": [
                {
                    "id": "1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.1,
                    "position": [260, 260],
                }
            ],
            "connections": {},
            "settings": {},
        },
    )
    result = validate_artifact_payload(artifact)
    assert result.is_valid is False
    assert result.issues[0].code == "missing_execution_order"


def test_make_workflow_validator_accepts_valid_nested_blueprint() -> None:
    artifact = ArtifactPayload(
        artifact_type=ArtifactType.MAKE_WORKFLOW,
        content_json={
            "name": "Lead Intake",
            "flow": [
                {
                    "id": 1,
                    "module": "scheduler",
                    "version": 1,
                    "parameters": {},
                    "mapper": {},
                    "metadata": {"designer": {"x": 0, "y": 0}},
                }
            ],
            "metadata": {
                "instant": False,
                "zone": "us1.make.com",
                "scenario": {},
            },
        },
    )
    result = validate_artifact_payload(artifact)
    assert result.is_valid is True


def test_ghl_workflow_validator_accepts_valid_build_spec() -> None:
    artifact = ArtifactPayload(
        artifact_type=ArtifactType.GHL_WORKFLOW,
        content_json={
            "workflow_name": "Lead Follow Up",
            "workflow_description": "Follow up after form submission.",
            "trigger": {
                "type": "Form Submitted",
                "category": "Events",
                "configuration_notes": "Use website lead form.",
                "filter_conditions": [],
            },
            "steps": [
                {
                    "step_number": 1,
                    "step_type": "action",
                    "name": "Tag lead",
                    "action_name": "Add Contact Tag",
                    "action_category": "Contact",
                    "configuration": {"tag": "new-lead"},
                    "wait_duration": None,
                    "branch_condition": None,
                    "if_true_next_step": None,
                    "if_false_next_step": None,
                    "notes": "Tag new leads.",
                }
            ],
            "estimated_build_time_minutes": 15,
            "required_integrations": [],
            "required_custom_fields": [],
        },
    )
    result = validate_artifact_payload(artifact)
    assert result.is_valid is True
