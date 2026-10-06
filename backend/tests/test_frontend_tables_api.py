"""Tests for the read-only frontend tables API (/api/v1/tables/...).

No real database and no network are used. A small FakeDB records every SQL
statement it receives so tests can also check *how* the router queried.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user
from commerce_connector.api.routers import tables
from commerce_connector.api.routers.tables import (
    _escape_like,
    build_count_query,
    build_table_query,
)

TENANT_ID = str(uuid.uuid4())
OTHER_TENANT_ID = str(uuid.uuid4())
USER_ID = "user-frontend-tables-test"
CONN_API = str(uuid.uuid4())
CONN_FILE = str(uuid.uuid4())
CONN_OTHER_TENANT = str(uuid.uuid4())

# Keys that must NEVER reach the frontend.
INTERNAL_KEYS = ("tenant_id", "raw_record_id", "source_hash")


# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


@dataclass
class FakeSettings:
    max_user_file_bytes: int = 25 * 1024 * 1024
    user_files_bucket: str = "test-bucket"


def _order(n: int, conn: str = CONN_API) -> dict[str, Any]:
    """One fake order row. It deliberately contains internal keys so the
    tests can prove the router strips them."""
    return {
        "order_number": f"#{1000 + n}",
        "source_name": "My Store",
        "source": "Shopify",
        "sales_channel": "online",
        "status": "paid",
        "fulfillment_status": "fulfilled",
        "total_amount": 100.0 + n,
        "net_amount": 100.0 + n,
        "order_date": f"2026-09-{n:02d}",
        "id": f"order-{n}",
        "connection_id": conn,
        "currency_code": "USD",
        "source_type": "api",
        "source_order_id": f"gid://shopify/Order/{n}",
        "refunded_amount": 0.0,
        # internal – must be stripped:
        "tenant_id": TENANT_ID,
        "raw_record_id": "raw-1",
        "source_hash": "abc123",
    }


class FakeDB:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fail_with: Exception | None = None
        self.total_override: int | None = None  # lets a test force the window total
        self.entity_rows: dict[str, list[dict[str, Any]]] = {
            "orders": [_order(1), _order(2)],
            "products": [
                {
                    "title": "Blue Shirt",
                    "vendor": "Acme",
                    "product_type": "Shirts",
                    "status": "active",
                    "source_name": "My Store",
                    "source": "Shopify",
                    "product_date": "2026-08-01",
                    "id": "prod-1",
                    "connection_id": CONN_API,
                    "source_type": "api",
                    "source_product_id": "p-1",
                    "tenant_id": TENANT_ID,
                }
            ],
            "customers": [
                {
                    "name": "Ayesha Khan",
                    "email": "ayesha@example.com",
                    "phone": None,
                    "orders_count": 3,
                    "total_spent": 450.5,
                    "source_name": "customers.csv",
                    "source": "File Upload",
                    "customer_since": "2026-07-01",
                    "id": "cust-1",
                    "connection_id": CONN_FILE,
                    "source_type": "file",
                    "tenant_id": TENANT_ID,
                }
            ],
        }
        self.sources_rows: list[dict[str, Any]] = [
            {
                "connection_id": CONN_FILE,
                "name": "orders.csv",
                "platform_code": "file_upload",
                "platform_name": "File Upload",
                "status": "active",
                "last_synced_at": None,
                "created_at": "2026-09-02T00:00:00Z",
                "source_type": "file",
                "dataset_id": "ds-1",
                "dataset_filename": "orders.csv",
                "dataset_file_type": "csv",
                "dataset_status": "completed",
                "dataset_row_count": 12,
                "dataset_created_at": "2026-09-02T00:00:00Z",
            },
            {
                "connection_id": CONN_API,
                "name": "My Store",
                "platform_code": "shopify",
                "platform_name": "Shopify",
                "status": "active",
                "last_synced_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "source_type": "api",
                "dataset_id": None,
                "dataset_filename": None,
                "dataset_file_type": None,
                "dataset_status": None,
                "dataset_row_count": None,
                "dataset_created_at": None,
            },
        ]
        self.source_counts: dict[str, list[dict[str, Any]]] = {
            "orders": [
                {"connection_id": CONN_API, "cnt": 5},
                {"connection_id": CONN_FILE, "cnt": 12},
            ],
            "products": [{"connection_id": CONN_API, "cnt": 3}],
            "customers": [],
        }

    # -- auth helper used by require_tenant_access ---------------------------
    def is_tenant_member(self, tenant_id: str, user_id: str) -> bool:
        return str(tenant_id) == TENANT_ID

    # -- query helpers --------------------------------------------------------
    def fetch_one(self, sql: str, params: Any = None):
        self.calls.append((sql, tuple(params or ())))
        if self.fail_with:
            raise self.fail_with
        if "FROM control.connections WHERE id" in sql:
            conn_id, tenant = params
            if conn_id == CONN_API and tenant == TENANT_ID:
                return {"id": conn_id}
            return None
        if sql.lstrip().startswith("SELECT count(*)::bigint AS total"):
            # fallback count query used for empty pages
            entity = self._entity_in(sql)
            return {"total": len(self.entity_rows[entity])}
        return None

    def fetch_all(self, sql: str, params: Any = None):
        params = tuple(params or ())
        self.calls.append((sql, params))
        if self.fail_with:
            raise self.fail_with

        stripped = sql.lstrip()
        # 1) sources list
        if stripped.startswith("SELECT\n    c.id") or "uploaded_datasets" in sql:
            return list(self.sources_rows)
        # 2) per-entity grouped counts used by /sources
        if stripped.startswith("SELECT connection_id, count(*)"):
            entity = self._entity_in(sql)
            return list(self.source_counts[entity])
        # 3) entity page query
        if "count(*) over() AS _total" in sql:
            entity = self._entity_in(sql)
            limit, offset = int(params[-2]), int(params[-1])
            full = self.entity_rows[entity]
            page = full[offset : offset + limit]
            total = (
                self.total_override if self.total_override is not None else len(full)
            )
            return [{**row, "_total": total} for row in page]
        return []

    @staticmethod
    def _entity_in(sql: str) -> str:
        for entity in ("orders", "products", "customers"):
            if f"silver.{entity}" in sql:
                return entity
        raise AssertionError(f"No silver entity found in SQL: {sql[:80]}")

    # -- convenience for assertions -------------------------------------------
    def entity_calls(self) -> list[tuple[str, tuple[Any, ...]]]:
        return [c for c in self.calls if "count(*) over() AS _total" in c[0]]

    def count_fallback_calls(self) -> list[tuple[str, tuple[Any, ...]]]:
        return [
            c
            for c in self.calls
            if c[0].lstrip().startswith("SELECT count(*)::bigint AS total")
        ]


class FakeService:
    def __init__(self) -> None:
        self.settings = FakeSettings()
        self.db = FakeDB()
        self.user_files = None
        self.indexer = None
        self.datasets_engine = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_and_service():
    """Logged-in client (auth bypassed with a fake user)."""
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID, email="user@example.com", raw={}
    )
    client = TestClient(app, raise_server_exceptions=False)
    yield client, service
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client():
    """Client with NO auth override: a request without token must give 401."""
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1) Authentication / authorization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["sources", "orders", "products", "customers"])
def test_no_token_returns_401(anon_client, path):
    resp = anon_client.get(f"/api/v1/tables/{path}", params={"tenant_id": TENANT_ID})
    assert resp.status_code == 401


@pytest.mark.parametrize("path", ["sources", "orders", "products", "customers"])
def test_user_without_tenant_access_returns_403(client_and_service, path):
    client, service = client_and_service
    resp = client.get(f"/api/v1/tables/{path}", params={"tenant_id": OTHER_TENANT_ID})
    assert resp.status_code == 403
    # access is checked BEFORE any DB query runs
    assert service.db.calls == []


def test_tenant_id_is_required(client_and_service):
    client, _ = client_and_service
    assert client.get("/api/v1/tables/orders").status_code == 422
    assert client.get("/api/v1/tables/sources").status_code == 422


# ---------------------------------------------------------------------------
# 2) Orders happy path + pagination
# ---------------------------------------------------------------------------


def test_orders_happy_path(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={
            "tenant_id": TENANT_ID,
            "limit": 1,
            "offset": 0,
            "sort_by": "order_date",
            "sort_dir": "desc",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity"] == "orders"
    assert data["total"] == 2
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert data["has_more"] is True
    assert len(data["items"]) == 1

    col_keys = [c["key"] for c in data["columns"]]
    assert col_keys == [
        "order_number",
        "source_name",
        "source",
        "sales_channel",
        "status",
        "fulfillment_status",
        "total_amount",
        "net_amount",
        "order_date",
    ]

    item = data["items"][0]
    for key in INTERNAL_KEYS:
        assert key not in item
    assert "_total" not in item
    # useful extra keys are kept
    for key in (
        "id",
        "connection_id",
        "currency_code",
        "source_type",
        "source_order_id",
    ):
        assert key in item


def test_money_columns_have_currency_key(client_and_service):
    client, _ = client_and_service
    data = client.get("/api/v1/tables/orders", params={"tenant_id": TENANT_ID}).json()
    cols = {c["key"]: c for c in data["columns"]}
    assert cols["total_amount"]["type"] == "money"
    assert cols["total_amount"]["currency_key"] == "currency_code"
    assert cols["net_amount"]["currency_key"] == "currency_code"
    assert cols["order_number"]["sortable"] is True
    assert cols["status"]["type"] == "status"


def test_has_more_false_on_last_page(client_and_service):
    client, _ = client_and_service
    data = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "limit": 50, "offset": 1},
    ).json()
    assert len(data["items"]) == 1
    assert data["total"] == 2
    assert data["has_more"] is False


def test_has_more_is_based_on_offset_plus_returned_rows(client_and_service):
    """Spec: has_more = offset + returned_rows < total (NOT offset + limit)."""
    client, service = client_and_service
    service.db.total_override = 5  # DB says 5 rows exist, page returned only 2
    data = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "limit": 50, "offset": 0},
    ).json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["has_more"] is True  # 0 + 2 < 5


def test_empty_page_uses_fallback_count(client_and_service):
    """offset beyond the data: page is empty, but total must still be correct."""
    client, service = client_and_service
    data = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "limit": 10, "offset": 100},
    ).json()
    assert data["items"] == []
    assert data["total"] == 2
    assert data["has_more"] is False
    fallback = service.db.count_fallback_calls()
    assert len(fallback) == 1
    # fallback count uses the same WHERE params (tenant first), no limit/offset
    assert fallback[0][1][0] == TENANT_ID
    assert 100 not in fallback[0][1]


def test_empty_first_page_has_no_fallback_query(client_and_service):
    client, service = client_and_service
    service.db.entity_rows["orders"] = []
    data = client.get("/api/v1/tables/orders", params={"tenant_id": TENANT_ID}).json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["has_more"] is False
    assert service.db.count_fallback_calls() == []


# ---------------------------------------------------------------------------
# 3) Products and customers
# ---------------------------------------------------------------------------


def test_products_columns_and_items(client_and_service):
    client, _ = client_and_service
    data = client.get("/api/v1/tables/products", params={"tenant_id": TENANT_ID}).json()
    assert [c["key"] for c in data["columns"]] == [
        "title",
        "vendor",
        "product_type",
        "status",
        "source_name",
        "source",
        "product_date",
    ]
    assert data["total"] == 1
    assert all(k not in data["items"][0] for k in INTERNAL_KEYS)


def test_customers_columns_and_total_spent_is_not_money(client_and_service):
    client, _ = client_and_service
    data = client.get(
        "/api/v1/tables/customers", params={"tenant_id": TENANT_ID}
    ).json()
    assert [c["key"] for c in data["columns"]] == [
        "name",
        "email",
        "phone",
        "orders_count",
        "total_spent",
        "source_name",
        "source",
        "customer_since",
    ]
    cols = {c["key"]: c for c in data["columns"]}
    assert cols["total_spent"]["type"] == "number"
    assert "currency_key" not in cols["total_spent"]
    assert all(k not in data["items"][0] for k in INTERNAL_KEYS)


# ---------------------------------------------------------------------------
# 4) Validation
# ---------------------------------------------------------------------------


def test_unknown_entity_rejected(client_and_service):
    client, _ = client_and_service
    resp = client.get("/api/v1/tables/widgets", params={"tenant_id": TENANT_ID})
    assert resp.status_code in (404, 422)


def test_invalid_sort_key_400(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "sort_by": "nonexistent"},
    )
    assert resp.status_code == 400


def test_malicious_sort_key_400_and_never_reaches_db(client_and_service):
    client, service = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "sort_by": "total_amount; drop table x"},
    )
    assert resp.status_code == 400
    assert service.db.entity_calls() == []
    for sql, _params in service.db.calls:
        assert "drop table" not in sql.lower()


def test_invalid_sort_dir_422(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "sort_dir": "sideways"},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("limit", [0, 201, -1])
def test_limit_out_of_range_422(client_and_service, limit):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders", params={"tenant_id": TENANT_ID, "limit": limit}
    )
    assert resp.status_code == 422


def test_negative_offset_422(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders", params={"tenant_id": TENANT_ID, "offset": -1}
    )
    assert resp.status_code == 422


def test_invalid_date_is_422_not_500(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "date_from": "abc"},
    )
    assert resp.status_code == 422


def test_date_from_after_date_to_is_400(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={
            "tenant_id": TENANT_ID,
            "date_from": "2026-09-10",
            "date_to": "2026-09-01",
        },
    )
    assert resp.status_code == 400


def test_invalid_source_type_422(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "source_type": "ftp"},
    )
    assert resp.status_code == 422


def test_search_and_status_length_limits_422(client_and_service):
    client, _ = client_and_service
    too_long_search = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "search": "x" * 101},
    )
    too_long_status = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "status": "x" * 51},
    )
    assert too_long_search.status_code == 422
    assert too_long_status.status_code == 422


# ---------------------------------------------------------------------------
# 5) Connection security
# ---------------------------------------------------------------------------


def test_connection_from_other_tenant_404(client_and_service):
    client, service = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "connection_id": CONN_OTHER_TENANT},
    )
    assert resp.status_code == 404
    assert service.db.entity_calls() == []


def test_unknown_connection_404(client_and_service):
    client, _ = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "connection_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


def test_valid_connection_filter_is_bound_as_param(client_and_service):
    client, service = client_and_service
    resp = client.get(
        "/api/v1/tables/orders",
        params={"tenant_id": TENANT_ID, "connection_id": CONN_API},
    )
    assert resp.status_code == 200
    sql, params = service.db.entity_calls()[0]
    assert "t.connection_id = %s" in sql
    assert CONN_API in params
    assert CONN_API not in sql


# ---------------------------------------------------------------------------
# 6) Error handling (no raw DB errors leaked)
# ---------------------------------------------------------------------------


def test_unexpected_db_error_is_generic_500(client_and_service):
    client, service = client_and_service
    service.db.fail_with = RuntimeError("password=supersecret host=db.internal")
    resp = client.get("/api/v1/tables/orders", params={"tenant_id": TENANT_ID})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Query failed"
    assert "supersecret" not in resp.text


# ---------------------------------------------------------------------------
# 7) Sources route
# ---------------------------------------------------------------------------


def test_sources_file_has_dataset_and_api_has_null(client_and_service):
    client, _ = client_and_service
    resp = client.get("/api/v1/tables/sources", params={"tenant_id": TENANT_ID})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    by_id = {i["connection_id"]: i for i in items}

    file_src = by_id[CONN_FILE]
    assert file_src["source_type"] == "file"
    assert file_src["platform_code"] == "file_upload"
    assert file_src["dataset"] == {
        "id": "ds-1",
        "filename": "orders.csv",
        "file_type": "csv",
        "status": "completed",
        "row_count": 12,
        "created_at": "2026-09-02T00:00:00Z",
    }

    api_src = by_id[CONN_API]
    assert api_src["source_type"] == "api"
    assert api_src["dataset"] is None


def test_sources_counts_merged_in_python(client_and_service):
    client, service = client_and_service
    items = client.get(
        "/api/v1/tables/sources", params={"tenant_id": TENANT_ID}
    ).json()["items"]
    by_id = {i["connection_id"]: i for i in items}
    assert by_id[CONN_API]["counts"] == {"orders": 5, "products": 3, "customers": 0}
    assert by_id[CONN_FILE]["counts"] == {"orders": 12, "products": 0, "customers": 0}

    # exactly one grouped count query per entity (3 total), not one per connection
    count_calls = [
        c
        for c in service.db.calls
        if c[0].lstrip().startswith("SELECT connection_id, count(*)")
    ]
    assert len(count_calls) == 3


def test_sources_do_not_leak_secrets_or_internal_fields(client_and_service):
    client, service = client_and_service
    # even if the DB row carried secrets, the response must not contain them
    service.db.sources_rows[1].update(
        {
            "config": {"api_key": "sk-secret"},
            "metadata": {"x": 1},
            "base_url": "https://shop.example.com",
            "tenant_id": TENANT_ID,
        }
    )
    resp = client.get("/api/v1/tables/sources", params={"tenant_id": TENANT_ID})
    text = resp.text
    assert "sk-secret" not in text
    assert "base_url" not in text
    assert "config" not in text
    assert "metadata" not in text
    assert "tenant_id" not in text


def test_sources_route_is_not_captured_by_entity_route(client_and_service):
    client, _ = client_and_service
    data = client.get("/api/v1/tables/sources", params={"tenant_id": TENANT_ID}).json()
    assert "items" in data and "entity" not in data


# ---------------------------------------------------------------------------
# 8) Query builder (pure function, no DB)
# ---------------------------------------------------------------------------


def test_escape_like_percent_underscore_backslash():
    assert _escape_like("50%") == "%50\\%%"
    assert _escape_like("a_b") == "%a\\_b%"
    assert _escape_like("a\\b") == "%a\\\\b%"
    assert _escape_like("a%b_c\\d") == "%a\\%b\\_c\\\\d%"


def test_user_input_only_in_params_not_in_sql():
    sql, params = build_table_query(
        "orders",
        tenant_id=TENANT_ID,
        search="O'Reilly 100%",
        status="PAID",
        fulfillment_status="Unfulfilled",
        connection_id=CONN_API,
    )
    assert "O'Reilly" not in sql
    assert "100" not in sql  # the only digits in params
    assert TENANT_ID not in sql
    assert CONN_API not in sql
    assert "%O'Reilly 100\\%%" in params
    assert "paid" in params  # status is lower-cased in params
    assert "unfulfilled" in params


def test_tenant_id_is_first_param_and_in_where():
    sql, params = build_table_query("orders", tenant_id=TENANT_ID)
    assert params[0] == TENANT_ID
    where_part = sql.split("WHERE", 1)[1]
    assert "t.tenant_id = %s" in where_part
    # joins are also tenant-scoped
    assert "c.tenant_id = t.tenant_id" in sql


def test_stable_tiebreaker_and_nulls_last():
    sql, _ = build_table_query(
        "orders", tenant_id=TENANT_ID, sort_by="total_amount", sort_dir="asc"
    )
    order_by = sql.split("ORDER BY", 1)[1]
    assert "NULLS LAST" in order_by
    assert "t.id" in order_by
    assert order_by.strip().startswith("t.total_amount ASC")


@pytest.mark.parametrize("entity", ["orders", "products", "customers"])
def test_default_sort_and_window_total(entity):
    sql, params = build_table_query(entity, tenant_id=TENANT_ID)
    assert "count(*) over() AS _total" in sql
    assert "DESC NULLS LAST" in sql
    assert params[-2:] == [50, 0]


def test_sort_allowlist_rejects_unknown_and_unsortable():
    with pytest.raises(ValueError):
        build_table_query("orders", tenant_id=TENANT_ID, sort_by="x; drop table y")
    # 'source' column exists but is not sortable
    with pytest.raises(ValueError):
        build_table_query("orders", tenant_id=TENANT_ID, sort_by="source")
    # a sort key from another entity is invalid here
    with pytest.raises(ValueError):
        build_table_query("orders", tenant_id=TENANT_ID, sort_by="title")


def test_date_to_is_inclusive():
    sql, params = build_table_query(
        "orders",
        tenant_id=TENANT_ID,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
    )
    assert ">= %s::date" in sql
    assert "< (%s::date + interval '1 day')" in sql
    assert date(2026, 9, 1) in params
    assert date(2026, 9, 30) in params


def test_dates_are_ignored_for_non_order_entities():
    sql, params = build_table_query(
        "products", tenant_id=TENANT_ID, date_from=date(2026, 9, 1)
    )
    assert "::date" not in sql
    assert date(2026, 9, 1) not in params


def test_status_normalization_expression_for_orders():
    sql, _ = build_table_query("orders", tenant_id=TENANT_ID, status="paid")
    assert (
        "lower(replace(btrim(coalesce(nullif(t.status,''), t.financial_status)), ' ', '_')) = %s"
        in sql
    )


def test_fulfillment_filter_only_for_orders():
    sql_orders, _ = build_table_query(
        "orders", tenant_id=TENANT_ID, fulfillment_status="fulfilled"
    )
    sql_products, params_products = build_table_query(
        "products", tenant_id=TENANT_ID, fulfillment_status="fulfilled"
    )
    assert "t.fulfillment_status" in sql_orders.split("WHERE", 1)[1]
    assert "fulfillment" not in sql_products.split("WHERE", 1)[1]
    assert "fulfilled" not in params_products


def test_source_type_filter_uses_platform_code():
    sql_file, _ = build_table_query("orders", tenant_id=TENANT_ID, source_type="file")
    sql_api, _ = build_table_query("orders", tenant_id=TENANT_ID, source_type="api")
    sql_all, _ = build_table_query("orders", tenant_id=TENANT_ID)
    assert "p.code = 'file_upload'" in sql_file
    assert "p.code != 'file_upload'" in sql_api
    assert "p.code =" not in sql_all.split("WHERE", 1)[1]
    assert "p.code !=" not in sql_all.split("WHERE", 1)[1]


def test_blank_search_is_ignored():
    sql, params = build_table_query("orders", tenant_id=TENANT_ID, search="   ")
    assert "ILIKE" not in sql
    assert params == [TENANT_ID, 50, 0]


def test_search_joins_expressions_with_or_and_escape_clause():
    sql, params = build_table_query("customers", tenant_id=TENANT_ID, search="ali")
    where_part = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert where_part.count("ILIKE %s ESCAPE '\\'") == 5
    assert where_part.count(" OR ") == 4
    assert params[1:6] == ["%ali%"] * 5


def test_every_entity_selects_source_fields():
    for entity in ("orders", "products", "customers"):
        sql, _ = build_table_query(entity, tenant_id=TENANT_ID)
        assert "c.name AS source_name" in sql
        assert "p.name AS source" in sql
        assert "AS source_type" in sql
        assert "t.connection_id AS connection_id" in sql


@pytest.mark.parametrize("entity", ["orders", "products", "customers"])
def test_internal_columns_are_never_selected(entity):
    sql, _ = build_table_query(entity, tenant_id=TENANT_ID)
    select_part = sql.split("FROM", 1)[0]
    for key in INTERNAL_KEYS:
        assert key not in select_part


def test_order_date_uses_business_date_not_insert_time_only():
    sql, _ = build_table_query("orders", tenant_id=TENANT_ID)
    assert "coalesce(t.source_created_at, t.created_at) AS order_date" in sql


def test_customer_name_expression():
    sql, _ = build_table_query("customers", tenant_id=TENANT_ID)
    assert (
        "coalesce(nullif(btrim(t.display_name),''), "
        "nullif(btrim(concat_ws(' ', t.first_name, t.last_name)),''), t.email) AS name"
    ) in sql


def test_count_query_shares_exact_where_with_page_query():
    kwargs = dict(
        tenant_id=TENANT_ID,
        connection_id=CONN_API,
        source_type="api",
        search="abc",
        status="paid",
        fulfillment_status="fulfilled",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
    )
    page_sql, page_params = build_table_query("orders", limit=10, offset=20, **kwargs)
    count_sql, count_params = build_count_query("orders", **kwargs)

    page_where = page_sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0].strip()
    count_where = count_sql.split("WHERE", 1)[1].strip()
    assert page_where == count_where
    assert page_params[:-2] == count_params
    assert "LIMIT" not in count_sql


def test_tables_module_has_no_write_sql():
    """Read-only guarantee: the module never builds a write/DDL statement."""
    import inspect
    import re

    source = inspect.getsource(tables)
    for word in (
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE TABLE",
    ):
        assert not re.search(rf"\b{word}\b", source), f"{word} found in tables.py"
