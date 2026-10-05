from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import DatasetIngestRequest, DatasetItemResponse
from commerce_connector.api.task_manager import TASKS
from commerce_connector.platform.datasets.parsers import parse_dataset_stream
from commerce_connector.platform.datasets.profiler import profile_dataset
from commerce_connector.platform.datasets.validator import SecurityValidationError, validate_file_security

logger = logging.getLogger("commerce_connector.api")
router = APIRouter(prefix="/datasets", tags=["Datasets & File Ingestion"])


def _safe_name(name: str) -> str:
    base = Path(name or "dataset").name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base[:180] or "dataset"


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    request: Request,
    tenant_id: UUID = Form(...),
    upload: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    if not service.user_files:
        raise HTTPException(status_code=503, detail="Supabase Storage is not configured on the backend")

    max_bytes = min(service.settings.max_user_file_bytes, 25 * 1024 * 1024)
    cl_header = request.headers.get("content-length")
    if cl_header and cl_header.isdigit() and int(cl_header) > max_bytes + 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {max_bytes} byte limit")

    chunk_size = 1024 * 1024
    chunks: list[bytes] = []
    total_bytes = 0
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(status_code=413, detail=f"File exceeds {max_bytes} byte limit")
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")

    filename = _safe_name(upload.filename or "dataset")
    content_type = upload.content_type or "application/octet-stream"

    try:
        file_type = validate_file_security(filename, content_type, data, max_bytes=max_bytes)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    checksum = hashlib.sha256(data).hexdigest()
    dataset_id = str(uuid4())
    storage_path = f"datasets/{tenant_id}/{dataset_id}/{filename}"

    try:
        # 1. Upload to Supabase Storage
        stored = await service.user_files.upload(storage_path, data, content_type)

        # 2. Fast Profile Sample Rows
        sample_rows = parse_dataset_stream(file_type, data, max_rows=5000)
        profile = profile_dataset(sample_rows)

        # 3. Create Dataset Record in Ingestion Schema
        dataset_row = await asyncio_to_thread_db(
            service.db.create_uploaded_dataset,
            tenant_id=str(tenant_id),
            created_by=current_user.id,
            filename=filename,
            file_type=file_type,
            storage_path=stored.path,
            byte_size=len(data),
            checksum_sha256=checksum,
        )

        # Update initial profiling stats
        quality_summary = {
            "validation_issues": profile.validation_issues,
            "has_validation_errors": profile.has_validation_errors,
        }
        updated_dataset = await asyncio_to_thread_db(
            service.db.update_dataset_profile,
            dataset_row["id"],
            str(tenant_id),
            status="profiled",
            has_validation_errors=profile.has_validation_errors,
            detected_entity=profile.detected_entity,
            profile_summary=profile.to_dict(),
            quality_summary=quality_summary,
            row_count=profile.row_count,
        )

        return {
            "dataset": updated_dataset,
            "profile": profile.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Dataset upload failed for tenant %s, user %s", tenant_id, current_user.id)
        raise HTTPException(status_code=500, detail="Dataset upload failed") from exc


@router.get("")
def list_datasets(
    tenant_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_uploaded_datasets(str(tenant_id), limit=limit, offset=offset)}


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: UUID,
    tenant_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    row = service.db.get_uploaded_dataset(str(dataset_id), str(tenant_id))
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return row


@router.post("/{dataset_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_dataset(
    dataset_id: UUID,
    payload: DatasetIngestRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    dataset = service.db.get_uploaded_dataset(str(dataset_id), str(payload.tenant_id))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if dataset.get("status") == "ingesting":
        raise HTTPException(status_code=409, detail="Dataset is already being ingested")

    if not service.user_files:
        raise HTTPException(status_code=503, detail="Supabase Storage is not configured")

    # Download raw file bytes
    try:
        raw_bytes = await service.user_files.download(dataset["storage_path"])
    except Exception as exc:
        logger.exception("Failed to download dataset storage file %s", dataset["storage_path"])
        raise HTTPException(status_code=500, detail="Could not retrieve stored dataset file") from exc

    tenant_id_str = str(payload.tenant_id)
    dataset_id_str = str(dataset_id)

    async def _run():
        return await service.datasets_engine.ingest_dataset(
            tenant_id=tenant_id_str,
            user_id=current_user.id,
            dataset_id=dataset_id_str,
            target_entity=payload.target_entity,
            column_mappings=payload.column_mappings,
            natural_key_column=payload.natural_key_column,
            raw_file_bytes=raw_bytes,
            rebuild_rag_after_sync=payload.rebuild_rag_after_sync,
            indexer=service.indexer,
        )

    task_state = TASKS.submit(
        _run,
        tenant_id=tenant_id_str,
        user_id=current_user.id,
    )

    return {
        "task_id": task_state.id,
        "dataset_id": dataset_id,
        "status": task_state.status,
    }


async def asyncio_to_thread_db(func, *args, **kwargs):
    import asyncio
    return await asyncio.to_thread(func, *args, **kwargs)
