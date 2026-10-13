from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

import pytest

from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    is_overview_request,
    parse_overview_window,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient


def test_is_overview_request_detection():
    # Overview requests must be detected
    assert is_overview_request("generate me a dashboard for my data") is True
    assert is_overview_request("generate a dashboard for my data") is True
    assert is_overview_request("show my dashboard") is True
    assert is_overview_request("give me an overview") is True
    assert is_overview_request("summarize my data") is True
    assert is_overview_request("show me my dashboard") is True
    assert is_overview_request("give me an overview of my store") is True
    assert is_overview_request("generate a dashboard") is True

    # Specific analytical questions must NOT be routed as overview
    assert is_overview_request("What is the total revenue?") is False
    assert is_overview_request("Show revenue for the last 30 days") is False
    assert is_overview_request("What was the refund rate last month?") is False
    assert is_overview_request("Compare revenue between channels") is False
    assert is_overview_request("Breakdown of sales by product") is False
    assert is_overview_request("Why did refunds spike in March?") is False
    assert is_overview_request("How many orders were placed today?") is False


@pytest.mark.parametrize(
    "question",
    [
        "What is the total revenue?",
        "Show revenue for the last 30 days",
        "sales overview last 30 days (revenue, orders, AOV, top products by category)",
        "refund rate last month",
        "compare revenue between channels",
        "top 5 products",
        "orders by day",
        "why did refunds spike in March",
        "how many orders yesterday",
        "revenue",
        "orders",
        "what is my AOV",
        "show my store revenue",
        "meri sales kitni hain",
        "my orders",
        "customers report",
        "sales report",
        "revenue last 30 days",
        "show revenue for the last 30 days",
        "top products last month",
        "orders by day this month",
        "compare this month and last month",
        "what is my revenue this month",
        None,
    ],
)
def test_is_overview_request_must_stay_false(question):
    assert is_overview_request(question) is False


@pytest.mark.parametrize(
    "question",
    [
        "generate me a dashboard for my data",
        "give me insights on my store",
        "analyze my data",
        "build me a report",
        "how is my store doing",
        "summarize my business",
        "mera dashboard dikhao",
        "mere data ka overview do",
        "dashboard banao",
        "show me an overview",
        "store summary",
        "business snapshot",
        "please give me a dashboard",
        "dashboard for last 30 days",
        "how is my store doing this month",
        "overview of the last 7 days",
        "give me a summary of the last quarter",
        "dashboard this year",
        "mera dashboard last 30 days",
    ],
)
def test_is_overview_request_must_be_true(question):
    assert is_overview_request(question) is True



