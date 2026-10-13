from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user

USER_A = "user-a"
USER_B = "user-b"
TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
CONN_A = uuid.uuid4()
CONN_B = uuid.uuid4()
MISSING_CONN = uuid.uuid4()
DASH_A = uuid.uuid4()
DASH_B = uuid.uuid4()
JOB_A = uuid.uuid4()
JOB_B = uuid.uuid4()
CONV_A = uuid.uuid4()
CONV_B = uuid.uuid4()

_SECRET_KEY_MARKERS = ("secret", "token", "password", "api_key")


def _conn_row(conn_id, tenant_id):
    return {
        "id": str(conn_id),
        "tenant_id": str(tenant_id),
        "platform_code": "shopify",
        "name": "store",
        "base_url": "https://store.example.com",
        "config": {},
        "api_key": "leaked-if-returned",
        "access_token": "leaked-if-returned",
        "password": "leaked-if-returned",
        "client_secret": "leaked-if-returned",
    }


class FakeDB:
    def __init__(self):
        self.connections = {
            str(CONN_A): _conn_row(CONN_A, TENANT_A),
            str(CONN_B): _conn_row(CONN_B, TENANT_B),
        }
        self.dashboards = {
            str(DASH_A): {"id": str(DASH_A), "tenant_id": str(TENANT_A), "name": "A"},
            str(DASH_B): {"id": str(DASH_B), "tenant_id": str(TENANT_B), "name": "B"},
        }
        self.jobs = {
            str(JOB_A): {"id": str(JOB_A), "tenant_id": str(TENANT_A)},
            str(JOB_B): {"id": str(JOB_B), "tenant_id": str(TENANT_B)},
        }
        self.conversations = {
            str(CONV_A): {"id": str(CONV_A), "tenant_id": str(TENANT_A), "user_id": USER_A, "title": "A"},
            str(CONV_B): {"id": str(CONV_B), "tenant_id": str(TENANT_B), "user_id": USER_B, "title": "B"},
        }
        self.tenants = {
            str(TENANT_A): {"id": str(TENANT_A), "metadata": {"plan_code": "free"}},
            str(TENANT_B): {"id": str(TENANT_B), "metadata": {"plan_code": "free"}},
        }

    def is_tenant_member(self, tenant_id, user_id) -> bool:
        tenant = str(tenant_id)
        if user_id == USER_A:
            return tenant == str(TENANT_A)
        if user_id == USER_B:
            return tenant == str(TENANT_B)
        return False

    def get_connection(self, connection_id):
        row = self.connections.get(str(connection_id))
        if row is None:
            raise KeyError(connection_id)
        return row

    def list_connections(self, tenant_id):
        tid = str(tenant_id)
        return [c for c in self.connections.values() if c["tenant_id"] == tid]

    def update_connection_basics(self, connection_id, name, base_url, config):
        return None

    def get_connection_resources(self, connection_id, enabled_only=False):
        return [{"resource_key": "orders", "enabled": True}]

    def update_connection_resource(self, connection_id, resource_key, enabled, sync_mode):
        return True

    def store_secret(self, tenant_id, connection_id, key, value):
        return None

    def get_dashboard(self, dashboard_id):
        return self.dashboards.get(str(dashboard_id))

    def get_job(self, job_id):
        return self.jobs.get(str(job_id))

    def list_job_connections(self, job_id):
        return []

    def list_runs(self, job_id):
        return []

    def list_stage_runs(self, job_id):
        return []

    def list_job_events(self, job_id):
        return []

    def get_conversation(self, conversation_id, tenant_id, user_id):
        row = self.conversations.get(str(conversation_id))
        if not row or row["tenant_id"] != str(tenant_id) or row["user_id"] != user_id:
            return None
        return row

    def get_tenant(self, tenant_id):
        return self.tenants.get(str(tenant_id))

    def usage_summary(self, tenant_id, days=30):
        return {"connections": 1, "ai_queries": 0}


class FakeService:
    def __init__(self):
        self.db = FakeDB()

    async def test_connection(self, connection_id: str):
        return {"ok": True, "connection_id": connection_id}

    async def run_pipeline(self, tenant_id, connection_ids, rebuild_rag_after_sync=False):
        return {"ok": True, "tenant_id": tenant_id, "connection_ids": connection_ids}


