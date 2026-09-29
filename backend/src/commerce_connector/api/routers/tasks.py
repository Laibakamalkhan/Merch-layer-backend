from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import MessageCreate, TaskCreate, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks & Conversations"])


@router.get("")
def list_tasks(
    tenant_id: UUID,
    q: str | None = None,
    archived: bool | None = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_conversations(tenant_id, current_user.id, q=q, archived=archived, limit=limit, offset=offset)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    return service.db.create_conversation(payload.tenant_id, current_user.id, payload.title, payload.metadata)


@router.get("/{task_id}")
def get_task(task_id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    task = service.db.get_conversation(task_id, tenant_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}")
def update_task(task_id: UUID, payload: TaskUpdate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    row = service.db.update_conversation(
        task_id,
        payload.tenant_id,
        current_user.id,
        title=payload.title,
        archived=payload.archived,
        pinned=payload.pinned,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    if not service.db.delete_conversation(task_id, tenant_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    return None


@router.get("/{task_id}/messages")
def task_messages(
    task_id: UUID,
    tenant_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    before: datetime | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    if not service.db.get_conversation(task_id, tenant_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"items": service.db.list_messages(task_id, tenant_id, limit=limit, before=before)}


@router.post("/{task_id}/messages", status_code=status.HTTP_201_CREATED)
def add_task_message(task_id: UUID, payload: MessageCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    if not service.db.get_conversation(task_id, payload.tenant_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    return service.db.add_message(payload.tenant_id, task_id, payload.role, payload.content, payload.metadata)