def _setup_mock_analyst(monkeypatch, raw_profile_data=None, query_results=None):
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    analyst = AIAnalyst(fake_db, fake_llm)

    executed_queries: list[tuple[str, Any]] = []

    monkeypatch.setattr(fake_db, "create_query_run", lambda *a, **k: {"id": "run-overview-1"})
    monkeypatch.setattr(fake_db, "save_dashboard_spec", lambda *a, **k: {"id": "dash-overview-1"})
    monkeypatch.setattr(fake_db, "update_query_run", lambda *a, **k: None)
    monkeypatch.setattr(fake_db, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(fake_db, "maybe_title_conversation", lambda *a, **k: None)

    def get_data_profile_raw(tenant_id):
        if raw_profile_data is not None:
            return raw_profile_data
        return {
            "daily_sales": {
                "first_date": "2026-01-01",
                "last_date": "2026-08-10",
                "rows": 100,
                "currencies": [
                    {"currency_code": "USD", "orders_count_sum": 50, "net_sales_sum": 5000.0}
                ],
            },
            "tables": {
                "daily_sales": 100,
                "products": 20,
                "refunds": 5,
            },
            "silver_orders": 50,
            "orders_with_items": 50,
        }

    monkeypatch.setattr(fake_db, "get_data_profile_raw", get_data_profile_raw)

    def execute_readonly_query(sql, tenant_id, timeout_ms=10000):
        executed_queries.append((sql, tenant_id))
        if query_results and sql in query_results:
            return query_results[sql]
        if "gold.daily_sales" in sql and "COALESCE(SUM(ds.gross_sales)" in sql:
            return [
                {
                    "gross_sales": 6000.0,
                    "discounts": 500.0,
                    "refunds": 500.0,
                    "net_sales": 5000.0,
                    "orders_count": 50,
                    "units_sold": 100,
                    "aov": 100.0,
                }
            ]
        if "gold.daily_sales" in sql and "ds.metric_date" in sql:
            return [
                {"metric_date": "2026-08-09", "net_sales": 2500.0, "orders_count": 25},
                {"metric_date": "2026-08-10", "net_sales": 2500.0, "orders_count": 25},
            ]
        if "gold.product_daily" in sql:
            return [
                {
                    "product": "Cool Shirt",
                    "category": "Apparel",
                    "net_sales": 3000.0,
                    "units_sold": 60,
                }
            ]
        if "gold.refund_daily" in sql:
            return [{"refund_count": 5, "refund_amount": 500.0}]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", execute_readonly_query)
    fake_db.executed_queries = executed_queries
    return analyst, fake_db


def test_overview_routing_with_verified_data(monkeypatch):
    analyst, fake_db = _setup_mock_analyst(monkeypatch)
    res = analyst.ask("tenant-123", "generate me a dashboard for my data", include_debug=True)

    # 1. Response contract
    assert res["dashboard_id"] == "dash-overview-1"
    assert res["query_run_id"] == "run-overview-1"
    assert "verified dashboard overview" in res["answer"].lower()
    assert res["route"] is None

    # 2. Tenant isolation & parameterized queries
    assert len(fake_db.executed_queries) > 0
    for sql, tid in fake_db.executed_queries:
        assert tid == "tenant-123"
        assert "%(tenant_id)s" in sql
        assert ":tenant_id" not in sql  # Converted by SQLGuard

    # 3. Verified numbers come strictly from DB
    dashboard = res["dashboard"]
    assert dashboard["no_data"] is False
    assert dashboard["currency"] == "USD"
    kpis = {k["column"]: k["value"] for k in dashboard["kpis"]}
    assert kpis["net_sales"] == 5000.0
    assert kpis["orders_count"] == 50
    assert kpis["gross_sales"] == 6000.0

    # KPI polish: formats, labels, duplicate drop
    kpi_records = {k["id"]: k for k in dashboard["kpis"]}
    assert "refund_amount" not in kpi_records  # Dropped because "refunds" is present
    assert kpi_records["net_sales"]["format"] == "currency"
    assert kpi_records["gross_sales"]["format"] == "currency"
    assert kpi_records["discounts"]["format"] == "currency"
    assert kpi_records["refunds"]["format"] == "currency"
    assert kpi_records["refunds"]["label"] == "Refunds (amount)"
    assert kpi_records["aov"]["format"] == "currency"
    assert kpi_records["aov"]["label"] == "Average Order Value"
    assert kpi_records["orders_count"]["format"] == "integer"
    assert kpi_records["orders_count"]["label"] == "Orders"
    assert kpi_records["units_sold"]["format"] == "integer"

    # Charts check: top_products chart y_field == "net_sales" and data contains net_sales
    charts = {c["id"]: c for c in dashboard["charts"]}
    top_prod_chart = next(c for c in dashboard["charts"] if "top_products" in c["id"] or c["title"].startswith("Top products"))
    assert top_prod_chart["x_field"] == "product"
    assert top_prod_chart["y_field"] == "net_sales"
    assert len(top_prod_chart["data"]) > 0
    assert "net_sales" in top_prod_chart["data"][0]
    assert top_prod_chart["data"][0]["net_sales"] == 3000.0

    # Top-level rows: merged revenue_trend and orders_trend daily table
    assert res["rows"] == [
        {"metric_date": "2026-08-09", "net_sales": 2500.0, "orders_count": 25},
        {"metric_date": "2026-08-10", "net_sales": 2500.0, "orders_count": 25},
    ]
    if "debug" in res:
        assert res["debug"]["row_count"] == len(res["rows"])

    # 4. Data range reflects recipe query window, observed_data_range reflects observed profile dates
    assert dashboard["data_range"] == {
        "first_date": "2026-05-13",
        "last_date": "2026-08-10",
    }
    assert dashboard["observed_data_range"] == {
        "first_date": "2026-01-01",
        "last_date": "2026-08-10",
    }


def test_overview_empty_no_data(monkeypatch):
    empty_profile = {
        "daily_sales": {"first_date": None, "last_date": None, "rows": 0, "currencies": []},
        "tables": {},
        "silver_orders": 0,
        "orders_with_items": 0,
    }
    analyst, fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=empty_profile)
    res = analyst.ask("tenant-123", "show my dashboard")

    assert res["dashboard_id"] == "dash-overview-1"
    assert "No data has been synced or uploaded for this workspace yet." in res["answer"]
    assert res["dashboard"]["no_data"] is True
    assert res["dashboard"]["kpis"] == []
    assert res["dashboard"]["charts"] == []
    assert len(fake_db.executed_queries) == 0


