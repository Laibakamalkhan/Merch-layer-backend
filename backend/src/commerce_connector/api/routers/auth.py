from __future__ import annotations

from fastapi import APIRouter, Depends

from commerce_connector.api.auth import get_access_token, get_auth_client, get_current_user, CurrentUser
from commerce_connector.api.deps import get_service
from commerce_connector.api.deps import get_api_settings
from commerce_connector.api.schemas import AuthLoginRequest, AuthRefreshRequest, AuthResendRequest, AuthSignupRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup")
def signup(payload: AuthSignupRequest):
    metadata = {"full_name": payload.display_name} if payload.display_name else None
    return get_auth_client().signup(
        payload.email, payload.password, metadata, redirect_to=get_api_settings().frontend_url
    )


@router.post("/resend-confirmation")
def resend_confirmation(payload: AuthResendRequest):
    get_auth_client().resend_confirmation(payload.email, redirect_to=get_api_settings().frontend_url)
    return {"ok": True}


@router.post("/login")
def login(payload: AuthLoginRequest):
    return get_auth_client().login(payload.email, payload.password)


@router.post("/refresh")
def refresh(payload: AuthRefreshRequest):
    return get_auth_client().refresh(payload.refresh_token)


@router.post("/logout")
def logout(access_token: str = Depends(get_access_token)):
    get_auth_client().logout(access_token)
    return {"ok": True}


@router.get("/session")
def session(current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "profile": service.db.get_profile(current_user.id),
        },
        "workspaces": service.db.list_user_workspaces(current_user.id),
    }
