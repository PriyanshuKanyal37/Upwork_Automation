from uuid import uuid4

from fastapi.testclient import TestClient


def _register(client: TestClient, name: str) -> tuple[str, str]:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": password},
    )
    assert response.status_code == 201
    return email, password


def _login(client: TestClient, email: str, password: str) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def _job_url() -> str:
    return f"https://www.upwork.com/jobs/example-{uuid4().hex[:8]}~{uuid4().hex}"


def test_projects_create_and_list_for_current_user(client: TestClient) -> None:
    _register(client, "ProjectOwner")

    empty_list = client.get("/api/v1/projects")
    assert empty_list.status_code == 200
    assert empty_list.json()["count"] == 0

    create_response = client.post("/api/v1/projects", json={"name": "  AI  "})
    assert create_response.status_code == 201
    project = create_response.json()["project"]
    assert project["name"] == "AI"

    duplicate_response = client.post("/api/v1/projects", json={"name": "AI"})
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "project_name_exists"

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["count"] == 1
    assert payload["projects"][0]["id"] == project["id"]


def test_jobs_can_be_assigned_to_projects_and_filtered(client: TestClient) -> None:
    _register(client, "ProjectJobsOwner")
    project = client.post("/api/v1/projects", json={"name": "Web"}).json()["project"]

    intake_a = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": _job_url(), "project_id": project["id"]},
    )
    assert intake_a.status_code == 201
    job_a_id = intake_a.json()["job"]["id"]
    assert intake_a.json()["job"]["project_id"] == project["id"]

    intake_b = client.post("/api/v1/jobs/intake", json={"job_url": _job_url()})
    assert intake_b.status_code == 201
    job_b_id = intake_b.json()["job"]["id"]
    assert intake_b.json()["job"]["project_id"] is None

    list_project_jobs = client.get(f"/api/v1/jobs?project_id={project['id']}")
    assert list_project_jobs.status_code == 200
    assert list_project_jobs.json()["count"] == 1
    assert list_project_jobs.json()["jobs"][0]["id"] == job_a_id

    assign_response = client.patch(
        f"/api/v1/jobs/{job_b_id}/project",
        json={"project_id": project["id"]},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["job"]["project_id"] == project["id"]

    list_project_jobs_after_assign = client.get(f"/api/v1/jobs?project_id={project['id']}")
    assert list_project_jobs_after_assign.status_code == 200
    assert list_project_jobs_after_assign.json()["count"] == 2

    unassign_response = client.patch(
        f"/api/v1/jobs/{job_a_id}/project",
        json={"project_id": None},
    )
    assert unassign_response.status_code == 200
    assert unassign_response.json()["job"]["project_id"] is None

    list_project_jobs_after_unassign = client.get(f"/api/v1/jobs?project_id={project['id']}")
    assert list_project_jobs_after_unassign.status_code == 200
    assert list_project_jobs_after_unassign.json()["count"] == 1
    assert list_project_jobs_after_unassign.json()["jobs"][0]["id"] == job_b_id


def test_user_cannot_assign_job_to_other_users_project(client: TestClient) -> None:
    owner_email, owner_password = _register(client, "OwnerForCrossProject")
    owner_project = client.post("/api/v1/projects", json={"name": "Owner Project"}).json()["project"]
    owner_job = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": _job_url(), "project_id": owner_project["id"]},
    ).json()["job"]

    client.post("/api/v1/auth/logout")
    _register(client, "OtherProjectOwner")
    other_project = client.post("/api/v1/projects", json={"name": "Other Project"}).json()["project"]

    client.post("/api/v1/auth/logout")
    _login(client, owner_email, owner_password)

    response = client.patch(
        f"/api/v1/jobs/{owner_job['id']}/project",
        json={"project_id": other_project["id"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"