def test_specific_question_stays_on_analytical_path(monkeypatch):
    analyst, fake_db = _setup_mock_analyst(monkeypatch)
    rag_called = []
    monkeypatch.setattr(
        analyst.retriever,
        "retrieve",
        lambda *a, **k: rag_called.append(True) or [
            {"chunk_id": "ctx-1", "title": "Sales", "similarity": 0.9, "content": "Sales context"}
        ],
    )
    monkeypatch.setattr(
        fake_db,
        "semantic_catalog_snapshot",
        lambda *a: {
            "metrics": [
                {
                    "metric_code": "revenue",
                    "display_name": "Revenue",
                    "calculation_type": "sum",
                    "sql_expression": "SUM(ds.net_sales)",
                    "data_type": "currency",
                    "preferred_source_schema": "gold",
                    "preferred_source_table": "daily_sales",
                    "default_time_column": "metric_date",
                    "allowed_dimensions": ["date"],
                    "requires_currency_filter": True,
                }
            ],
            "dimensions": [],
            "permissions": [{"schema_name": "gold", "table_name": "daily_sales", "max_rows": 500}],
        },
    )

    fake_llm = analyst.llm

    def generate_json(prompt, **kwargs):
        if kwargs.get("schema_name") == "analytics_query_plan":
            return {
                "route": "metric",
                "title": "Net Sales",
                "sql": "SELECT COALESCE(SUM(ds.net_sales), 0) AS revenue FROM gold.daily_sales ds WHERE ds.tenant_id = :tenant_id",
                "intent": {
                    "metric": "revenue",
                    "dimensions": [],
                    "date_range": "30d",
                    "comparison": None,
                    "filters": {},
                },
            }
        return {"answer": "Revenue is 5000", "dashboard": {"title": "Sales"}}

    monkeypatch.setattr(fake_llm, "generate_json", generate_json)

    res = analyst.ask("tenant-123", "What is the total revenue?")
    # Verified it went to RAG retriever
    assert len(rag_called) == 1
    assert res["route"] == "metric"


def test_overview_observed_longer_than_recipe_window(monkeypatch):
    """When observed data range spans 1 year, recipe window is capped to 90d while observed is preserved."""
    profile_1y = {
        "daily_sales": {
            "first_date": "2025-01-01",
            "last_date": "2026-01-01",
            "rows": 365,
            "currencies": [
                {"currency_code": "USD", "orders_count_sum": 100, "net_sales_sum": 10000.0}
            ],
        },
        "tables": {"daily_sales": 365, "products": 10, "refunds": 2},
        "silver_orders": 100,
        "orders_with_items": 100,
    }
    analyst, fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=profile_1y)
    res = analyst.ask("tenant-123", "show my dashboard")

    dash = res["dashboard"]
    assert dash["no_data"] is False
    # Recipe window: 90 days ending at anchor 2026-01-01 -> 2025-10-04 to 2026-01-01
    assert dash["data_range"]["first_date"] == "2025-10-04"
    assert dash["data_range"]["last_date"] == "2026-01-01"
    # Observed coverage: full dataset
    assert dash["observed_data_range"]["first_date"] == "2025-01-01"
    assert dash["observed_data_range"]["last_date"] == "2026-01-01"


def test_overview_single_all_null_row_returns_clean_no_data(monkeypatch):
    """Single all-null row produces no usable widgets and returns clean no-data response without fabricated KPIs."""
    null_rows = [
        {
            "gross_sales": None,
            "discounts": None,
            "refunds": None,
            "net_sales": None,
            "orders_count": None,
            "units_sold": None,
            "aov": None,
        }
    ]
    query_results = {}
    analyst, fake_db = _setup_mock_analyst(monkeypatch)
    # Monkeypatch execute_readonly_query to return all-null rows for all recipes
    monkeypatch.setattr(fake_db, "execute_readonly_query", lambda sql, tid, **kw: null_rows if "COALESCE" in sql else [])

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "give me an overview")

    dash = res["dashboard"]
    assert dash["no_data"] is True
    assert dash["kpis"] == []
    assert dash["charts"] == []
    assert res["rows"] == []
    assert "no usable data" in res["answer"].lower()
    # Ensure completed query run lifecycle is preserved without fabricating numbers
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "completed"


