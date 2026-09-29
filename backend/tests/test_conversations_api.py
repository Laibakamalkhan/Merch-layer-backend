"""Behaviour tests for conversations / prompts / usage / health.

They use an in-memory fake service instead of Postgres + Supabase, so they run
anywhere. The fake mirrors what the real AIAnalyst does: ask_ai() itself stores
the user question and assistant answer when a conversation_id is given.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user

TENANT = str(uuid.uuid4())
OTHER_TENANT = str(uuid.uuid4())
ME = "user-me"
SOMEONE_ELSE = "user-other"


class FakeDB:
    def __init__(self):
        self.conversations = {}
        self.messages = []
        self.plan = "free"
        self.ai_queries = 0
        self.connections = []
        self.direct_add_message_calls = 0

    def is_tenant_member(self, tenant_id, user_id):
        return str(tenant_id) == TENANT

    def create_conversation(self, tenant_id, user_id, title=None, metadata=None):
        row = {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), "user_id": user_id, "title": title, "metadata": metadata or {}}
        self.conversations[row["id"]] = row
        return row

    def get_conversation(self, cid, tenant_id, user_id):
        row = self.conversations.get(str(cid))
        if row and row["tenant_id"] == str(tenant_id) and row["user_id"] == user_id:
            return row
        return None

    def list_conversations(self, tenant_id, user_id, **kw):
        return [r for r in self.conversations.values() if r["tenant_id"] == str(tenant_id) and r["user_id"] == user_id]

    def update_conversation(self, cid, tenant_id, user_id, **kw):
        row = self.get_conversation(cid, tenant_id, user_id)
        if row and kw.get("title"):
            row["title"] = kw["title"]
        return row

    def delete_conversation(self, cid, tenant_id, user_id):
        return bool(self.conversations.pop(str(cid), None)) if self.get_conversation(cid, tenant_id, user_id) else False

    def add_message(self, tenant_id, conversation_id, role, content, metadata=None):
        self.direct_add_message_calls += 1  # routes must never call this directly
        return self._store(conversation_id, role, content)

    def _store(self, conversation_id, role, content):
        msg = {"id": str(uuid.uuid4()), "conversation_id": str(conversation_id), "role": role, "content": content}
        self.messages.append(msg)
        return msg

    def list_messages(self, cid, tenant_id, **kw):
        return [m for m in self.messages if m["conversation_id"] == str(cid)]

    def get_tenant(self, tenant_id):
        return {"id": str(tenant_id), "metadata": {"plan_code": self.plan}}

    def usage_summary(self, tenant_id, days=30):
        return {"ai_queries": self.ai_queries, "connections": len(self.connections), "days": days}

    def list_connections(self, tenant_id):
        return self.connections


class FakeService:
    def __init__(self):
        self.db = FakeDB()
        self.ask_calls = []
        self.fail_with = None

    def ask_ai(self, tenant_id, question, *, user_id=None, conversation_id=None, reasoning=False, model_id="merchlayer-2.0", file_ids=None):
        self.ask_calls.append({"conversation_id": conversation_id, "question": question, "user_id": user_id})
        if self.fail_with:
            raise self.fail_with
        # what the real AIAnalyst does: it stores BOTH messages itself
        self.db._store(conversation_id, "user", question)
        self.db._store(conversation_id, "assistant", "Sales were 100.")
        return {"conversation_id": conversation_id, "answer": "Sales were 100.", "rows": []}


@pytest.fixture()
def env():
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ME, email="me@example.com", raw={})
    client = TestClient(app)
    yield client, service, app
    app.dependency_overrides.clear()


def _make_conversation(client):
    r = client.post("/api/v1/conversations", json={"tenant_id": TENANT, "title": "Hello"})
    assert r.status_code == 201
    return r.json()["id"]


def test_create_list_get_conversation(env):
    client, _, _ = env
    cid = _make_conversation(client)
    listing = client.get("/api/v1/conversations", params={"tenant_id": TENANT}).json()["items"]
    assert [c["id"] for c in listing] == [cid]
    got = client.get(f"/api/v1/conversations/{cid}", params={"tenant_id": TENANT})
    assert got.status_code == 200 and got.json()["title"] == "Hello"


def test_conversation_of_another_user_is_404_and_other_workspace_is_403(env):
    client, service, _ = env
    foreign = service.db.create_conversation(TENANT, SOMEONE_ELSE, "secret")
    assert client.get(f"/api/v1/conversations/{foreign['id']}", params={"tenant_id": TENANT}).status_code == 404
    assert client.get("/api/v1/conversations", params={"tenant_id": OTHER_TENANT}).status_code == 403
    assert client.post("/api/v1/conversations", json={"tenant_id": OTHER_TENANT}).status_code == 403


def test_send_message_returns_ai_answer_and_stores_each_message_exactly_once(env):
    client, service, _ = env
    cid = _make_conversation(client)
    r = client.post(f"/api/v1/conversations/{cid}/messages", json={"tenant_id": TENANT, "content": "How were sales?"})
    assert r.status_code == 201
    assert r.json()["answer"] == "Sales were 100."
    assert service.ask_calls[0]["conversation_id"] == cid
    assert service.ask_calls[0]["user_id"] == ME
    stored = client.get(f"/api/v1/conversations/{cid}/messages", params={"tenant_id": TENANT}).json()["items"]
    assert [m["role"] for m in stored] == ["user", "assistant"]  # no duplicates
    assert service.db.direct_add_message_calls == 0


def test_client_cannot_forge_an_assistant_message(env):
    client, service, _ = env
    cid = _make_conversation(client)
    r = client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"tenant_id": TENANT, "content": "hi there", "role": "assistant"},
    )
    assert r.status_code == 201
    assert service.db.direct_add_message_calls == 0
    assert [m["role"] for m in service.db.messages] == ["user", "assistant"]


def test_send_message_to_unknown_conversation_is_404(env):
    client, service, _ = env
    r = client.post(f"/api/v1/conversations/{uuid.uuid4()}/messages", json={"tenant_id": TENANT, "content": "hello"})
    assert r.status_code == 404
    assert service.ask_calls == []


def test_free_plan_limit_returns_402_and_does_not_call_ai(env):
    client, service, _ = env
    cid = _make_conversation(client)
    service.db.ai_queries = 100
    r = client.post(f"/api/v1/conversations/{cid}/messages", json={"tenant_id": TENANT, "content": "hello"})
    assert r.status_code == 402
    assert service.ask_calls == []
    assert client.post(f"/api/v1/conversations/{cid}/stream", json={"tenant_id": TENANT, "content": "hello"}).status_code == 402


def test_ai_errors_are_mapped(env):
    client, service, _ = env
    cid = _make_conversation(client)
    service.fail_with = RuntimeError("Groq API key is required")
    assert client.post(f"/api/v1/conversations/{cid}/messages", json={"tenant_id": TENANT, "content": "hello"}).status_code == 503
    service.fail_with = ValueError("Unsupported model_id: x")
    assert client.post(f"/api/v1/conversations/{cid}/messages", json={"tenant_id": TENANT, "content": "hello"}).status_code == 400


def _events(text):
    out = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n")
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_stream_emits_started_status_result_done(env):
    client, service, _ = env
    cid = _make_conversation(client)
    r = client.post(f"/api/v1/conversations/{cid}/stream", json={"tenant_id": TENANT, "content": "How were sales?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    assert [n for n, _ in events] == ["started", "status", "result", "done"]
    assert events[0][1]["conversation_id"] == cid
    assert events[2][1]["answer"] == "Sales were 100."
    assert events[3][1] == {"ok": True}
    assert service.db.direct_add_message_calls == 0


def test_stream_reports_ai_failure_as_error_event(env):
    client, service, _ = env
    cid = _make_conversation(client)
    service.fail_with = Exception("boom")
    events = _events(client.post(f"/api/v1/conversations/{cid}/stream", json={"tenant_id": TENANT, "content": "hello"}).text)
    assert [n for n, _ in events] == ["started", "status", "error", "done"]
    assert events[-1][1] == {"ok": False}


def test_update_and_delete_conversation(env):
    client, _, _ = env
    cid = _make_conversation(client)
    assert client.patch(f"/api/v1/conversations/{cid}", json={"tenant_id": TENANT, "title": "Renamed"}).json()["title"] == "Renamed"
    assert client.delete(f"/api/v1/conversations/{cid}", params={"tenant_id": TENANT}).status_code == 204
    assert client.get(f"/api/v1/conversations/{cid}", params={"tenant_id": TENANT}).status_code == 404


def test_old_ai_ask_route_still_works_after_refactor(env):
    client, service, _ = env
    cid = _make_conversation(client)
    r = client.post("/api/v1/ai/ask", json={"tenant_id": TENANT, "question": "How were sales?", "conversation_id": cid})
    assert r.status_code == 200 and r.json()["answer"] == "Sales were 100."


def test_prompts_without_tenant_returns_general_prompts(env):
    client, _, _ = env
    body = client.get("/api/v1/prompts").json()
    assert len(body["items"]) >= 5
    assert body["context"] is None
    assert all({"id", "title", "text", "category"} <= set(p) for p in body["items"])
    assert "min_connections" not in body["items"][0]


def test_prompts_are_tailored_to_connected_stores(env):
    client, service, _ = env
    none = client.get("/api/v1/prompts", params={"tenant_id": TENANT}).json()
    assert none["context"]["connections"] == 0
    assert len(none["items"]) >= 5  # a brand-new workspace must NOT get an empty list
    assert "channels-compare" not in [p["id"] for p in none["items"]]
    service.db.connections = [{"platform_code": "shopify"}]
    one = client.get("/api/v1/prompts", params={"tenant_id": TENANT}).json()
    assert "channels-compare" not in [p["id"] for p in one["items"]]
    service.db.connections = [{"platform_code": "shopify"}, {"platform_code": "amazon"}]
    two = client.get("/api/v1/prompts", params={"tenant_id": TENANT}).json()
    assert "channels-compare" in [p["id"] for p in two["items"]]
    assert two["context"]["connected_platforms"] == ["amazon", "shopify"]
    only_sales = client.get("/api/v1/prompts", params={"tenant_id": TENANT, "category": "sales"}).json()["items"]
    assert only_sales and {p["category"] for p in only_sales} == {"sales"}
    assert client.get("/api/v1/prompts", params={"tenant_id": OTHER_TENANT}).status_code == 403


def test_usage_alias_matches_subscription_usage(env):
    client, service, _ = env
    service.db.ai_queries = 7
    a = client.get("/api/v1/usage", params={"tenant_id": TENANT, "days": 7}).json()
    b = client.get("/api/v1/subscription/usage", params={"tenant_id": TENANT, "days": 7}).json()
    assert a == b and a["ai_queries"] == 7 and a["days"] == 7
    assert client.get("/api/v1/usage", params={"tenant_id": OTHER_TENANT}).status_code == 403
    assert client.get("/api/v1/usage", params={"tenant_id": TENANT, "days": 0}).status_code == 422


def test_ready_returns_ok_when_database_answers_and_503_when_it_fails(env):
    client, service, _ = env
    service.health = lambda: {"database": "postgres"}
    assert client.get("/api/v1/health/ready").json() == {"status": "ok", "database": {"database": "postgres"}}

    def boom():
        raise ConnectionError("db down")

    service.health = boom
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503 and "ConnectionError" in r.json()["detail"]


def test_health_is_up_even_without_database_but_ready_reports_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    deps.reset_cached_dependencies()
    client = TestClient(create_app())
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").status_code == 503
    deps.reset_cached_dependencies()


def test_protected_routes_require_a_bearer_token():
    client = TestClient(create_app())
    for method, path in [("get", "/api/v1/prompts"), ("get", "/api/v1/usage?tenant_id=" + TENANT), ("get", "/api/v1/conversations?tenant_id=" + TENANT)]:
        assert getattr(client, method)(path).status_code == 401


def test_provider_and_database_failures_become_clean_json_errors(env):
    """Groq network errors / DB errors used to escape as a bare 500 with no message."""
    import httpx
    import psycopg

    client, service, _ = env
    cid = _make_conversation(client)
    url = f"/api/v1/conversations/{cid}/messages"
    body = {"tenant_id": TENANT, "content": "hello"}

    service.fail_with = httpx.ReadTimeout("slow")
    r = client.post(url, json=body)
    assert r.status_code == 504 and "timed out" in r.json()["detail"]

    service.fail_with = httpx.ConnectError("no internet")
    r = client.post(url, json=body)
    assert r.status_code == 502 and "Groq" in r.json()["detail"]

    service.fail_with = psycopg.OperationalError("connection dropped")
    r = client.post(url, json=body)
    assert r.status_code == 503 and "Database" in r.json()["detail"]

    service.fail_with = KeyError("surprise")
    r = client.post(url, json=body)
    assert r.status_code == 500 and "KeyError" in r.json()["detail"]
