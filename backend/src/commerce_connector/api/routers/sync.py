from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import SyncRequest
from commerce_connector.api.task_manager import TASKS

router = APIRouter(prefix="/sync", tags=["Sync & Pipeline"])


@router.post("/run")
async def run_sync(payload: SyncRequest, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    for connection_id in payload.connection_ids:
        connection = service.db.get_connection(connection_id)
        if str(connection["tenant_id"]) != str(payload.tenant_id):
            raise HTTPException(status_code=400, detail=f"Connection {connection_id} does not belong to workspace")
    return await service.run_pipeline(
        tenant_id=str(payload.tenant_id),
        connection_ids=[str(x) for x in payload.connection_ids],
        rebuild_rag_after_sync=payload.rebuild_rag_after_sync,
    )


@router.post("/background", status_code=status.HTTP_202_ACCEPTED)
async def run_sync_background(payload: SyncRequest, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    tenant_id = str(payload.tenant_id)
    connection_ids = [str(x) for x in payload.connection_ids]
    for connection_id in connection_ids:
        connection = service.db.get_connection(connection_id)
        if str(connection["tenant_id"]) != tenant_id:
            raise HTTPException(status_code=400, detail=f"Connection {connection_id} does not belong to workspace")
    state = TASKS.submit(
        lambda: service.run_pipeline(
            tenant_id=tenant_id,
            connection_ids=connection_ids,
            rebuild_rag_after_sync=payload.rebuild_rag_after_sync,
        ),
        tenant_id=tenant_id,
        user_id=current_user.id,
    )
    return {"task_id": state.id, "status": state.status}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    state = TASKS.get(task_id)
    if not state or not state.tenant_id or not service.db.is_tenant_member(state.tenant_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    return state


@router.get("/jobs")
def list_jobs(tenant_id: UUID, limit: int = 50, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_jobs(tenant_id, min(max(limit, 1), 200))}


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    job = service.db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_tenant_access(service, current_user.id, str(job["tenant_id"]))
    return {
        "job": job,
        "connections": service.db.list_job_connections(job_id),
        "runs": service.db.list_runs(job_id),
        "stages": service.db.list_stage_runs(job_id),
        "events": service.db.list_job_events(job_id),
    }