def test_overview_all_recipes_failing_or_rejected(monkeypatch):
    """When all recipes fail validation or execution, fail safely using query-run error contract instead of falsely claiming no data exists."""
    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    def failing_execute(sql, tid, **kw):
        raise RuntimeError("Database connection timeout")

    monkeypatch.setattr(fake_db, "execute_readonly_query", failing_execute)

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "give me an overview")

    dash = res["dashboard"]
    assert dash["no_data"] is False
    assert dash["kpis"] == []
    assert dash["charts"] == []
    # Verify it does not falsely claim "no data has been synced" or "no usable data was found"
    assert "failed validation or execution" in res["answer"].lower()
    # Query run status marked failed
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "failed"
    assert "failed validation or execution" in update_calls[0]["error_message"]
    assert update_calls[0]["selected_context"]["failure"] is True
    assert len(update_calls[0]["selected_context"]["failed_recipe_ids"]) > 0
    assert len(update_calls[0]["selected_context"]["successful_recipe_ids"]) == 0


def test_overview_partial_success_retains_only_verified_widgets(monkeypatch):
    """When some recipes fail but others succeed, retain verified widgets and record partial metadata."""
    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    def partial_execute(sql, tid, **kw):
        # Fail the KPI summary query, succeed the trend and top_products queries
        if "COALESCE(SUM(ds.gross_sales)" in sql:
            raise RuntimeError("Syntax error in KPI recipe")
        if "gold.daily_sales" in sql and "ds.metric_date" in sql:
            return [
                {"metric_date": "2026-08-09", "net_sales": 2500.0, "orders_count": 25},
                {"metric_date": "2026-08-10", "net_sales": 2500.0, "orders_count": 25},
            ]
        if "gold.product_daily" in sql:
            return [
                {"product": "Cool Shirt", "category": "Apparel", "net_sales": 3000.0, "units_sold": 60}
            ]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", partial_execute)

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "give me an overview")

    dash = res["dashboard"]
    # Verified usable widgets exist, so no_data is False
    assert dash["no_data"] is False
    assert dash.get("partial") is True
    assert len(dash.get("charts") or []) > 0
    # KPI query failed, so no fabricated KPIs should exist
    assert dash.get("kpis") == []
    # Query run marked completed with partial failure metadata
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "completed"
    assert update_calls[0]["selected_context"]["partial"] is True
    assert "kpi_summary" in update_calls[0]["selected_context"]["failed_recipe_ids"]
    assert "revenue_trend" in update_calls[0]["selected_context"]["successful_recipe_ids"]


def test_overview_sql_guard_rejects_recipe_without_executing(monkeypatch):
    """When SQLGuard rejects a recipe, execution must not happen for that query and failure is tracked."""
    from commerce_connector.platform.sql_guard import GuardResult, SQLGuard

    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    executed_queries = []
    def recording_execute(sql, tid, **kw):
        executed_queries.append(sql)
        if "COALESCE(SUM(ds.gross_sales)" in sql:
            return [
                {
                    "gross_sales": 6000.0,
                    "discounts": 500.0,
                    "refunds": 500.0,
                    "net_sales": 5000.0,
                    "orders_count": 50,
                    "units_sold": 100,
                    "aov": 100.0,
                }
            ]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", recording_execute)

    orig_validate = SQLGuard.validate
    def guarded_validate(self, sql, **kwargs):
        # Reject specifically the revenue_trend recipe at SQLGuard level
        if "ORDER BY ds.metric_date" in sql:
            return GuardResult(ok=False, sql=sql, reason="Blocked unsafe clause")
        return orig_validate(self, sql, **kwargs)

    monkeypatch.setattr(SQLGuard, "validate", guarded_validate)

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "give me an overview")

    dash = res["dashboard"]
    # Rejection prevented the rejected revenue_trend query from executing
    assert not any("ORDER BY ds.metric_date" in sql for sql in executed_queries)
    assert not any("revenue_trend" in sql.lower() for sql in executed_queries)
    # Successful KPI recipe executed and provided verified KPIs
    assert any("COALESCE(SUM(ds.gross_sales)" in sql for sql in executed_queries)
    assert len(dash.get("kpis") or []) > 0
    assert dash.get("partial") is True
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "completed"
    assert update_calls[0]["selected_context"]["partial"] is True
    assert "revenue_trend" in update_calls[0]["selected_context"]["failed_recipe_ids"]
    assert "kpi_summary" in update_calls[0]["selected_context"]["successful_recipe_ids"]


