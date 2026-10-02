from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4


@dataclass(slots=True)
class TaskState:
    id: str
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    result: Any = None
    error: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None


def _get_retention_seconds() -> float:
    try:
        val = int(os.getenv("TASK_RETENTION_SECONDS", "3600"))
        return float(max(val, 60))
    except Exception:
        return 3600.0


class BackgroundTaskManager:
    def __init__(self) -> None:
        self._states: dict[str, TaskState] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def prune(self) -> None:
        now = datetime.now(timezone.utc)
        retention = _get_retention_seconds()
        expired: list[str] = []
        for task_id, state in list(self._states.items()):
            if state.status in ("completed", "failed") and state.finished_at:
                try:
                    finished = datetime.fromisoformat(state.finished_at)
                    if (now - finished).total_seconds() > retention:
                        expired.append(task_id)
                except Exception:
                    pass
        for task_id in expired:
            self._states.pop(task_id, None)
            self._tasks.pop(task_id, None)

        for task_id, task in list(self._tasks.items()):
            if task.done():
                self._tasks.pop(task_id, None)

    def submit(
        self,
        factory: Callable[[], Awaitable[Any]],
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> TaskState:
        self.prune()
        task_id = str(uuid4())
        state = TaskState(id=task_id, tenant_id=tenant_id, user_id=user_id)
        self._states[task_id] = state

        async def runner() -> None:
            state.status = "running"
            state.started_at = datetime.now(timezone.utc).isoformat()
            try:
                state.result = await factory()
                state.status = "completed"
            except Exception as exc:  # persisted job/run errors remain in Postgres as well
                state.error = f"{type(exc).__name__}: {exc}"
                state.status = "failed"
            finally:
                state.finished_at = datetime.now(timezone.utc).isoformat()
                self._tasks.pop(task_id, None)

        self._tasks[task_id] = asyncio.create_task(runner())
        return state

    def get(self, task_id: str) -> TaskState | None:
        return self._states.get(task_id)


TASKS = BackgroundTaskManager()
