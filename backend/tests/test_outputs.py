from uuid import uuid4
from fastapi.testclient import TestClient


def _register(client: TestClient, name: str) -> str:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201
    return email


def _create_job(client: TestClient) -> str:
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    return intake.json()["job"]["id"]


def test_job_output_requires_auth(client: TestClient) -> None:
    response = client.get(f"/api/v1/jobs/{uuid4()}/outputs")
    assert response.status_code == 401


def test_job_output_create_get_update_and_edit_log(client: TestClient) -> None:
    _register(client, "OutputUserA")
    job_id = _create_job(client)

    create_response = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={
            "google_doc_url": "https://docs.google.com/document/d/abc123",
            "google_doc_markdown": "## Doc output",
            "workflow_jsons": [
                {"name": "main", "workflow_json": {"nodes": [{"id": "1", "type": "trigger"}]}}
            ],
            "workflow_explanation": "This workflow captures leads and pushes to CRM.",
            "loom_script": "Step 1 explain context",
            "proposal_text": "Initial proposal draft",
        },
    )
    assert create_response.status_code == 200
    created_output = create_response.json()["output"]
    assert created_output["google_doc_markdown"] == "## Doc output"
    assert created_output["loom_script"] == "Step 1 explain context"
    assert created_output["proposal_text"] == "Initial proposal draft"
    assert created_output["workflow_explanation"] == "This workflow captures leads and pushes to CRM."
    assert len(created_output["workflow_jsons"]) == 1
    assert created_output["workflow_jsons"][0]["name"] == "main"
    assert len(created_output["edit_log_json"]) == 1
    assert created_output["edit_log_json"][0]["action"] == "save"

    update_response = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={"proposal_text": "Updated proposal copy"},
    )
    assert update_response.status_code == 200
    updated_output = update_response.json()["output"]
    assert updated_output["proposal_text"] == "Updated proposal copy"
    assert updated_output["loom_script"] == "Step 1 explain context"
    assert len(updated_output["edit_log_json"]) == 2
    assert updated_output["edit_log_json"][-1]["changed_fields"] == ["proposal_text"]

    get_response = client.get(f"/api/v1/jobs/{job_id}/outputs")
    assert get_response.status_code == 200
    fetched_output = get_response.json()["output"]
    assert fetched_output["proposal_text"] == "Updated proposal copy"
    assert len(fetched_output["edit_log_json"]) == 2


def test_regenerate_updates_only_target_output(client: TestClient) -> None:
    _register(client, "OutputUserB")
    job_id = _create_job(client)

    seed_response = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={
            "loom_script": "Original loom script",
            "proposal_text": "Original proposal text",
        },
    )
    assert seed_response.status_code == 200

    regenerate = client.post(
        f"/api/v1/jobs/{job_id}/outputs/regenerate",
        json={
            "target_output": "proposal_text",
            "instruction": "Make this more concise.",
            "generated_text": "Regenerated concise proposal",
        },
    )
    assert regenerate.status_code == 200
    payload = regenerate.json()
    assert payload["regenerated_output"] == "proposal_text"
    assert payload["output"]["proposal_text"] == "Regenerated concise proposal"
    assert payload["output"]["loom_script"] == "Original loom script"
    assert payload["output"]["edit_log_json"][-1]["action"] == "regenerate"
    assert payload["output"]["edit_log_json"][-1]["target_output"] == "proposal_text"


def test_workflow_json_structure_validation(client: TestClient) -> None:
    _register(client, "OutputUserC")
    job_id = _create_job(client)

    invalid = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={"workflow_jsons": [{"workflow_json": {"nodes": []}}]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_regenerate_payload_mismatch_validation(client: TestClient) -> None:
    _register(client, "OutputUserD")
    job_id = _create_job(client)

    invalid = client.post(
        f"/api/v1/jobs/{job_id}/outputs/regenerate",
        json={
            "target_output": "workflow_jsons",
            "generated_text": "not-allowed",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_patch_output_rejects_removed_classification_fields(client: TestClient) -> None:
    _register(client, "OutputUserE")
    job_id = _create_job(client)

    response = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={
            "proposal_text": "Hello",
            "job_type": "automation",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