def test_overview_sql_guard_rejects_all_recipes_fails_query_run(monkeypatch):
    """When SQLGuard rejects all recipes, query run fails safely without executing any SQL."""
    from commerce_connector.platform.sql_guard import GuardResult, SQLGuard

    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    executed_queries = []
    monkeypatch.setattr(fake_db, "execute_readonly_query", lambda sql, tid, **kw: executed_queries.append(sql) or [])

    monkeypatch.setattr(SQLGuard, "validate", lambda self, sql, **kw: GuardResult(ok=False, sql=sql, reason="Disallowed query"))

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "give me an overview")

    # Absolutely zero SQL executed against DB
    assert len(executed_queries) == 0

    dash = res["dashboard"]
    assert dash["no_data"] is False
    assert dash["kpis"] == []
    assert dash["charts"] == []
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "failed"
    assert update_calls[0]["selected_context"]["failure"] is True
    assert len(update_calls[0]["selected_context"]["failed_recipe_ids"]) > 0
    assert len(update_calls[0]["selected_context"]["successful_recipe_ids"]) == 0


def test_overview_genuinely_empty_data_lifecycle(monkeypatch):
    """When tenant data profile indicates no data synced, use completed query run and dashboard.no_data=True."""
    raw_profile_empty = {
        "daily_sales": {"first_date": None, "last_date": None, "rows": 0, "currencies": []},
        "tables": {"daily_sales": 0, "products": 0, "refunds": 0},
        "silver_orders": 0,
        "orders_with_items": 0,
    }
    analyst, fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=raw_profile_empty)

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "show me my dashboard")

    dash = res["dashboard"]
    assert dash["no_data"] is True
    assert dash["currency"] is None
    assert dash["kpis"] == []
    assert dash["charts"] == []
    assert "no data has been synced" in res["answer"].lower()
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "completed"
    assert update_calls[0]["selected_context"]["profile_has_data"] is False


def test_overview_merged_rows_date_objects_and_strings(monkeypatch):
    """When metric_date comes as date objects in one recipe and ISO strings in the other, rows merge correctly."""
    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    def custom_execute(sql, tid, **kw):
        if "gold.daily_sales" in sql and "ds.metric_date" in sql:
            if "net_sales" in sql:
                # revenue_trend returns Python date objects
                return [
                    {"metric_date": date(2026, 8, 10), "net_sales": 300.0},
                    {"metric_date": date(2026, 8, 9), "net_sales": 200.0},
                ]
            if "orders_count" in sql:
                # orders_trend returns ISO string representations
                return [
                    {"metric_date": "2026-08-09T00:00:00", "orders_count": 2},
                    {"metric_date": "2026-08-10", "orders_count": 3},
                ]
        if "gold.daily_sales" in sql and "COALESCE(SUM(ds.gross_sales)" in sql:
            return [{"gross_sales": 500.0, "discounts": 0.0, "refunds": 0.0, "net_sales": 500.0, "orders_count": 5, "units_sold": 5, "aov": 100.0}]
        if "gold.product_daily" in sql:
            return [{"product": "Widget", "category": "General", "net_sales": 500.0, "units_sold": 5}]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", custom_execute)

    res = analyst.ask("tenant-123", "give me an overview", include_debug=True)

    expected_rows = [
        {"metric_date": "2026-08-09", "net_sales": 200.0, "orders_count": 2},
        {"metric_date": "2026-08-10", "net_sales": 300.0, "orders_count": 3},
    ]
    assert res["rows"] == expected_rows
    assert res["debug"]["row_count"] == 2
    assert res["dashboard"]["currency"] == "USD"


def test_overview_refunds_summary_kpi_polish(monkeypatch):
    """Test refunds KPI polish: when refunds recipe runs, refund_count has label 'Refunds (count)' and format 'integer'."""
    raw_profile = {
        "daily_sales": {
            "first_date": "2026-01-01",
            "last_date": "2026-08-10",
            "rows": 100,
            "currencies": [{"currency_code": "USD", "orders_count_sum": 50, "net_sales_sum": 5000.0}],
        },
        "tables": {"daily_sales": 100, "products": 20, "refunds": 5},
        "silver_orders": 50,
        "orders_with_items": 50,
    }
    analyst, fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=raw_profile)
    res = analyst.ask("tenant-123", "give me an overview")
    dashboard = res["dashboard"]
    kpis = {k["id"]: k for k in dashboard["kpis"]}
    assert "refund_count" in kpis
    assert kpis["refund_count"]["label"] == "Refunds (count)"
    assert kpis["refund_count"]["format"] == "integer"
    assert "refund_amount" not in kpis  # Since refunds was present in kpi_summary


