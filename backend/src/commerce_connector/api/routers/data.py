from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/data", tags=["Data Explorer"])


@router.get("/catalog")
def data_catalog(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "bronze": ["raw_objects", "records", "schema_snapshots"],
        "silver": [
            "customers", "customer_addresses", "products", "product_variants", "categories",
            "product_categories", "locations", "inventory_levels", "orders", "order_items",
            "order_addresses", "payments", "refunds", "refund_items", "fulfillments",
            "fulfillment_items", "returns", "return_items",
        ],
        "gold": [
            "daily_sales", "product_daily", "customer_metrics", "inventory_snapshot_daily",
            "refund_daily", "fulfillment_daily", "channel_daily",
        ],
    }


@router.get("/overview/{tenant_id}")
def overview(tenant_id: UUID, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    require_tenant_access(service, current_user.id, str(tenant_id))
    return service.db.tenant_overview(tenant_id)


@router.get("/{layer}/{table}")
def read_layer_table(
    layer: str,
    table: str,
    tenant_id: UUID,
    connection_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
):
    require_tenant_access(service, current_user.id, str(tenant_id))
    try:
        rows = service.db.read_data_table(
            layer=layer,
            table=table,
            tenant_id=tenant_id,
            connection_id=connection_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": rows, "limit": limit, "offset": offset}
