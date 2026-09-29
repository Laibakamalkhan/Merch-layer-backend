from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/usage", tags=["Plans & Usage"])


@router.get("")
def usage(
    tenant_id: UUID,
    days: int = Query(default=30, ge=1, le=366),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    """Short alias of ``GET /subscription/usage``."""
    require_tenant_access(service, current_user.id, str(tenant_id))
    return service.db.usage_summary(tenant_id, days=days)
