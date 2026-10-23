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

# Same-tenant conversation/message fixtures for ai.messages authz tests
SHARED_TENANT = uuid.uuid4()
USER_X = str(uuid.uuid4())
USER_Y = str(uuid.uuid4())
CONV_X = uuid.uuid4()  # conversation owned by USER_X in SHARED_TENANT
CONV_Y = uuid.uuid4()  # conversation owned by USER_Y in SHARED_TENANT
MSG_X = uuid.uuid4()   # message in CONV_X (belongs to USER_X)
MSG_Y = uuid.uuid4()   # message in CONV_Y (belongs to USER_Y)

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
        # ai.conversations rows for same-tenant ownership tests
        self._ai_conversations = [
            {"id": str(CONV_X), "tenant_id": str(SHARED_TENANT), "user_id": USER_X, "title": "X conv", "created_at": "2026-10-01"},
            {"id": str(CONV_Y), "tenant_id": str(SHARED_TENANT), "user_id": USER_Y, "title": "Y conv", "created_at": "2026-10-01"},
        ]
        # ai.messages rows — no user_id column; ownership derived via conversation_id
        self._ai_messages = [
            {
                "id": str(MSG_X), "conversation_id": str(CONV_X),
                "tenant_id": str(SHARED_TENANT), "role": "user",
                "content": "secret-x", "metadata": {"key": "val-x"},
                "file_ids": ["file-x"], "created_at": "2026-10-01",
            },
            {
                "id": str(MSG_Y), "conversation_id": str(CONV_Y),
                "tenant_id": str(SHARED_TENANT), "role": "user",
                "content": "secret-y", "metadata": {"key": "val-y"},
                "file_ids": ["file-y"], "created_at": "2026-10-01",
            },
        ]
        # Column definitions used by the generic database endpoints
        self._table_columns = {
            ("ai", "messages"): [
                "id", "conversation_id", "tenant_id", "role",
                "content", "metadata", "file_ids", "created_at",
            ],
            ("ai", "conversations"): [
                "id", "tenant_id", "user_id", "title", "created_at",
            ],
        }

    # -- generic database endpoint helpers -----------------------------------
    def table_columns(self, schema, table):
        return list(self._table_columns.get((schema, table), []))

    def _filter_rows(self, rows, *, scope, tenant_column, tenant_id, user_id,
                     filters, owner_user_id=None, parent_schema=None,
                     parent_table=None, parent_fk=None,
                     parent_user_column="user_id", **_kw):
        """In-memory simulation of the SQL WHERE logic in the real gateway."""
        result = list(rows)
        if scope in {"tenant", "tenant_or_global"} and tenant_id is not None:
            result = [r for r in result if r.get(tenant_column) == str(tenant_id)]
        if scope == "user" and user_id is not None:
            uid_col = "user_id" if any("user_id" in r for r in result) else "id"
            result = [r for r in result if r.get(uid_col) == str(user_id)]
        # Parent-table ownership: simulate the EXISTS subquery
        if owner_user_id and parent_schema and parent_table and parent_fk:
            parent_rows = self._table_data(parent_schema, parent_table)
            owned_parent_ids = {
                r["id"] for r in parent_rows
                if r.get(parent_user_column) == str(owner_user_id)
                and r.get(tenant_column) == str(tenant_id)
            }
            result = [r for r in result if r.get(parent_fk) in owned_parent_ids]
        for key, value in (filters or {}).items():
            result = [r for r in result if r.get(key) == str(value)]
        return result

    def _table_data(self, schema, table):
        key = f"{schema}.{table}"
        if key == "ai.messages":
            return self._ai_messages
        if key == "ai.conversations":
            return self._ai_conversations
        return []

    def read_frontend_table(self, *, schema, table, scope, tenant_column="tenant_id",
                            tenant_id=None, user_id=None, filters=None,
                            hidden_columns=(), large_columns=(),
                            include_large_fields=False, limit=100, offset=0,
                            order_by=None, order_dir="desc", **kwargs):
        rows = self._table_data(schema, table)
        filtered = self._filter_rows(
            rows, scope=scope, tenant_column=tenant_column,
            tenant_id=tenant_id, user_id=user_id, filters=filters, **kwargs,
        )
        hidden_set = set(hidden_columns)
        large_set = set(large_columns)
        result = []
        for r in filtered[offset:offset + limit]:
            row = {
                k: v for k, v in r.items()
                if k not in hidden_set and (include_large_fields or k not in large_set)
            }
            result.append(row)
        return result

    def count_frontend_table(self, *, schema, table, scope, tenant_column="tenant_id",
                             tenant_id=None, user_id=None, filters=None,
                             hidden_columns=(), **kwargs):
        rows = self._table_data(schema, table)
        return len(self._filter_rows(
            rows, scope=scope, tenant_column=tenant_column,
            tenant_id=tenant_id, user_id=user_id, filters=filters, **kwargs,
        ))

    def get_frontend_record(self, *, schema, table, record_id, scope,
                            tenant_column="tenant_id", tenant_id=None,
                            user_id=None, hidden_columns=(), large_columns=(),
                            include_large_fields=True, **kwargs):
        rows = self.read_frontend_table(
            schema=schema, table=table, scope=scope,
            tenant_column=tenant_column, tenant_id=tenant_id,
            user_id=user_id, filters={"id": record_id},
            hidden_columns=hidden_columns, large_columns=large_columns,
            include_large_fields=include_large_fields, limit=1, offset=0,
            **kwargs,
        )
        return rows[0] if rows else None

    def is_tenant_member(self, tenant_id, user_id) -> bool:
        tenant = str(tenant_id)
        if user_id == USER_A:
            return tenant == str(TENANT_A)
        if user_id == USER_B:
            return tenant == str(TENANT_B)
        if user_id in {USER_X, USER_Y}:
            return tenant == str(SHARED_TENANT)
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