def test_overview_previous_period_comparison_enriched(monkeypatch):
    """(c) overview with fake DB returning different KPI rows for current and previous window -> change_pct correct."""
    from decimal import Decimal

    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    def custom_execute(sql, tid, **kw):
        if "gold.daily_sales" in sql and "COALESCE(SUM(ds.gross_sales)" in sql:
            # Tell the two windows apart by checking whether previous window's start date literal appears
            if "2026-02-12" in sql:
                return [
                    {
                        "gross_sales": Decimal("5000.0"),
                        "discounts": Decimal("400.0"),
                        "refunds": Decimal("300.0"),
                        "net_sales": Decimal("4000.0"),
                        "orders_count": 40,
                        "units_sold": 80,
                        "aov": Decimal("100.0"),
                    }
                ]
            else:
                return [
                    {
                        "gross_sales": Decimal("6000.0"),
                        "discounts": Decimal("500.0"),
                        "refunds": Decimal("500.0"),
                        "net_sales": Decimal("5000.0"),
                        "orders_count": 50,
                        "units_sold": 100,
                        "aov": Decimal("100.0"),
                    }
                ]
        if "gold.daily_sales" in sql and "ds.metric_date" in sql:
            return [
                {"metric_date": "2026-08-09", "net_sales": 2500.0, "orders_count": 25},
                {"metric_date": "2026-08-10", "net_sales": 2500.0, "orders_count": 25},
            ]
        if "gold.product_daily" in sql:
            return [{"product": "Shirt", "category": "Apparel", "net_sales": 3000.0, "units_sold": 60}]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", custom_execute)

    res = analyst.ask("tenant-123", "give me an overview")
    dash = res["dashboard"]

    # Comparison data range
    assert dash["previous_data_range"] == {
        "first_date": "2026-02-12",
        "last_date": "2026-05-12",
    }
    assert dash.get("partial") is not True

    # Validate KPI enrichment
    kpis = {k["id"]: k for k in dash["kpis"]}

    # net_sales: 5000 vs 4000 = 25.0%
    assert kpis["net_sales"]["value"] == Decimal("5000.0")
    assert kpis["net_sales"]["previous_value"] == Decimal("4000.0")
    assert kpis["net_sales"]["change_pct"] == 25.0
    assert kpis["net_sales"]["comparison"] == "vs previous 90 days"
    assert kpis["net_sales"]["higher_is_better"] is True

    # gross_sales: 6000 vs 5000 = 20.0%
    assert kpis["gross_sales"]["change_pct"] == 20.0
    assert kpis["gross_sales"]["higher_is_better"] is True

    # discounts: 500 vs 400 = 25.0%
    assert kpis["discounts"]["change_pct"] == 25.0
    assert kpis["discounts"]["higher_is_better"] is False

    # refunds: 500 vs 300 = 66.7%
    assert kpis["refunds"]["change_pct"] == 66.7
    assert kpis["refunds"]["higher_is_better"] is False

    # orders_count: 50 vs 40 = 25.0%
    assert kpis["orders_count"]["change_pct"] == 25.0
    assert kpis["orders_count"]["higher_is_better"] is True

    # aov: 100 vs 100 = 0.0%
    assert kpis["aov"]["change_pct"] == 0.0
    assert kpis["aov"]["higher_is_better"] is True

    # Verify "internal" never appears in API response or dashboard dict
    assert "internal" not in res
    assert "internal" not in dash
    for k in dash["kpis"]:
        assert "internal" not in k
    for c in dash["charts"]:
        assert "internal" not in c


def test_overview_previous_value_zero_or_non_numeric(monkeypatch):
    """(d) previous value 0 or non-numeric -> change_pct None, no crash."""
    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    def custom_execute(sql, tid, **kw):
        if "gold.daily_sales" in sql and "COALESCE(SUM(ds.gross_sales)" in sql:
            if "2026-02-12" in sql:
                return [
                    {
                        "gross_sales": 0.0,
                        "discounts": None,
                        "refunds": "not-a-number",
                        "net_sales": 0,
                        "orders_count": 0,
                        "units_sold": 0,
                        "aov": 0.0,
                    }
                ]
            else:
                return [
                    {
                        "gross_sales": 6000.0,
                        "discounts": 500.0,
                        "refunds": 500.0,
                        "net_sales": 5000.0,
                        "orders_count": 50,
                        "units_sold": 100,
                        "aov": 100.0,
                    }
                ]
        if "gold.daily_sales" in sql and "ds.metric_date" in sql:
            return [
                {"metric_date": "2026-08-09", "net_sales": 2500.0, "orders_count": 25},
                {"metric_date": "2026-08-10", "net_sales": 2500.0, "orders_count": 25},
            ]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", custom_execute)

    res = analyst.ask("tenant-123", "give me an overview")
    dash = res["dashboard"]
    kpis = {k["id"]: k for k in dash["kpis"]}

    # Zero previous value -> change_pct is None, no division by zero
    assert kpis["gross_sales"]["previous_value"] == 0.0
    assert kpis["gross_sales"]["change_pct"] is None
    assert kpis["gross_sales"]["comparison"] == "vs previous 90 days"
    assert kpis["gross_sales"]["higher_is_better"] is True

    # None previous value -> change_pct is None
    assert kpis["discounts"]["previous_value"] is None
    assert kpis["discounts"]["change_pct"] is None
    assert kpis["discounts"]["higher_is_better"] is False

    # Non-numeric previous value -> change_pct is None
    assert kpis["refunds"]["change_pct"] is None
    assert kpis["refunds"]["higher_is_better"] is False


