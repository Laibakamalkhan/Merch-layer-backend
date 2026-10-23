from __future__ import annotations

import logging
from typing import Any, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from commerce_connector.api.auth import CurrentUser, get_current_user, require_tenant_access
from commerce_connector.api.deps import get_service
from commerce_connector.api.schemas import TableQueryRequest
from commerce_connector.api.table_registry import TABLE_SPECS, TableSpec, get_table_spec, grouped_table_specs

logger = logging.getLogger("commerce_connector.api")
router = APIRouter(prefix="/database", tags=["Database Tables"])


def _common_filters(
    *,
    connection_id: UUID | None = None,
    job_id: UUID | None = None,
    run_id: UUID | None = None,
    resource_key: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "connection_id": connection_id,
            "job_id": job_id,
            "run_id": run_id,
            "resource_key": resource_key,
            "status": status,
        }.items()
        if value is not None
    }


def _parent_scope_kwargs(spec: TableSpec, current_user_id: str) -> dict[str, Any]:
    """Return gateway kwargs for parent-table ownership, or empty dict."""
    if spec.parent_schema and spec.parent_table and spec.parent_fk:
        return {
            "owner_user_id": current_user_id,
            "parent_schema": spec.parent_schema,
            "parent_table": spec.parent_table,
            "parent_fk": spec.parent_fk,
            "parent_user_column": spec.parent_user_column,
        }
    return {}


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Database query error: %s", exc)
    return HTTPException(status_code=500, detail="Query failed")


