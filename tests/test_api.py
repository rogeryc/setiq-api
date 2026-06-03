from fastapi.testclient import TestClient

from setiq.main import app

CREDS = {"email": "thalma@example.com", "password": "changeme123"}


def _auth_header(client: TestClient) -> dict[str, str]:
    resp = client.post("/auth/login", json=CREDS)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_login_me_refresh_logout() -> None:
    with TestClient(app) as client:
        headers = _auth_header(client)

        me = client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["tenant"]["slug"] == "thalma"

        refreshed = client.post("/auth/refresh", headers=headers)
        assert refreshed.status_code == 200
        assert refreshed.json()["access_token"]

        assert client.post("/auth/logout", headers=headers).status_code == 204
        # The token is revoked after logout.
        assert client.get("/auth/me", headers=headers).status_code == 401


def test_me_requires_token() -> None:
    with TestClient(app) as client:
        assert client.get("/auth/me").status_code == 401


def test_tracked_subject_roundtrip() -> None:
    with TestClient(app) as client:
        headers = _auth_header(client)

        created = client.post(
            "/tracked-subjects",
            headers=headers,
            json={"kind": "competitor", "label": "CI Roundtrip Subject"},
        )
        assert created.status_code == 201, created.text
        subject_id = created.json()["id"]

        listed = client.get("/tracked-subjects", headers=headers)
        assert any(s["id"] == subject_id for s in listed.json())

        detail = client.get(f"/tracked-subjects/{subject_id}/detail", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["label"] == "CI Roundtrip Subject"

        assert client.delete(f"/tracked-subjects/{subject_id}", headers=headers).status_code == 204


def test_search_returns_hits() -> None:
    with TestClient(app) as client:
        headers = _auth_header(client)
        resp = client.get("/search", params={"q": "thalma"}, headers=headers)
        assert resp.status_code == 200
        assert "hits" in resp.json()


def test_competitor_activity() -> None:
    with TestClient(app) as client:
        headers = _auth_header(client)
        resp = client.get("/dashboard/competitor-activity", headers=headers)
        assert resp.status_code == 200
        assert "competitors" in resp.json()
