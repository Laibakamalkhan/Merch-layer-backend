"""
Frontend-ready paginated table data from Silver layer.

Routes
------
GET /api/v1/tables/sources          – data-source list for filter dropdown
GET /api/v1/tables/{entity}         – paginated, searchable entity rows

All routes are read-only. They require a valid Bearer token and enforce
tenant membership via ``require_tenant_access``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from commerce_connector.api.auth import (
    CurrentUser,
    get_current_user,
    require_tenant_access,
)
from commerce_connector.api.deps import get_service

logger = logging.getLogger("commerce_connector.api")
router = APIRouter(prefix="/tables", tags=["Frontend Tables"])

# ---------------------------------------------------------------------------
# Column / entity config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnDef:
    key: str  # JSON key in items
    label: str  # Display label for the frontend
    sql_expr: str  # SQL expression (must use alias t for entity, c for connection, p for platform)
    col_type: str  # "text" | "status" | "money" | "datetime" | "number"
    sortable: bool = False
    currency_key: str | None = None  # only for money columns


@dataclass(frozen=True)
class EntityConfig:
    table: str  # silver table name (no schema)
    columns: list[ColumnDef]
    search_exprs: list[str]  # SQL exprs using ILIKE %s ESCAPE '\'
    date_expr: str  # for date_from/date_to filter
    default_sort: str  # must be a key in SORT_ALLOWLIST
    extra_select: list[str] = field(
        default_factory=list
    )  # extra SQL fragments (AS key)


# Status normalization expression — reusable fragment.
_NORM_STATUS = (
    "lower(replace(btrim(coalesce(nullif(t.status,''), t.financial_status)), ' ', '_'))"
)
_NORM_FULFILLMENT = "lower(replace(btrim(t.fulfillment_status), ' ', '_'))"
_NORM_PROD_STATUS = "lower(replace(btrim(t.status), ' ', '_'))"

ENTITY_CONFIGS: dict[str, EntityConfig] = {
    "orders": EntityConfig(
        table="orders",
        columns=[
            ColumnDef("order_number", "Order", "t.order_number", "text", sortable=True),
            ColumnDef("source_name", "Store / File", "c.name", "text", sortable=True),
            ColumnDef("source", "Platform", "p.name", "text"),
            ColumnDef("sales_channel", "Channel", "t.sales_channel", "text"),
            ColumnDef("status", "Status", _NORM_STATUS, "status", sortable=True),
            ColumnDef(
                "fulfillment_status",
                "Fulfillment",
                _NORM_FULFILLMENT,
                "status",
                sortable=True,
            ),
            ColumnDef(
                "total_amount",
                "Total",
                "t.total_amount",
                "money",
                sortable=True,
                currency_key="currency_code",
            ),
            ColumnDef(
                "net_amount",
                "Net",
                "t.net_amount",
                "money",
                currency_key="currency_code",
            ),
            ColumnDef(
                "order_date",
                "Order Date",
                "coalesce(t.source_created_at, t.created_at)",
                "datetime",
                sortable=True,
            ),
        ],
        extra_select=[
            "t.id AS id",
            "t.connection_id AS connection_id",
            "t.currency_code AS currency_code",
            "case when p.code = 'file_upload' then 'file' else 'api' end AS source_type",
            "t.source_id AS source_order_id",
            "t.refunded_amount AS refunded_amount",
        ],
        search_exprs=["t.order_number", "t.source_id"],
        date_expr="coalesce(t.source_created_at, t.created_at)",
        default_sort="order_date",
    ),
    "products": EntityConfig(
        table="products",
        columns=[
            ColumnDef("title", "Title", "t.title", "text", sortable=True),
            ColumnDef("vendor", "Vendor", "t.vendor", "text", sortable=True),
            ColumnDef("product_type", "Type", "t.product_type", "text"),
            ColumnDef("status", "Status", _NORM_PROD_STATUS, "status", sortable=True),
            ColumnDef("source_name", "Store / File", "c.name", "text", sortable=True),
            ColumnDef("source", "Platform", "p.name", "text"),
            ColumnDef(
                "product_date",
                "Published",
                "coalesce(t.source_created_at, t.created_at)",
                "datetime",
                sortable=True,
            ),
        ],
        extra_select=[
            "t.id AS id",
            "t.connection_id AS connection_id",
            "case when p.code = 'file_upload' then 'file' else 'api' end AS source_type",
            "t.source_id AS source_product_id",
        ],
        search_exprs=["t.title", "t.vendor", "t.handle"],
        date_expr="coalesce(t.source_created_at, t.created_at)",
        default_sort="product_date",
    ),
    "customers": EntityConfig(
        table="customers",
        columns=[
            ColumnDef(
                "name",
                "Name",
                "coalesce(nullif(btrim(t.display_name),''), nullif(btrim(concat_ws(' ', t.first_name, t.last_name)),''), t.email)",
                "text",
                sortable=True,
            ),
            ColumnDef("email", "Email", "t.email", "text", sortable=True),
            ColumnDef("phone", "Phone", "t.phone", "text"),
            ColumnDef(
                "orders_count", "Orders", "t.orders_count", "number", sortable=True
            ),
            ColumnDef("total_spent", "Spent", "t.total_spent", "number", sortable=True),
            ColumnDef("source_name", "Store / File", "c.name", "text", sortable=True),
            ColumnDef("source", "Platform", "p.name", "text"),
            ColumnDef(
                "customer_since",
                "Since",
                "coalesce(t.source_created_at, t.created_at)",
                "datetime",
                sortable=True,
            ),
        ],
        extra_select=[
            "t.id AS id",
            "t.connection_id AS connection_id",
            "case when p.code = 'file_upload' then 'file' else 'api' end AS source_type",
        ],
        search_exprs=[
            "t.display_name",
            "t.first_name",
            "t.last_name",
            "t.email",
            "t.phone",
        ],
        date_expr="coalesce(t.source_created_at, t.created_at)",
        default_sort="customer_since",
    ),
}

# Allowlists: map sort_by key -> SQL expression (static, never interpolated)
SORT_ALLOWLISTS: dict[str, dict[str, str]] = {}
for _entity, _cfg in ENTITY_CONFIGS.items():
    _allow: dict[str, str] = {}
    for _col in _cfg.columns:
        if _col.sortable:
            _allow[_col.key] = _col.sql_expr
    SORT_ALLOWLISTS[_entity] = _allow

# ---------------------------------------------------------------------------
# SQL builder (pure function for unit-testability)
# ---------------------------------------------------------------------------


def _escape_like(value: str) -> str:
    """Escape %, _ and \\ in a user-supplied search string for ILIKE ESCAPE '\\'.

    Note: the ESCAPE character is backslash. We must escape backslash first,
    then percent, then underscore.
    """
    value = value.replace("\\", "\\\\")
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")
    return "%" + value + "%"


def _from_sql(cfg: EntityConfig) -> str:
    """Static FROM + JOIN part (same for the page query and the count query)."""
    return (
        f"silver.{cfg.table} t\n"
        "  join control.connections c on c.id = t.connection_id and c.tenant_id = t.tenant_id\n"
        "  join control.platforms p on p.id = c.platform_id"
    )


def _build_where(
    entity: str,
    *,
    tenant_id: str,
    connection_id: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    status: str | None = None,
    fulfillment_status: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
) -> tuple[str, list[Any]]:
    """Build the WHERE text + params. Shared by the page query and the count query,
    so both always filter exactly the same rows."""
    cfg = ENTITY_CONFIGS[entity]
    where_parts: list[str] = ["t.tenant_id = %s"]
    params: list[Any] = [tenant_id]

    if connection_id is not None:
        where_parts.append("t.connection_id = %s")
        params.append(connection_id)

    if source_type == "file":
        where_parts.append("p.code = 'file_upload'")
    elif source_type == "api":
        where_parts.append("p.code != 'file_upload'")

    if search:
        clean = search.strip()[:100]
        if clean:
            like_pattern = _escape_like(clean)
            ilike_parts = [f"{expr} ILIKE %s ESCAPE '\\'" for expr in cfg.search_exprs]
            where_parts.append("(" + " OR ".join(ilike_parts) + ")")
            params.extend([like_pattern] * len(cfg.search_exprs))

    if status:
        where_parts.append(
            f"{_NORM_STATUS} = %s"
            if entity == "orders"
            else f"{_NORM_PROD_STATUS} = %s"
        )
        params.append(status.strip().lower())

    if fulfillment_status and entity == "orders":
        where_parts.append(f"{_NORM_FULFILLMENT} = %s")
        params.append(fulfillment_status.strip().lower())

    if entity == "orders":
        if (
            date_from is not None
            and date_to is not None
            and str(date_from) > str(date_to)
        ):
            raise ValueError("date_from must not be after date_to")
        if date_from is not None:
            where_parts.append(f"{cfg.date_expr} >= %s::date")
            params.append(date_from)
        if date_to is not None:
            # Inclusive: everything before the start of the NEXT day
            where_parts.append(f"{cfg.date_expr} < (%s::date + interval '1 day')")
            params.append(date_to)

    return " AND ".join(where_parts), params


def build_table_query(
    entity: str,
    *,
    tenant_id: str,
    connection_id: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    status: str | None = None,
    fulfillment_status: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[str, list[Any]]:
    """Build a paginated Silver query for one entity.

    Returns (sql_text, params). All user input lives only in params,
    never in the SQL text. Pure function: it does not touch the database.
    """
    cfg = ENTITY_CONFIGS[entity]

    col_selects = [f"{col.sql_expr} AS {col.key}" for col in cfg.columns]
    select_parts = col_selects + cfg.extra_select + ["count(*) over() AS _total"]
    select_sql = ",\n       ".join(select_parts)

    where_sql, params = _build_where(
        entity,
        tenant_id=tenant_id,
        connection_id=connection_id,
        source_type=source_type,
        search=search,
        status=status,
        fulfillment_status=fulfillment_status,
        date_from=date_from,
        date_to=date_to,
    )

    # ORDER BY — resolved via allowlist, never interpolated from user input
    sort_allow = SORT_ALLOWLISTS[entity]
    if sort_by and sort_by not in sort_allow:
        raise ValueError(f"Invalid sort_by '{sort_by}'. Allowed: {sorted(sort_allow)}")
    resolved_sort = sort_allow[sort_by or cfg.default_sort]
    safe_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"
    order_sql = f"{resolved_sort} {safe_dir} NULLS LAST, t.id {safe_dir}"

    sql = (
        f"SELECT {select_sql}\n"
        f"FROM   {_from_sql(cfg)}\n"
        f"WHERE  {where_sql}\n"
        f"ORDER BY {order_sql}\n"
        f"LIMIT %s OFFSET %s"
    )
    params.extend([limit, offset])
    return sql, params


def build_count_query(
    entity: str,
    *,
    tenant_id: str,
    connection_id: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    status: str | None = None,
    fulfillment_status: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
) -> tuple[str, list[Any]]:
    """Fallback count query — exact same WHERE as build_table_query, no pagination."""
    cfg = ENTITY_CONFIGS[entity]
    where_sql, params = _build_where(
        entity,
        tenant_id=tenant_id,
        connection_id=connection_id,
        source_type=source_type,
        search=search,
        status=status,
        fulfillment_status=fulfillment_status,
        date_from=date_from,
        date_to=date_to,
    )
    sql = (
        f"SELECT count(*)::bigint AS total\nFROM   {_from_sql(cfg)}\nWHERE  {where_sql}"
    )
    return sql, params


# ---------------------------------------------------------------------------
# Helper: strip internal fields and _total from a row
# ---------------------------------------------------------------------------

_NEVER_RETURN = {"tenant_id", "raw_record_id", "source_hash"}


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _NEVER_RETURN and k != "_total"}


# ---------------------------------------------------------------------------
# Error translation (mirrors database.py pattern)
# ---------------------------------------------------------------------------


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Frontend table query error: %s", exc)
    return HTTPException(status_code=500, detail="Query failed")


# ---------------------------------------------------------------------------
# Route A: GET /tables/sources
# ---------------------------------------------------------------------------

_SOURCES_SQL = """
SELECT
    c.id                AS connection_id,
    c.name              AS name,
    p.code              AS platform_code,
    p.name              AS platform_name,
    c.status::text      AS status,
    c.last_synced_at    AS last_synced_at,
    c.created_at        AS created_at,
    case when p.code = 'file_upload' then 'file' else 'api' end AS source_type,
    ud.id               AS dataset_id,
    ud.filename         AS dataset_filename,
    ud.file_type        AS dataset_file_type,
    ud.status::text     AS dataset_status,
    ud.row_count        AS dataset_row_count,
    ud.created_at       AS dataset_created_at
