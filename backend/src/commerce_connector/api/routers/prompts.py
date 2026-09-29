from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.prompt_library import CATEGORIES, PROMPTS

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.get("")
def list_prompts(
    tenant_id: UUID | None = None,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    """Suggested starter prompts for the chat screen.

    Without ``tenant_id`` every general prompt is returned. With ``tenant_id``
    the list is tailored to the workspace (e.g. "compare my stores" only shows
    when 2+ stores are connected) and ``context`` says what is connected, so the
    UI can show a "connect a store first" hint when ``connections`` is 0.
    """
    connections: list[dict] = []
    if tenant_id is not None:
        require_tenant_access(service, current_user.id, str(tenant_id))
        connections = service.db.list_connections(tenant_id)
    count = len(connections) if tenant_id is not None else None

    items = [
        {k: v for k, v in p.items() if k != "min_connections"}
        for p in PROMPTS
        if (category is None or p["category"] == category)
        and (count is None or count >= p["min_connections"])
    ][:limit]
    return {
        "items": items,
        "categories": CATEGORIES,
        "context": None if tenant_id is None else {
            "connections": count,
            "connected_platforms": sorted({str(c.get("platform_code")) for c in connections if c.get("platform_code")}),
        },
    }
