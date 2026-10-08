"""Chat conversations (the UI's "conversation" == the database's ai.conversations).

Same data as the older ``/tasks`` routes, which stay available for backward
compatibility. The important difference is ``POST /{id}/messages``: it takes the
user's question, asks the AI, and returns the answer. The user message and the
assistant message are both saved by the AI analyst, so nothing is stored twice.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from commerce_connector.api.ai_helpers import SSE_HEADERS, ai_event_stream, ask_ai_or_http_error, enforce_ai_limit
from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import ConversationMessageCreate, TaskCreate, TaskUpdate

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _owned_conversation(service, current_user: CurrentUser, conversation_id: UUID, tenant_id: UUID) -> dict:
    """Tenant check + ownership check. 403 for foreign workspace, 404 for foreign/missing conversation."""
    require_tenant_access(service, current_user.id, str(tenant_id))
    row = service.db.get_conversation(conversation_id, tenant_id, current_user.id)
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


@router.post("", status_code=status.HTTP_201_CREATED)
def create_conversation(payload: TaskCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    return service.db.create_conversation(payload.tenant_id, current_user.id, payload.title, payload.metadata)


@router.get("")
def list_conversations(
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


@router.get("/{id}")
def get_conversation(id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    return _owned_conversation(service, current_user, id, tenant_id)


@router.patch("/{id}")
def update_conversation(id: UUID, payload: TaskUpdate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    _owned_conversation(service, current_user, id, payload.tenant_id)
    row = service.db.update_conversation(id, payload.tenant_id, current_user.id, title=payload.title, archived=payload.archived, pinned=payload.pinned)
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    _owned_conversation(service, current_user, id, tenant_id)
    if not service.db.delete_conversation(id, tenant_id, current_user.id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None


@router.get("/{id}/messages")
def list_messages(
    id: UUID,
    tenant_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    before: datetime | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    _owned_conversation(service, current_user, id, tenant_id)
    return {"items": service.db.list_messages(id, tenant_id, limit=limit, before=before)}


@router.post("/{id}/messages", status_code=status.HTTP_201_CREATED)
def send_message(id: UUID, payload: ConversationMessageCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    """Send a question and get the AI answer in one call (both messages are saved)."""
    _owned_conversation(service, current_user, id, payload.tenant_id)
    enforce_ai_limit(service, payload.tenant_id)
    return ask_ai_or_http_error(
        service,
        tenant_id=payload.tenant_id,
        question=payload.content,
        user_id=current_user.id,
        conversation_id=id,
        reasoning=payload.reasoning,
        model_id=payload.model_id,
        file_ids=payload.file_ids,
        include_debug=payload.include_debug,
    )


@router.post("/{id}/stream")
async def stream_message(id: UUID, payload: ConversationMessageCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    """Same as ``POST /{id}/messages`` but delivered as Server-Sent Events."""
    _owned_conversation(service, current_user, id, payload.tenant_id)
    enforce_ai_limit(service, payload.tenant_id)
    return StreamingResponse(
        ai_event_stream(
            service,
            tenant_id=payload.tenant_id,
            question=payload.content,
            user_id=current_user.id,
            conversation_id=id,
            reasoning=payload.reasoning,
            model_id=payload.model_id,
            file_ids=payload.file_ids,
            include_debug=payload.include_debug,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
