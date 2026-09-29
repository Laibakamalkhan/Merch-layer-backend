from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/library", tags=["Library"])


@router.get("")
def library(
    tenant_id: UUID,
    q: str | None = None,
    item_type: Literal["task", "file", "dashboard"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.library_items(tenant_id, current_user.id, q=q, item_type=item_type, limit=limit)}
