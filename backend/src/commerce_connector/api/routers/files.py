from __future__ import annotations

import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.platform.user_files import extract_indexable_text

logger = logging.getLogger("commerce_connector.api")
router = APIRouter(prefix="/files", tags=["Files"])


def _safe_name(name: str) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base[:180] or "file"


@router.get("")
def list_files(
    tenant_id: UUID,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_file_documents(tenant_id, current_user.id, q=q, limit=limit, offset=offset)}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    tenant_id: UUID = Form(...),
    upload: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    if not service.user_files:
        raise HTTPException(status_code=503, detail="Supabase Storage is not configured on the backend")

    cl_header = request.headers.get("content-length")
    if cl_header and cl_header.isdigit():
        if int(cl_header) > service.settings.max_user_file_bytes + 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {service.settings.max_user_file_bytes} byte limit",
            )

    chunk_size = 1024 * 1024
    chunks: list[bytes] = []
    total_bytes = 0
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > service.settings.max_user_file_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {service.settings.max_user_file_bytes} byte limit",
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")

    filename = _safe_name(upload.filename or "file")
    object_path = f"{tenant_id}/{current_user.id}/{uuid4()}/{filename}"
    try:
        stored = await service.user_files.upload(object_path, data, upload.content_type or "application/octet-stream")
        text, index_status = extract_indexable_text(filename, stored.content_type, data)
        document = service.db.create_file_document(
            tenant_id,
            current_user.id,
            title=filename,
            content=text,
            content_hash=stored.sha256,
            metadata={
                "object_path": stored.path,
                "filename": filename,
                "mime_type": stored.content_type,
                "size_bytes": stored.byte_size,
                "bucket": service.settings.user_files_bucket,
                "index_status": index_status,
            },
        )
        if text.strip() and service.indexer:
            try:
                chunks = service.indexer.index_document(str(tenant_id), document)
                service.db.execute(
                    "update ai.documents set metadata=jsonb_set(metadata,'{index_status}','\"indexed\"'::jsonb,true),updated_at=now() where id=%s",
                    (document["id"],),
                )
                document["indexed_chunks"] = chunks
            except Exception as exc:
                service.db.execute(
                    "update ai.documents set metadata=jsonb_set(jsonb_set(metadata,'{index_status}','\"index_failed\"'::jsonb,true),'{index_error}',to_jsonb(%s::text),true),updated_at=now() where id=%s",
                    (str(exc)[:500], document["id"]),
                )
        return {"file": document, "storage": {"path": stored.path, "size_bytes": stored.byte_size, "content_type": stored.content_type}}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("File upload failed for tenant %s, user %s", tenant_id, current_user.id)
        raise HTTPException(status_code=500, detail="File upload failed") from exc


@router.get("/{file_id}")
def get_file(file_id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    row = service.db.get_file_document(file_id, tenant_id, current_user.id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    row = dict(row)
    row["content"] = None  # file listing endpoint never leaks indexed body by default
    return row


@router.post("/{file_id}/reindex")
def reindex_file(file_id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    row = service.db.get_file_document(file_id, tenant_id, current_user.id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    if not service.indexer:
        raise HTTPException(status_code=503, detail="Groq API key is required to initialize the AI/RAG service")
    if not str(row.get("content") or "").strip():
        raise HTTPException(status_code=400, detail="This file type has no extracted text to index")
    chunks = service.indexer.index_document(str(tenant_id), row)
    return {"indexed": True, "chunks": chunks}


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: UUID, tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    row = service.db.get_file_document(file_id, tenant_id, current_user.id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    path = (row.get("metadata") or {}).get("object_path")
    if path and service.user_files:
        await service.user_files.delete([path])
    service.db.delete_file_document(file_id, tenant_id, current_user.id)
    return None
