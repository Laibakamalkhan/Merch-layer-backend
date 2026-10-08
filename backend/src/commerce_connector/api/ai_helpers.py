"""Shared helpers for every endpoint that asks the AI analyst a question.

Both the older ``/ai/ask`` + ``/ai/stream`` routes and the newer
``/conversations/{id}/messages`` + ``/conversations/{id}/stream`` routes go
through here, so the plan limit, error mapping and SSE format stay identical.

IMPORTANT: ``AIAnalyst.ask`` already writes the user question and the assistant
answer into ``ai.messages`` when a ``conversation_id`` is passed. Callers must
NOT insert those messages themselves, otherwise every question is stored twice.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator
from uuid import UUID

import httpx
import psycopg
from fastapi import HTTPException

from commerce_connector.api.deps import get_api_settings
from commerce_connector.platform.groq import GroqAPIError, GroqTransportError


logger = logging.getLogger("commerce_connector.api")


def map_ai_exception(exc: Exception) -> HTTPException:
    """Turn any failure inside the AI flow into a clean HTTP error.

    Before this, only ValueError/RuntimeError were mapped; a Groq network
    error (httpx) or a database error (psycopg) escaped as a bare
    "500 Internal Server Error" with no message for the frontend.
    """
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, GroqTransportError):
        return HTTPException(
            status_code=502,
            detail=f"Could not establish a reliable HTTPS connection to Groq. {exc}",
        )
    if isinstance(exc, GroqAPIError):
        status = exc.status_code if 400 <= exc.status_code < 600 else 502
        return HTTPException(
            status_code=status,
            detail=f"Groq API returned HTTP {exc.status_code}. {exc.body[:1200]}",
        )
    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(status_code=504, detail="The AI provider (Groq) timed out. Please try again.")
    if isinstance(exc, httpx.HTTPError):
        return HTTPException(status_code=502, detail="Could not reach the AI provider (Groq). Check internet/API key and try again.")
    if isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)):
        return HTTPException(status_code=503, detail="Database connection problem. Please try again.")
    if isinstance(exc, psycopg.Error):
        return HTTPException(status_code=500, detail=f"Database error ({type(exc).__name__}). See backend logs.")
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Unexpected error ({type(exc).__name__}). See backend logs.")


def enforce_ai_limit(service: Any, tenant_id: UUID) -> None:
    """Raise HTTP 402 when a free-plan workspace used up its monthly AI queries."""
    tenant = service.db.get_tenant(tenant_id) or {}
    plan_code = str((tenant.get("metadata") or {}).get("plan_code") or "free")
    if plan_code != "free":
        return
    cfg = get_api_settings()
    usage = service.db.usage_summary(tenant_id, days=30)
    if int(usage.get("ai_queries") or 0) >= cfg.free_ai_query_limit_monthly:
        raise HTTPException(status_code=402, detail="Free plan AI query limit reached")


def _call_service_ask_ai(
    service: Any,
    *,
    tenant_id: UUID,
    question: str,
    user_id: str,
    conversation_id: UUID | None,
    reasoning: bool,
    model_id: str,
    file_ids: list[UUID],
    include_debug: bool = False,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "user_id": user_id,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "reasoning": reasoning,
        "model_id": model_id,
        "file_ids": [str(x) for x in file_ids],
    }
    import inspect
    supports_debug = False
    try:
        sig = inspect.signature(service.ask_ai)
        supports_debug = "include_debug" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
    except (ValueError, TypeError):
        supports_debug = True

    if supports_debug:
        kwargs["include_debug"] = bool(include_debug)

    return service.ask_ai(str(tenant_id), question, **kwargs)


def ask_ai_or_http_error(
    service: Any,
    *,
    tenant_id: UUID,
    question: str,
    user_id: str,
    conversation_id: UUID | None,
    reasoning: bool,
    model_id: str,
    file_ids: list[UUID],
    include_debug: bool = False,
) -> dict[str, Any]:
    """Run ``service.ask_ai`` and translate expected failures into HTTP errors."""
    try:
        return _call_service_ask_ai(
            service,
            tenant_id=tenant_id,
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            reasoning=reasoning,
            model_id=model_id,
            file_ids=file_ids,
            include_debug=include_debug,
        )
    except Exception as exc:
        logger.exception("AI request failed")
        raise map_ai_exception(exc) from exc


def sse_event(name: str, data: dict[str, Any]) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n".encode("utf-8")


async def ai_event_stream(
    service: Any,
    *,
    tenant_id: UUID,
    question: str,
    user_id: str,
    conversation_id: UUID | None,
    reasoning: bool,
    model_id: str,
    file_ids: list[UUID],
    include_debug: bool = False,
) -> AsyncIterator[bytes]:
    """Server-Sent Events: started -> status -> result -> done (or error -> done).

    The Groq planner returns structured JSON, so partial tokens are not
    streamed; the validated final result is sent as one ``result`` event.
    """
    yield sse_event("started", {"conversation_id": str(conversation_id) if conversation_id else None})
    yield sse_event("status", {"stage": "retrieving_context", "reasoning": reasoning})
    try:
        result = await asyncio.to_thread(
            _call_service_ask_ai,
            service,
            tenant_id=tenant_id,
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            reasoning=reasoning,
            model_id=model_id,
            file_ids=file_ids,
            include_debug=include_debug,
        )
        yield sse_event("result", result)
        yield sse_event("done", {"ok": True})
    except Exception as exc:  # surfaced to the client as an SSE error event
        logger.exception("AI stream failed")
        mapped = map_ai_exception(exc)
        yield sse_event("error", {"message": str(mapped.detail), "status_code": mapped.status_code})
        yield sse_event("done", {"ok": False})


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