FROM control.connections c
JOIN control.platforms p ON p.id = c.platform_id
LEFT JOIN LATERAL (
    SELECT d.id, d.filename, d.file_type, d.status, d.row_count, d.created_at
    FROM ingestion.uploaded_datasets d
    WHERE d.connection_id = c.id AND d.tenant_id = c.tenant_id
    ORDER BY d.created_at DESC
    LIMIT 1
) ud ON true
WHERE c.tenant_id = %s
ORDER BY c.created_at DESC
"""

_COUNT_SQL_TMPL = (
    "SELECT connection_id, count(*)::bigint AS cnt "
    "FROM silver.{table} "
    "WHERE tenant_id = %s "
    "GROUP BY connection_id"
)


@router.get("/sources", summary="List data sources for tenant")
def list_sources(
    tenant_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
) -> dict[str, Any]:
    """Return all data sources (connections) for a tenant.

    Each item includes platform metadata, optional dataset info for file
    uploads, and pre-aggregated row counts from the Silver layer.
    """
    require_tenant_access(service, current_user.id, str(tenant_id))
    try:
        rows = service.db.fetch_all(_SOURCES_SQL, (str(tenant_id),))

        # Aggregate counts in one query per entity — no per-row subqueries
        counts_by_conn: dict[str, dict[str, int]] = {}
        for entity in ("orders", "products", "customers"):
            count_sql = _COUNT_SQL_TMPL.format(table=entity)
            for cr in service.db.fetch_all(count_sql, (str(tenant_id),)):
                cid = str(cr["connection_id"])
                counts_by_conn.setdefault(
                    cid, {"orders": 0, "products": 0, "customers": 0}
                )
                counts_by_conn[cid][entity] = int(cr["cnt"])

        items: list[dict[str, Any]] = []
        for row in rows:
            cid = str(row["connection_id"])
            dataset_block = None
            if row.get("dataset_id") is not None:
                dataset_block = {
                    "id": str(row["dataset_id"]),
                    "filename": row["dataset_filename"],
                    "file_type": row["dataset_file_type"],
                    "status": row["dataset_status"],
                    "row_count": row["dataset_row_count"],
                    "created_at": row["dataset_created_at"],
                }
            items.append(
                {
                    "connection_id": cid,
                    "name": row["name"],
                    "platform_code": row["platform_code"],
                    "platform_name": row["platform_name"],
                    "source_type": row["source_type"],
                    "status": row["status"],
                    "last_synced_at": row["last_synced_at"],
                    "dataset": dataset_block,
                    "counts": counts_by_conn.get(
                        cid, {"orders": 0, "products": 0, "customers": 0}
                    ),
                }
            )
        return {"items": items}
    except HTTPException:
        raise
    except Exception as exc:
        raise _translate_error(exc) from exc


# ---------------------------------------------------------------------------
# Route B: GET /tables/{entity}
# ---------------------------------------------------------------------------


@router.get(
    "/{entity}", summary="Paginated entity table (orders / products / customers)"
)
def get_entity_table(
    entity: Literal["orders", "products", "customers"],
    tenant_id: UUID = Query(..., description="Workspace / tenant UUID (required)"),
    connection_id: UUID | None = Query(
        default=None, description="Filter by a specific connection"
    ),
    source_type: Literal["api", "file"] | None = Query(
        default=None, description="Filter by source type"
    ),
    search: str | None = Query(
        default=None, max_length=100, description="Full-text search across key fields"
    ),
    status: str | None = Query(
        default=None, max_length=50, description="Normalized status filter (lowercase)"
    ),
    fulfillment_status: str | None = Query(
        default=None, max_length=50, description="Orders only: fulfillment status"
    ),
    date_from: date | None = Query(
        default=None, description="Orders only: ISO date (YYYY-MM-DD), inclusive"
    ),
    date_to: date | None = Query(
        default=None, description="Orders only: ISO date (YYYY-MM-DD), inclusive"
    ),
    sort_by: str | None = Query(
        default=None, description="Sort key (must be in entity allowlist)"
    ),
    sort_dir: str = Query(
        default="desc", pattern=r"^(asc|desc)$", description="asc or desc"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Page size (1–200)"),
    offset: int = Query(default=0, ge=0, description="Row offset"),
    current_user: CurrentUser = Depends(get_current_user),
    service=Depends(get_service),
) -> dict[str, Any]:
    """Return paginated, frontend-ready rows from a Silver entity table.

    Rows from both API connections (Shopify, WooCommerce, Amazon) and
    file uploads appear together; the ``source_type`` field distinguishes them.
    Use the ``connection_id`` query param to scope to a specific source.
    Status values are normalized to ``lower_snake_case``.
    """
    require_tenant_access(service, current_user.id, str(tenant_id))
    try:
        cfg = ENTITY_CONFIGS[entity]

        # Verify connection_id belongs to this tenant (prevents cross-tenant data leaks)
        conn_id_str: str | None = None
        if connection_id is not None:
            conn_check = service.db.fetch_one(
                "SELECT id FROM control.connections WHERE id = %s AND tenant_id = %s",
                (str(connection_id), str(tenant_id)),
            )
            if not conn_check:
                raise HTTPException(
                    status_code=404, detail="Connection not found for this tenant"
                )
            conn_id_str = str(connection_id)

        sql, params = build_table_query(
            entity,
            tenant_id=str(tenant_id),
            connection_id=conn_id_str,
            source_type=source_type,
            search=search,
            status=status,
            fulfillment_status=fulfillment_status,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

        raw_rows = service.db.fetch_all(sql, params)

        # Extract _total from window function; fall back to explicit count if empty page
        if raw_rows:
            total = int(raw_rows[0]["_total"])
        else:
            if offset > 0:
                count_sql, count_params = build_count_query(
                    entity,
                    tenant_id=str(tenant_id),
                    connection_id=conn_id_str,
                    source_type=source_type,
                    search=search,
                    status=status,
                    fulfillment_status=fulfillment_status,
                    date_from=date_from,
                    date_to=date_to,
                )
                count_row = service.db.fetch_one(count_sql, count_params)
                total = int(count_row["total"]) if count_row else 0
            else:
                total = 0

        items = [_clean_row(dict(row)) for row in raw_rows]

        # Build column definitions for response
        columns: list[dict[str, Any]] = []
        for col in cfg.columns:
            cd: dict[str, Any] = {
                "key": col.key,
                "label": col.label,
                "type": col.col_type,
                "sortable": col.sortable,
            }
            if col.currency_key:
                cd["currency_key"] = col.currency_key
            columns.append(cd)

        return {
            "entity": entity,
            "columns": columns,
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise _translate_error(exc) from exc
