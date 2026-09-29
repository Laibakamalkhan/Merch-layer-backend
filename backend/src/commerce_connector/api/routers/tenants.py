from fastapi import APIRouter, Depends, HTTPException

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import TenantCreate

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("")
def list_tenants(current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    return {"items": service.db.list_user_workspaces(current_user.id)}


@router.post("", status_code=201)
def create_tenant(payload: TenantCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    try:
        return service.db.create_workspace_for_user(current_user.id, payload.name, payload.slug, payload.timezone)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