def test_overview_previous_recipe_failure_isolated(monkeypatch):
    """(e) previous recipe fails -> KPIs still present without new keys; dashboard not partial, answer unchanged."""
    analyst, fake_db = _setup_mock_analyst(monkeypatch)

    def failing_execute(sql, tid, **kw):
        if "2026-02-12" in sql:
            raise RuntimeError("Database error executing kpi_previous_period")
        if "gold.daily_sales" in sql and "COALESCE(SUM(ds.gross_sales)" in sql:
            return [
                {
                    "gross_sales": 6000.0,
                    "discounts": 500.0,
                    "refunds": 500.0,
                    "net_sales": 5000.0,
                    "orders_count": 50,
                    "units_sold": 100,
                    "aov": 100.0,
                }
            ]
        if "gold.daily_sales" in sql and "ds.metric_date" in sql:
            return [
                {"metric_date": "2026-08-09", "net_sales": 2500.0, "orders_count": 25},
                {"metric_date": "2026-08-10", "net_sales": 2500.0, "orders_count": 25},
            ]
        return []

    monkeypatch.setattr(fake_db, "execute_readonly_query", failing_execute)

    update_calls = []
    monkeypatch.setattr(fake_db, "update_query_run", lambda run_id, **kw: update_calls.append(kw))

    res = analyst.ask("tenant-123", "give me an overview")
    dash = res["dashboard"]

    # Dashboard must NOT have partial=True because of internal recipe failure
    assert dash.get("partial") is not True
    assert "sections could not be loaded" not in res["answer"].lower()
    assert "verified dashboard overview" in res["answer"].lower()
    assert dash["previous_data_range"] is None

    # KPIs are present without comparison keys
    assert len(dash["kpis"]) > 0
    for kpi in dash["kpis"]:
        assert "previous_value" not in kpi
        assert "change_pct" not in kpi
        assert "comparison" not in kpi
        assert "higher_is_better" not in kpi

    # Failure recorded in query run selected_context without partial flag
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "completed"
    assert "kpi_previous_period" in update_calls[0]["selected_context"]["failed_recipe_ids"]
    assert update_calls[0]["selected_context"]["partial"] is False


def test_parse_overview_window_anchored():
    anchor = date(2026, 8, 10)
    assert parse_overview_window("last 30 days", anchor) == 30
    assert parse_overview_window("last 2 weeks", anchor) == 14
    assert parse_overview_window("this month", anchor) == 10
    assert parse_overview_window("ytd", anchor) == 222
    assert parse_overview_window("last week", anchor) == 7
    assert parse_overview_window("last 3 days", anchor) == 7  # clamped to min 7
    assert parse_overview_window("hello", anchor) is None
    # Crash-proof test with giant number: clamped before multiplying and final clamped to 366
    assert parse_overview_window("dashboard last 99999999999 days", anchor) == 366
    assert parse_overview_window(None, anchor) is None
    assert parse_overview_window("last 30 days", None) is None
    assert parse_overview_window("last 30 days", "invalid-date") is None


def test_overview_integration_last_30_days(monkeypatch):
    analyst, fake_db = _setup_mock_analyst(monkeypatch)
    res = analyst.ask("tenant-123", "dashboard for last 30 days", include_debug=True)

    dash = res["dashboard"]
    assert dash["window_days"] == 30
    assert dash["data_range"]["first_date"] == "2026-07-12"
    assert dash["data_range"]["last_date"] == "2026-08-10"

    # Assert SQL date literals start at 2026-07-12 and end at 2026-08-10
    assert len(fake_db.executed_queries) > 0
    found_literals = False
    for sql, tid in fake_db.executed_queries:
        if "2026-07-12" in sql and "2026-08-10" in sql:
            found_literals = True
            break
    assert found_literals is True