@router.get("/catalog")
def database_catalog(current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    grouped: dict[str, list[dict[str, Any]]] = {}
    for schema, specs in grouped_table_specs().items():
        grouped[schema] = []
        for spec in specs:
            columns = service.db.table_columns(spec.schema, spec.table)
            visible = [c for c in columns if c not in spec.hidden_columns]
            grouped[schema].append(
                {
                    "table": spec.table,
                    "key": spec.key,
                    "scope": spec.scope,
                    "write_mode": spec.write_mode,
                    "has_id": spec.has_id,
                    "columns": visible,
                    "hidden_columns": list(spec.hidden_columns),
                    "large_columns": list(spec.large_columns),
                    "list_endpoint": f"/api/v1/database/{spec.schema}/{spec.table}",
                    "count_endpoint": f"/api/v1/database/{spec.schema}/{spec.table}/_count",
                    "detail_endpoint": f"/api/v1/database/{spec.schema}/{spec.table}/{{record_id}}" if spec.has_id else None,
                }
            )
    return {"table_count": len(TABLE_SPECS), "schemas": grouped}


@router.post("/query/{schema}/{table}")
def query_table(schema: str, table: str, payload: TableQueryRequest, current_user: CurrentUser = Depends(get_current_user), service=Depends(get_service)):
    try:
        spec = get_table_spec(schema, table)
        tenant_id = payload.tenant_id
        user_id = payload.user_id
        if spec.scope in {"tenant", "tenant_or_global"}:
            if tenant_id is None:
                raise ValueError("tenant_id is required for this table")
            require_tenant_access(service, current_user.id, str(tenant_id))
        if spec.scope == "user":
            user_id = UUID(current_user.id)
        if spec.parent_schema:
            user_id = None
        items = service.db.read_frontend_table(
            schema=spec.schema,
            table=spec.table,
            scope=spec.scope,
            tenant_column=spec.tenant_column,
            tenant_id=tenant_id,
            user_id=user_id,
            filters=payload.filters,
            hidden_columns=spec.hidden_columns,
            large_columns=spec.large_columns,
            include_large_fields=payload.include_large_fields,
            limit=payload.limit,
            offset=payload.offset,
            order_by=payload.order_by,
            order_dir=payload.order_dir,
            **_parent_scope_kwargs(spec, current_user.id),
        )
        return {"table": spec.key, "items": items, "limit": payload.limit, "offset": payload.offset}
    except Exception as exc:
        raise _translate_error(exc) from exc


def _make_list_endpoint(spec: TableSpec) -> Callable[..., dict[str, Any]]:
    def endpoint(
        tenant_id: UUID | None = Query(default=None),
        user_id: UUID | None = Query(default=None),
        connection_id: UUID | None = Query(default=None),
        job_id: UUID | None = Query(default=None),
        run_id: UUID | None = Query(default=None),
        resource_key: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        order_by: str | None = Query(default=None),
        order_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
        include_large_fields: bool = Query(default=False),
        current_user: CurrentUser = Depends(get_current_user),
        service=Depends(get_service),
    ):
        try:
            if spec.scope in {"tenant", "tenant_or_global"}:
                if tenant_id is None:
                    raise ValueError("tenant_id is required for this table")
                require_tenant_access(service, current_user.id, str(tenant_id))
            if spec.scope == "user":
                user_id = UUID(current_user.id)
            if spec.parent_schema:
                user_id = None
            filters = _common_filters(
                connection_id=connection_id,
                job_id=job_id,
                run_id=run_id,
                resource_key=resource_key,
                status=status,
            )
            columns = set(service.db.table_columns(spec.schema, spec.table))
            filters = {k: v for k, v in filters.items() if k in columns}
            items = service.db.read_frontend_table(
                schema=spec.schema,
                table=spec.table,
                scope=spec.scope,
                tenant_column=spec.tenant_column,
                tenant_id=tenant_id,
                user_id=user_id,
                filters=filters,
                hidden_columns=spec.hidden_columns,
                large_columns=spec.large_columns,
                include_large_fields=include_large_fields,
                limit=limit,
                offset=offset,
                order_by=order_by,
                order_dir=order_dir,
                **_parent_scope_kwargs(spec, current_user.id),
            )
            return {"table": spec.key, "items": items, "limit": limit, "offset": offset}
        except Exception as exc:
            raise _translate_error(exc) from exc

    endpoint.__name__ = f"list_{spec.schema}_{spec.table}"
    endpoint.__doc__ = f"List rows from `{spec.key}` with enforced {spec.scope} scope."
    return endpoint


def _make_count_endpoint(spec: TableSpec) -> Callable[..., dict[str, Any]]:
    def endpoint(
        tenant_id: UUID | None = Query(default=None),
        user_id: UUID | None = Query(default=None),
        connection_id: UUID | None = Query(default=None),
        job_id: UUID | None = Query(default=None),
        run_id: UUID | None = Query(default=None),
        resource_key: str | None = Query(default=None),
        status: str | None = Query(default=None),
        current_user: CurrentUser = Depends(get_current_user),
        service=Depends(get_service),
    ):
        try:
            if spec.scope in {"tenant", "tenant_or_global"}:
                if tenant_id is None:
                    raise ValueError("tenant_id is required for this table")
                require_tenant_access(service, current_user.id, str(tenant_id))
            if spec.scope == "user":
                user_id = UUID(current_user.id)
            if spec.parent_schema:
                user_id = None
            filters = _common_filters(
                connection_id=connection_id,
                job_id=job_id,
                run_id=run_id,
                resource_key=resource_key,
                status=status,
            )
            columns = set(service.db.table_columns(spec.schema, spec.table))
            filters = {k: v for k, v in filters.items() if k in columns}
            total = service.db.count_frontend_table(
                schema=spec.schema,
                table=spec.table,
                scope=spec.scope,
                tenant_column=spec.tenant_column,
                tenant_id=tenant_id,
                user_id=user_id,
                filters=filters,
                hidden_columns=spec.hidden_columns,
                **_parent_scope_kwargs(spec, current_user.id),
            )
            return {"table": spec.key, "total": total}
        except Exception as exc:
            raise _translate_error(exc) from exc

    endpoint.__name__ = f"count_{spec.schema}_{spec.table}"
    endpoint.__doc__ = f"Count rows in `{spec.key}` within the enforced scope."
    return endpoint


def _make_detail_endpoint(spec: TableSpec) -> Callable[..., dict[str, Any]]:
    def endpoint(
        record_id: str,
        tenant_id: UUID | None = Query(default=None),
        user_id: UUID | None = Query(default=None),
        include_large_fields: bool = Query(default=True),
        current_user: CurrentUser = Depends(get_current_user),
        service=Depends(get_service),
    ):
        try:
            if spec.scope in {"tenant", "tenant_or_global"}:
                if tenant_id is None:
                    raise ValueError("tenant_id is required for this table")
                require_tenant_access(service, current_user.id, str(tenant_id))
            if spec.scope == "user":
                user_id = UUID(current_user.id)
            if spec.parent_schema:
                user_id = None
            row = service.db.get_frontend_record(
                schema=spec.schema,
                table=spec.table,
                record_id=record_id,
                scope=spec.scope,
                tenant_column=spec.tenant_column,
                tenant_id=tenant_id,
                user_id=user_id,
                hidden_columns=spec.hidden_columns,
                large_columns=spec.large_columns,
                include_large_fields=include_large_fields,
                **_parent_scope_kwargs(spec, current_user.id),
            )
            if not row:
                raise HTTPException(status_code=404, detail=f"Record not found in {spec.key}")
            return row
        except HTTPException:
            raise
        except Exception as exc:
            raise _translate_error(exc) from exc

    endpoint.__name__ = f"get_{spec.schema}_{spec.table}"
    endpoint.__doc__ = f"Get one row from `{spec.key}` by its `id`."
    return endpoint


# Register a concrete OpenAPI route for every finalized Supabase application
# table.  This keeps the frontend contract explicit while the implementation
# stays centralized and safe.
for _spec in TABLE_SPECS:
    _base = f"/{_spec.schema}/{_spec.table}"
    router.add_api_route(
        _base,
        _make_list_endpoint(_spec),
        methods=["GET"],
        name=f"list_{_spec.schema}_{_spec.table}",
        summary=f"List {_spec.key}",
    )
    router.add_api_route(
        f"{_base}/_count",
        _make_count_endpoint(_spec),
        methods=["GET"],
        name=f"count_{_spec.schema}_{_spec.table}",
        summary=f"Count {_spec.key}",
    )
    if _spec.has_id:
        router.add_api_route(
            f"{_base}/{{record_id}}",
            _make_detail_endpoint(_spec),
            methods=["GET"],
            name=f"get_{_spec.schema}_{_spec.table}",
            summary=f"Get {_spec.key} record",
        )
