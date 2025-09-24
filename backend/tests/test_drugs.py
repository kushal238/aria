import os
import json
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.routers import drugs


def _auth_headers():
    # For local test runs without API Gateway authorizer context, we skip auth by simulating failure path.
    # In deployed env, API Gateway enforces Cognito; here we just pass a dummy header.
    return {"Authorization": "Bearer dummy"}


client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    # Override the Cognito dependency so tests don't require API Gateway context
    app.dependency_overrides[drugs.get_cognito_user_info] = lambda: {"sub": "test-user"}
    yield
    app.dependency_overrides.clear()


def test_search_requires_query_param():
    r = client.get("/drugs/search", headers=_auth_headers())
    assert r.status_code in (400, 422)


def test_search_min_length():
    r = client.get("/drugs/search?q=a", headers=_auth_headers())
    assert r.status_code in (400, 422)


def test_search_limit_guardrail():
    r = client.get("/drugs/search?q=para&limit=1000", headers=_auth_headers())
    assert r.status_code in (400, 422)


def test_search_success_mocked(monkeypatch):
    # Mock connection + run calls to avoid DB dependency
    class DummyConn:
        def run(self, sql, params=None):
            if "ILIKE" in sql:
                return [
                    [111, "Paracetamol 500 mg", 222, "APPROVED"],
                ]
            else:
                return [
                    [333, "Paracet", 222, "APPROVED"],
                ]
        def close(self):
            pass

    from app.routers import drugs
    monkeypatch.setenv("DB_HOST", "dummy")
    monkeypatch.setenv("DB_SECRET_ARN", "dummy")
    monkeypatch.setenv("DB_NAME", "drugindex")

    def fake_get_db_creds(secret_arn, region=None):
        return ("u", "p")

    def fake_get_conn():
        return DummyConn()

    monkeypatch.setattr(drugs, "_get_db_creds", fake_get_db_creds)
    monkeypatch.setattr(drugs, "_get_conn", fake_get_conn)

    # Auth already overridden by fixture

    r = client.get("/drugs/search?q=para&limit=5", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["brand_name"].lower().startswith("para")

