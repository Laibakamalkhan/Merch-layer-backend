from __future__ import annotations

import psycopg.errors
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user
from commerce_connector.api.routers.database import _translate_error

USER_ID = "user-workspace-test"


class FakeDB:
    def __init__(self):
        self.error_to_raise: Exception | None = None

    def create_workspace_for_user(self, user_id: str, name: str, slug: str, timezone: str = "UTC"):
        if self.error_to_raise:
            raise self.error_to_raise
        return {"id": "ws-1", "name": name, "slug": slug, "timezone": timezone}


class FakeService:
    def __init__(self):
        self.db = FakeDB()


@pytest.fixture()
def client_and_service():
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=USER_ID, email="user@example.com", raw={})
    client = TestClient(app)
    yield client, service
    app.dependency_overrides.clear()


def test_create_workspace_duplicate_slug_returns_409(client_and_service):
    client, service = client_and_service
    service.db.error_to_raise = psycopg.errors.UniqueViolation("duplicate key value violates unique constraint")

    # /me/workspaces
    resp_me = client.post("/api/v1/me/workspaces", json={"name": "My Store", "slug": "my-store"})
    assert resp_me.status_code == 409
    assert resp_me.json()["detail"] == "Workspace slug already taken"

    # /tenants
    resp_tenant = client.post("/api/v1/tenants", json={"name": "My Store", "slug": "my-store"})
    assert resp_tenant.status_code == 409
    assert resp_tenant.json()["detail"] == "Workspace slug already taken"


def test_create_workspace_value_error_returns_400(client_and_service):
    client, service = client_and_service
    service.db.error_to_raise = ValueError("Slug must be lowercase alphanumeric")

    resp_me = client.post("/api/v1/me/workspaces", json={"name": "My Store", "slug": "INVALID SLUG"})
    assert resp_me.status_code == 400
    assert "Slug must be lowercase alphanumeric" in resp_me.json()["detail"]

    resp_tenant = client.post("/api/v1/tenants", json={"name": "My Store", "slug": "INVALID SLUG"})
    assert resp_tenant.status_code == 400
    assert "Slug must be lowercase alphanumeric" in resp_tenant.json()["detail"]


def test_create_workspace_unexpected_error_returns_500_without_leak(client_and_service):
    client, service = client_and_service
    sensitive_msg = "psql: error: connection to server at secret-host.internal failed"
    service.db.error_to_raise = RuntimeError(sensitive_msg)

    resp_me = client.post("/api/v1/me/workspaces", json={"name": "My Store", "slug": "my-store"})
    assert resp_me.status_code == 500
    assert resp_me.json()["detail"] == "Could not create workspace"
    assert sensitive_msg not in resp_me.text

    resp_tenant = client.post("/api/v1/tenants", json={"name": "My Store", "slug": "my-store"})
    assert resp_tenant.status_code == 500
    assert resp_tenant.json()["detail"] == "Could not create workspace"
    assert sensitive_msg not in resp_tenant.text


def test_database_translate_error_masks_internal_exceptions():
    err_404 = _translate_error(KeyError("record_not_found"))
    assert err_404.status_code == 404

    err_400 = _translate_error(ValueError("invalid filter argument"))
    assert err_400.status_code == 400
    assert err_400.detail == "invalid filter argument"

    sensitive_leak = "SELECT * FROM secret_internal_table WHERE failed"
    err_500 = _translate_error(RuntimeError(sensitive_leak))
    assert err_500.status_code == 500
    assert err_500.detail == "Query failed"
    assert sensitive_leak not in err_500.detail
