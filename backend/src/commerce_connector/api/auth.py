from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from commerce_connector.api.deps import get_api_settings


@dataclass(slots=True)
class CurrentUser:
    id: str
    email: str | None
    raw: dict[str, Any]


class SupabaseAuthClient:
    def __init__(self, supabase_url: str, anon_key: str, service_role_key: str = ""):
        self.base = supabase_url.rstrip("/")
        self.anon_key = anon_key.strip()
        self.service_role_key = service_role_key.strip()
        if not self.base:
            raise ValueError("SUPABASE_URL is required")
        if not self.anon_key and not self.service_role_key:
            raise ValueError("SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY is required")

    @property
    def api_key(self) -> str:
        return self.anon_key or self.service_role_key

    def _headers(self, *, bearer: str | None = None) -> dict[str, str]:
        headers = {"apikey": self.api_key, "Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    def signup(
        self,
        email: str,
        password: str,
        metadata: dict[str, Any] | None = None,
        redirect_to: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"email": email, "password": password}
        if metadata:
            payload["data"] = metadata
        response = httpx.post(
            f"{self.base}/auth/v1/signup",
            headers=self._headers(),
            params={"redirect_to": redirect_to} if redirect_to else None,
            json=payload,
            timeout=30,
        )
        if response.status_code >= 300:
            raise HTTPException(status_code=response.status_code, detail=self._auth_error(response))
        return response.json()

    def resend_confirmation(self, email: str, redirect_to: str | None = None) -> None:
        response = httpx.post(
            f"{self.base}/auth/v1/resend",
            headers=self._headers(),
            params={"redirect_to": redirect_to} if redirect_to else None,
            json={"type": "signup", "email": email},
            timeout=30,
        )
        if response.status_code >= 300:
            raise HTTPException(status_code=response.status_code, detail=self._auth_error(response))

    def login(self, email: str, password: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base}/auth/v1/token?grant_type=password",
            headers=self._headers(),
            json={"email": email, "password": password},
            timeout=30,
        )
        if response.status_code >= 300:
            raise HTTPException(status_code=response.status_code, detail=self._auth_error(response))
        return response.json()

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base}/auth/v1/token?grant_type=refresh_token",
            headers=self._headers(),
            json={"refresh_token": refresh_token},
            timeout=30,
        )
        if response.status_code >= 300:
            raise HTTPException(status_code=response.status_code, detail=self._auth_error(response))
        return response.json()

    def logout(self, access_token: str) -> None:
        response = httpx.post(
            f"{self.base}/auth/v1/logout",
            headers=self._headers(bearer=access_token),
            timeout=30,
        )
        if response.status_code not in (200, 204):
            raise HTTPException(status_code=response.status_code, detail=self._auth_error(response))

    def user(self, access_token: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base}/auth/v1/user",
            headers=self._headers(bearer=access_token),
            timeout=30,
        )
        if response.status_code >= 300:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
        return response.json()

    @staticmethod
    def _auth_error(response: httpx.Response) -> str:
        try:
            data = response.json()
            return str(data.get("msg") or data.get("message") or data.get("error_description") or data.get("error") or response.text)
        except Exception:
            return response.text[:500]


def get_auth_client() -> SupabaseAuthClient:
    settings = get_api_settings()
    try:
        return SupabaseAuthClient(
            settings.supabase_url,
            settings.supabase_anon_key,
            settings.supabase_service_role_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


bearer_scheme = HTTPBearer(auto_error=False)


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required",
        )
    return credentials.credentials.strip()


def get_current_user(token: str = Depends(get_access_token)) -> CurrentUser:
    raw = get_auth_client().user(token)
    user_id = raw.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to resolve authenticated user",
        )
    return CurrentUser(id=str(user_id), email=raw.get("email"), raw=raw)


def require_tenant_access(service: Any, user_id: str, tenant_id: str) -> None:
    if not service.db.is_tenant_member(tenant_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this workspace")