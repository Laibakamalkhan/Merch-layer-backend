from __future__ import annotations

import asyncio
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


class BackgroundTaskManager:
    def __init__(self) -> None:
        self._states: dict[str, TaskState] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(self, factory: Callable[[], Awaitable[Any]]) -> TaskState:
        task_id = str(uuid4())
        state = TaskState(id=task_id)
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

        self._tasks[task_id] = asyncio.create_task(runner())
        return state

    def get(self, task_id: str) -> TaskState | None:
        return self._states.get(task_id)


TASKS = BackgroundTaskManager()
