from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_api_settings, get_service
from commerce_connector.api.schemas import PlanChangeRequest, UpgradeIntentRequest

router = APIRouter(prefix="/subscription", tags=["Plans & Usage"])


def _plans():
    cfg = get_api_settings()
    return [
        {
            "code": "free",
            "name": "Free",
            "store_limit": cfg.free_store_limit,
            "ai_query_limit_monthly": cfg.free_ai_query_limit_monthly,
            "can_connect_all_stores": False,
        },
        {
            "code": "pro",
            "name": "Pro",
            "store_limit": None,
            "ai_query_limit_monthly": None,
            "can_connect_all_stores": True,
        },
    ]


@router.get("/plans")
def plans():
    return {"items": _plans()}


@router.get("")
def subscription(tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    tenant = service.db.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    plan_code = str((tenant.get("metadata") or {}).get("plan_code") or "free")
    plan = next((p for p in _plans() if p["code"] == plan_code), _plans()[0])
    usage = service.db.usage_summary(tenant_id, days=30)
    return {"tenant_id": str(tenant_id), "plan": plan, "usage": usage}


@router.get("/usage")
def usage(tenant_id: UUID, days: int = 30, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return service.db.usage_summary(tenant_id, days=days)


@router.post("/upgrade-intent")
def upgrade_intent(payload: UpgradeIntentRequest, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    plan = next((p for p in _plans() if p["code"] == payload.plan_code), None)
    if not plan or payload.plan_code == "free":
        raise HTTPException(status_code=400, detail="Choose an upgrade plan")
    cfg = get_api_settings()
    if not cfg.billing_checkout_url:
        return {
            "configured": False,
            "plan": plan,
            "message": "Billing provider is not configured yet. Set BILLING_CHECKOUT_URL when checkout is ready.",
        }
    url = cfg.billing_checkout_url.replace("{tenant_id}", str(payload.tenant_id)).replace("{plan_code}", payload.plan_code)
    if payload.return_url:
        url = url.replace("{return_url}", payload.return_url)
    return {"configured": True, "plan": plan, "checkout_url": url}


@router.post("/change-plan")
def change_plan(payload: PlanChangeRequest, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    cfg = get_api_settings()
    if not cfg.allow_direct_plan_change:
        raise HTTPException(status_code=409, detail="Direct plan changes are disabled. Connect a billing provider before enabling this endpoint.")
    allowed = {p["code"] for p in _plans()}
    if payload.plan_code not in allowed:
        raise HTTPException(status_code=400, detail="Unknown plan")
    service.db.set_tenant_plan(payload.tenant_id, payload.plan_code)
    return {"updated": True, "plan_code": payload.plan_code}
