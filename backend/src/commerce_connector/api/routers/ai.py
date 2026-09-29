from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.ai_helpers import SSE_HEADERS, ai_event_stream, ask_ai_or_http_error, enforce_ai_limit
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import AIQuestionRequestV2, RAGRebuildRequest

router = APIRouter(prefix="/ai", tags=["AI & RAG"])


@router.post("/rag/rebuild")
def rebuild_rag(payload: RAGRebuildRequest, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    try:
        return service.rebuild_rag(str(payload.tenant_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/rag/status")
def rag_status(tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return service.db.rag_status(tenant_id)


@router.post("/ask")
def ask_ai(payload: AIQuestionRequestV2, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    enforce_ai_limit(service, payload.tenant_id)
    return ask_ai_or_http_error(
        service,
        tenant_id=payload.tenant_id,
        question=payload.question,
        user_id=current_user.id,
        conversation_id=payload.conversation_id,
        reasoning=payload.reasoning,
        model_id=payload.model_id,
        file_ids=payload.file_ids,
    )


@router.post("/stream")
async def stream_ai(payload: AIQuestionRequestV2, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    """SSE endpoint for the chat UI (see ``ai_helpers.ai_event_stream``)."""
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    enforce_ai_limit(service, payload.tenant_id)
    return StreamingResponse(
        ai_event_stream(
            service,
            tenant_id=payload.tenant_id,
            question=payload.question,
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            reasoning=payload.reasoning,
            model_id=payload.model_id,
            file_ids=payload.file_ids,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/queries")
def query_history(tenant_id: UUID, limit: int = 50, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_query_runs(tenant_id, min(max(limit, 1), 200), current_user.id)}


@router.get("/semantic-catalog")
def semantic_catalog(tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return service.db.semantic_catalog_snapshot(tenant_id)