def test_overview_integration_giant_window_still_builds(monkeypatch):
    analyst, fake_db = _setup_mock_analyst(monkeypatch)
    res = analyst.ask("tenant-123", "dashboard last 99999999999 days", include_debug=True)

    dash = res["dashboard"]
    assert dash["window_days"] == 366
    assert dash["no_data"] is False
    assert len(dash["kpis"]) > 0


@pytest.mark.parametrize(
    "question",
    [
        "dashboard for yesterday",
        "dashboard for march",
        "overview for 2025",
        "dashboard for today",
        "overview next month",
    ],
)
def test_t4d_is_overview_request_must_be_false(question):
    assert is_overview_request(question) is False


@pytest.mark.parametrize(
    "question",
    [
        "dashboard for last 30 days",
        "overview of the last 2 weeks",
        "dashboard this month",
        "give me a summary of the last quarter",
        "dashboard this year",
        "dashboard",
    ],
)
def test_t4d_is_overview_request_must_be_true(question):
    assert is_overview_request(question) is True


def test_overview_integration_partial_window_suffix(monkeypatch):
    profile_20_days = {
        "daily_sales": {
            "first_date": "2026-07-22",
            "last_date": "2026-08-10",
            "rows": 20,
            "currencies": [
                {"currency_code": "USD", "orders_count_sum": 20, "net_sales_sum": 2000.0}
            ],
        },
        "tables": {"daily_sales": 20, "products": 10, "refunds": 2},
        "silver_orders": 20,
        "orders_with_items": 20,
    }
    analyst, fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=profile_20_days)
    res = analyst.ask("tenant-123", "dashboard for last 30 days")

    assert "last 20 days" in res["answer"]
    assert res["dashboard"]["window_days"] == 30


def test_overview_integration_full_window_suffix(monkeypatch):
    profile_200_days = {
        "daily_sales": {
            "first_date": "2026-01-01",
            "last_date": "2026-08-10",
            "rows": 200,
            "currencies": [
                {"currency_code": "USD", "orders_count_sum": 200, "net_sales_sum": 20000.0}
            ],
        },
        "tables": {"daily_sales": 200, "products": 10, "refunds": 2},
        "silver_orders": 200,
        "orders_with_items": 200,
    }
    analyst, fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=profile_200_days)
    res = analyst.ask("tenant-123", "dashboard for last 30 days")

    assert "last 30 days" in res["answer"]
    assert res["dashboard"]["window_days"] == 30


@pytest.mark.parametrize(
    "question,expected",
    [
        ("dashboard for Q1", False),
        ("dashboard for jan", False),
        ("dashboard for sept", False),
        ("dashboard for last monday", False),
        ("dashboard for 5 days ago", False),
        ("dashboard for last weekend", False),
        ("dashboard for the first half", False),
        ("dashboard since march", False),
        ("dashboard between jan and mar", False),
        ("dashboard for yesterday", False),
        ("dashboard for march", False),
        ("overview for 2025", False),
        ("dashboard for today", False),
        ("overview next month", False),
        ("dashboard", True),
        ("generate me a dashboard for my data", True),
        ("dashboard for last 30 days", True),
        ("overview of the last 2 weeks", True),
        ("dashboard this month", True),
        ("give me a summary of the last quarter", True),
        ("dashboard this year", True),
        ("show my dashboard", True),
        ("give me an overview", True),
    ],
)
def test_t4e_overview_request_time_windows(question: str, expected: bool):
    assert is_overview_request(question) is expected


def test_overview_answer_notes_separated_by_space(monkeypatch):
    profile = {
        "daily_sales": {
            "first_date": "2026-01-01",
            "last_date": "2026-08-10",
            "rows": 100,
            "currencies": [
                {"currency_code": "USD", "orders_count_sum": 50, "net_sales_sum": 5000.0},
                {"currency_code": "CAD", "orders_count_sum": 5, "net_sales_sum": 100.0},
                {"currency_code": "EUR", "orders_count_sum": 5, "net_sales_sum": 200.0},
                {"currency_code": "GBP", "orders_count_sum": 5, "net_sales_sum": 150.0},
            ],
        },
        "tables": {"daily_sales": 100, "products": 20, "refunds": 5},
        "silver_orders": 100,
        "orders_with_items": 10,
    }
    analyst, _fake_db = _setup_mock_analyst(monkeypatch, raw_profile_data=profile)
    answer = analyst.ask("tenant-123", "generate me a dashboard for my data")["answer"]

    assert "soit" not in answer
    assert "so it is not shown" in answer
    assert "Window: last" in answer
    for i, ch in enumerate(answer):
        if ch == "." and i + 1 < len(answer):
            assert answer[i + 1] == " "






