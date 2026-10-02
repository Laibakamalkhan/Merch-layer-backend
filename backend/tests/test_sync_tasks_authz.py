from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user
from commerce_connector.api.task_manager import TASKS, TaskState

MEMBER_USER = "user-member"
NON_MEMBER_USER = "user-other"
TENANT_ID = str(uuid.uuid4())


class FakeDB:
    def is_tenant_member(self, tenant_id: str, user_id: str) -> bool:
        return str(tenant_id) == TENANT_ID and user_id == MEMBER_USER


class FakeService:
    def __init__(self):
        self.db = FakeDB()


@pytest.fixture()
def client_factory():
    def _create(user_id: str):
        service = FakeService()
        app = create_app()
        app.dependency_overrides[deps.get_service] = lambda: service
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id, email=f"{user_id}@example.com", raw={})
        return TestClient(app)

    return _create


def test_member_gets_200_and_sees_status_result(client_factory):
    client = client_factory(MEMBER_USER)
    task_id = str(uuid.uuid4())
    TASKS._states[task_id] = TaskState(
        id=task_id,
        status="completed",
        result={"synced": 42},
        tenant_id=TENANT_ID,
        user_id=MEMBER_USER,
    )

    resp = client.get(f"/api/v1/sync/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"] == {"synced": 42}
    assert data["error"] is None


def test_non_member_gets_404(client_factory):
    client = client_factory(NON_MEMBER_USER)
    task_id = str(uuid.uuid4())
    TASKS._states[task_id] = TaskState(
        id=task_id,
        status="completed",
        result={"synced": 42},
        tenant_id=TENANT_ID,
        user_id=MEMBER_USER,
    )

    resp = client.get(f"/api/v1/sync/tasks/{task_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


def test_unknown_task_id_gets_404(client_factory):
    client = client_factory(MEMBER_USER)
    resp = client.get(f"/api/v1/sync/tasks/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


def test_legacy_task_without_tenant_id_gets_404(client_factory):
    client = client_factory(MEMBER_USER)
    task_id = str(uuid.uuid4())
    TASKS._states[task_id] = TaskState(
        id=task_id,
        status="completed",
        result="done",
        tenant_id=None,
    )

    resp = client.get(f"/api/v1/sync/tasks/{task_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


def test_task_prune_removes_old_finished_tasks(monkeypatch):
    monkeypatch.setenv("TASK_RETENTION_SECONDS", "60")

    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(seconds=120)).isoformat()
    recent_time = (now - timedelta(seconds=10)).isoformat()

    old_id = "old-finished-task"
    recent_id = "recent-finished-task"
    running_id = "running-task"

    TASKS._states[old_id] = TaskState(
        id=old_id,
        status="completed",
        finished_at=old_time,
        tenant_id=TENANT_ID,
    )
    TASKS._states[recent_id] = TaskState(
        id=recent_id,
        status="completed",
        finished_at=recent_time,
        tenant_id=TENANT_ID,
    )
    TASKS._states[running_id] = TaskState(
        id=running_id,
        status="running",
        finished_at=None,
        tenant_id=TENANT_ID,
    )

    TASKS.prune()

    assert old_id not in TASKS._states
    assert recent_id in TASKS._states
    assert running_id in TASKS._states
