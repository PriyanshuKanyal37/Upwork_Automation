from fastapi.testclient import TestClient


def test_health_root(client: TestClient) -> None:
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"


def test_health_v1(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
