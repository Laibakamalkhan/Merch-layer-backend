from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


@router.get("")
def list_dashboards(tenant_id: UUID, limit: int = 50, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_dashboards(tenant_id, min(max(limit, 1), 200))}


@router.get("/{dashboard_id}")
def get_dashboard(dashboard_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    row = service.db.get_dashboard(dashboard_id)
    if not row:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    require_tenant_access(service, current_user.id, str(row["tenant_id"]))
    return row
