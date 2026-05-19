from fastapi.testclient import TestClient

from setiq.main import app


def test_health() -> None:
    # No context manager → lifespan not triggered, so no DB connection needed.
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body
