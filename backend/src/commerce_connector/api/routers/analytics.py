from uuid import UUID

from fastapi import APIRouter, Depends, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/sales-summary")
def sales_summary(tenant_id: UUID, days: int = Query(default=30, ge=1, le=730), current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return service.db.sales_summary(tenant_id, days)


@router.get("/channel-performance")
def channel_performance(tenant_id: UUID, days: int = Query(default=30, ge=1, le=730), current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.channel_performance(tenant_id, days)}
