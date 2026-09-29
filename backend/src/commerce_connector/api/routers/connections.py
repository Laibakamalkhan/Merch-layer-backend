from urllib.parse import urlparse
from uuid import UUID

import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException, status

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_api_settings, get_service
from commerce_connector.api.schemas import ConnectionCreate, ConnectionResourceUpdate, ConnectionUpdate, CredentialUpsert

def normalize_base_url(platform_code: str, url: str | None) -> str | None:
    """User kabhi 'shop.myshopify.com', kabhi 'https://shop.myshopify.com/admin/' likhta hai.
    Yahan sab ko ek sahi shakal mein la rahe hain."""
    if not url:
        return url
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if platform_code == "shopify":
        return f"{parsed.scheme}://{parsed.netloc}"          # sirf domain, path nahi
    path = parsed.path.rstrip("/")
    if path.endswith("/wp-json"):
        path = path[: -len("/wp-json")]
    return f"{parsed.scheme}://{parsed.netloc}{path}"


router = APIRouter(prefix="/connections", tags=["Connections"])


def _guard_connection(service, current_user: CurrentUser, connection_id: UUID):
    connection = service.db.get_connection(connection_id)
    require_tenant_access(service, current_user.id, str(connection["tenant_id"]))
    return connection


@router.get("")
def list_connections(tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return {"items": service.db.list_connections(tenant_id)}


@router.get("/{connection_id}")
def get_connection(connection_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    try:
        return _guard_connection(service, current_user, connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_connection(payload: ConnectionCreate, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(payload.tenant_id))
    base_url = normalize_base_url(payload.platform_code, payload.base_url)

    # FIX A: agar isi tenant mein isi naam ka connection pehle se hai (jaise pehli koshish fail ho gayi thi),
    # to naya insert karne ki jagah usi ko update karo. Isse "connections_tenant_id_name_key" wala 500 nahi aata,
    # aur free plan ki limit bhi dobara nahi lagti.
    existing = service.db.find_connection_by_name(payload.tenant_id, payload.name)
    if existing:
        if existing["platform_code"] != payload.platform_code:
            raise HTTPException(status_code=409, detail="Is naam ka connection kisi aur platform ke liye pehle se maujood hai. Koi aur naam chunein.")
        service.db.update_connection_basics(existing["id"], payload.name, base_url, payload.config)
        for key, value in payload.secrets.items():
            service.db.store_secret(payload.tenant_id, existing["id"], key, value)
        return service.db.get_connection(existing["id"])

    tenant = service.db.get_tenant(payload.tenant_id) or {}
    plan_code = str((tenant.get("metadata") or {}).get("plan_code") or "free")
    cfg = get_api_settings()
    current_count = service.db.usage_summary(payload.tenant_id, days=30)["connections"]
    if plan_code == "free" and current_count >= cfg.free_store_limit:
        raise HTTPException(status_code=402, detail="Free plan store limit reached")

    try:
        connection = service.db.create_connection(
            tenant_id=payload.tenant_id,
            platform_code=payload.platform_code,
            name=payload.name,
            base_url=base_url,
            config=payload.config,
            metadata=payload.metadata,
            enabled_resources=payload.enabled_resources,
        )
    except psycopg.errors.UniqueViolation as exc:  # do requests ek saath aa jayen to bhi 500 nahi, 409 milega
        raise HTTPException(status_code=409, detail="Yeh connection pehle se maujood hai. Page refresh karke dobara try karein.") from exc
    for key, value in payload.secrets.items():
        service.db.store_secret(payload.tenant_id, connection["id"], key, value)
    return connection


@router.patch("/{connection_id}")
def update_connection(
    connection_id: UUID,
    payload: ConnectionUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    """Test fail hone ke baad user URL/token theek karke dobara try kare -> naya connection banane ki zaroorat nahi
    (warna free plan ki 1-store limit ki wajah se 402 aata)."""
    connection = _guard_connection(service, current_user, connection_id)
    service.db.update_connection_basics(
        connection_id, payload.name, normalize_base_url(connection["platform_code"], payload.base_url), payload.config
    )
    for key, value in payload.secrets.items():
        service.db.store_secret(connection["tenant_id"], connection_id, key, value)
    return service.db.get_connection(connection_id)


@router.get("/{connection_id}/resources")
def connection_resources(connection_id: UUID, enabled_only: bool = False, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    _guard_connection(service, current_user, connection_id)
    return {"items": service.db.get_connection_resources(connection_id, enabled_only=enabled_only)}


@router.patch("/{connection_id}/resources/{resource_key}")
def update_connection_resource(
    connection_id: UUID,
    resource_key: str,
    payload: ConnectionResourceUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    _guard_connection(service, current_user, connection_id)
    changed = service.db.update_connection_resource(
        connection_id=connection_id,
        resource_key=resource_key,
        enabled=payload.enabled,
        sync_mode=payload.sync_mode,
    )
    if not changed:
        raise HTTPException(status_code=404, detail="Connection resource not found")
    return {"updated": True}


@router.post("/{connection_id}/test")
async def test_connection(connection_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    try:
        _guard_connection(service, current_user, connection_id)
        return await service.test_connection(str(connection_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{connection_id}/credentials")
def upsert_credentials(
    connection_id: UUID,
    payload: CredentialUpsert,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    connection = _guard_connection(service, current_user, connection_id)
    if str(connection["tenant_id"]) != str(payload.tenant_id):
        raise HTTPException(status_code=400, detail="Connection does not belong to tenant")
    stored = []
    for key, value in payload.secrets.items():
        service.db.store_secret(payload.tenant_id, connection_id, key, value)
        stored.append(key)
    return {"stored_secret_keys": stored}