from __future__ import annotations

import logging

import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import TenantCreate

logger = logging.getLogger("commerce_connector.api")
router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("")
def list_tenants(current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    return {"items": service.db.list_user_workspaces(current_user.id)}


@router.post("", status_code=201)
def create_tenant(payload: TenantCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    try:
        return service.db.create_workspace_for_user(current_user.id, payload.name, payload.slug, payload.timezone)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Workspace slug already taken")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not create workspace for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Could not create workspace") from exc
