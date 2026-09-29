from uuid import UUID

from fastapi import APIRouter, Depends, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/ops", tags=["Operations"])


@router.get("/errors")
def list_errors(tenant_id: UUID, limit: int = Query(default=100, ge=1, le=500), current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_errors(tenant_id, limit)}


@router.get("/quality-runs")
def list_quality_runs(tenant_id: UUID, limit: int = Query(default=100, ge=1, le=500), current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_quality_runs(tenant_id, limit)}


@router.get("/events")
def list_events(tenant_id: UUID, limit: int = Query(default=200, ge=1, le=1000), current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_tenant_events(tenant_id, limit)}