# ---------------------------------------------------------------------------
# Same-tenant ai.messages authorization tests
# ---------------------------------------------------------------------------
# USER_X and USER_Y are both members of SHARED_TENANT.  USER_X must not see
# USER_Y's messages (and vice-versa) even though they share a tenant.


def _shared_client(user_id: str) -> TestClient:
    """Client wired to FakeDB/FakeService with both users in SHARED_TENANT."""
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, email=f"{user_id}@example.com", raw={}
    )
    return TestClient(app, raise_server_exceptions=False)


class TestSameTenantMessageIsolation:
    """Verify that ai.messages ownership is enforced via parent conversation."""

    # -- LIST ----------------------------------------------------------------
    def test_list_returns_only_own_messages(self):
        client = _shared_client(USER_X)
        resp = client.get(
            "/api/v1/database/ai/messages",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = {item["id"] for item in items}
        assert str(MSG_X) in ids
        assert str(MSG_Y) not in ids

    def test_list_with_large_fields_does_not_leak_other_user(self):
        client = _shared_client(USER_X)
        resp = client.get(
            "/api/v1/database/ai/messages",
            params={"tenant_id": str(SHARED_TENANT), "include_large_fields": "true"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = {item["id"] for item in items}
        assert str(MSG_X) in ids
        assert str(MSG_Y) not in ids
        # Verify own content is present but other user's content is not
        all_text = str(items)
        assert "secret-x" in all_text
        assert "secret-y" not in all_text
        assert "val-y" not in all_text
        assert "file-y" not in all_text

    # -- COUNT ---------------------------------------------------------------
    def test_count_excludes_other_user_messages(self):
        client = _shared_client(USER_X)
        resp = client.get(
            "/api/v1/database/ai/messages/_count",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1  # only MSG_X

    # -- DETAIL --------------------------------------------------------------
    def test_detail_own_message_returns_200(self):
        client = _shared_client(USER_X)
        resp = client.get(
            f"/api/v1/database/ai/messages/{MSG_X}",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(MSG_X)

    def test_detail_other_user_message_returns_404(self):
        client = _shared_client(USER_X)
        resp = client.get(
            f"/api/v1/database/ai/messages/{MSG_Y}",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        assert resp.status_code == 404

    def test_detail_does_not_disclose_other_user_content(self):
        client = _shared_client(USER_X)
        resp = client.get(
            f"/api/v1/database/ai/messages/{MSG_Y}",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        text = resp.text
        assert "secret-y" not in text
        assert "val-y" not in text
        assert "file-y" not in text

    # -- QUERY (POST) --------------------------------------------------------
    def test_query_cannot_retrieve_other_user_messages_by_conversation(self):
        client = _shared_client(USER_X)
        resp = client.post(
            "/api/v1/database/query/ai/messages",
            json={
                "tenant_id": str(SHARED_TENANT),
                "filters": {"conversation_id": str(CONV_Y)},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_query_returns_own_messages(self):
        client = _shared_client(USER_X)
        resp = client.post(
            "/api/v1/database/query/ai/messages",
            json={
                "tenant_id": str(SHARED_TENANT),
                "filters": {"conversation_id": str(CONV_X)},
            },
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(MSG_X)

    def test_query_ignores_client_supplied_user_id(self):
        """Supplying user_id in the query body must not bypass ownership."""
        client = _shared_client(USER_X)
        resp = client.post(
            "/api/v1/database/query/ai/messages",
            json={
                "tenant_id": str(SHARED_TENANT),
                "user_id": USER_Y,
                "filters": {"conversation_id": str(CONV_Y)},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    # -- Cross-tenant still blocked ------------------------------------------
    def test_cross_tenant_messages_still_blocked(self):
        """USER_A (TENANT_A member) cannot access SHARED_TENANT messages."""
        client = _shared_client(USER_A)
        resp = client.get(
            "/api/v1/database/ai/messages",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        assert resp.status_code == 403

    # -- Symmetric check for USER_Y -----------------------------------------
    def test_user_y_cannot_see_user_x_messages(self):
        client = _shared_client(USER_Y)
        resp = client.get(
            "/api/v1/database/ai/messages",
            params={"tenant_id": str(SHARED_TENANT)},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = {item["id"] for item in items}
        assert str(MSG_Y) in ids
        assert str(MSG_X) not in ids