def _client(user_id: str) -> TestClient:
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, email=f"{user_id}@example.com", raw={}
    )
    return TestClient(app, raise_server_exceptions=False)


def _forbidden_cases():
    return [
        ("GET", f"/api/v1/connections?tenant_id={TENANT_B}", None),
        ("GET", f"/api/v1/connections/{CONN_B}", None),
        ("GET", f"/api/v1/dashboards/{DASH_B}", None),
        ("GET", f"/api/v1/sync/jobs/{JOB_B}", None),
        ("GET", f"/api/v1/conversations/{CONV_B}?tenant_id={TENANT_B}", None),
        ("POST", "/api/v1/sync/run", {"tenant_id": str(TENANT_B), "connection_ids": [str(CONN_B)]}),
        ("GET", f"/api/v1/subscription?tenant_id={TENANT_B}", None),
    ]


def _member_success_cases():
    return [
        ("GET", f"/api/v1/connections?tenant_id={TENANT_A}", None, 200),
        ("GET", f"/api/v1/connections/{CONN_A}", None, 200),
        ("GET", f"/api/v1/dashboards/{DASH_A}", None, 200),
        ("GET", f"/api/v1/sync/jobs/{JOB_A}", None, 200),
        ("GET", f"/api/v1/conversations/{CONV_A}?tenant_id={TENANT_A}", None, 200),
        ("POST", "/api/v1/sync/run", {"tenant_id": str(TENANT_A), "connection_ids": [str(CONN_A)]}, 200),
        ("GET", f"/api/v1/subscription?tenant_id={TENANT_A}", None, 200),
        ("PATCH", f"/api/v1/connections/{CONN_A}", {}, 200),
        ("GET", f"/api/v1/connections/{CONN_A}/resources", None, 200),
        ("PATCH", f"/api/v1/connections/{CONN_A}/resources/orders", {"enabled": True}, 200),
        ("POST", f"/api/v1/connections/{CONN_A}/test", None, 200),
        (
            "POST",
            f"/api/v1/connections/{CONN_A}/credentials",
            {"tenant_id": str(TENANT_A), "secrets": {"token": "abc"}},
            200,
        ),
    ]


def _missing_connection_cases():
    cid = MISSING_CONN
    return [
        ("GET", f"/api/v1/connections/{cid}", None),
        ("PATCH", f"/api/v1/connections/{cid}", {}),
        ("GET", f"/api/v1/connections/{cid}/resources", None),
        ("PATCH", f"/api/v1/connections/{cid}/resources/orders", {"enabled": True}),
        ("POST", f"/api/v1/connections/{cid}/test", None),
        (
            "POST",
            f"/api/v1/connections/{cid}/credentials",
            {"tenant_id": str(TENANT_A), "secrets": {"token": "abc"}},
        ),
    ]


def _request(client: TestClient, method: str, path: str, body):
    if method == "GET":
        return client.get(path)
    if method == "PATCH":
        return client.patch(path, json=body)
    return client.post(path, json=body)


@pytest.mark.parametrize("method,path,body", _forbidden_cases())
def test_user_a_cannot_access_tenant_b(method, path, body):
    resp = _request(_client(USER_A), method, path, body)
    assert resp.status_code == 403


@pytest.mark.parametrize("method,path,body", _missing_connection_cases())
def test_missing_connection_returns_404_not_500(method, path, body):
    resp = _request(_client(USER_A), method, path, body)
    assert resp.status_code == 404
    assert resp.status_code != 500


@pytest.mark.parametrize("method,path,body,ok", _member_success_cases())
def test_member_of_tenant_a_is_allowed(method, path, body, ok):
    resp = _request(_client(USER_A), method, path, body)
    assert resp.status_code == ok


def test_get_connection_does_not_leak_secret_keys():
    resp = _client(USER_A).get(f"/api/v1/connections/{CONN_A}")
    assert resp.status_code == 200
    payload = resp.json()
    leaked = [k for k in _walk_keys(payload) if any(m in k.lower() for m in _SECRET_KEY_MARKERS)]
    assert leaked == [], f"GET /connections/{{id}} leaked secret-like keys: {leaked}"


def _walk_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)
