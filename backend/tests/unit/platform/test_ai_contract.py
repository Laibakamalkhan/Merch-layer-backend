from __future__ import annotations

from copy import deepcopy

import test_metric_resolver

from commerce_connector.platform.ai_analyst import _normalise_dashboard
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from commerce_connector.platform.sql_guard import SQLGuard
from commerce_connector.platform.analytics.metric_resolver import MetricDefinition


def _new_multi_query_analyst(monkeypatch, planner, final, *, result_rows=None):
    from commerce_connector.platform.ai_analyst import AIAnalyst

    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    analyst = AIAnalyst(fake_db, fake_llm)
    snapshot = deepcopy(test_metric_resolver.REAL_REGISTRY_SNAPSHOT)
    fake_db.executed_sql = []
    snapshot["permissions"] = [
        {"schema_name": "gold", "table_name": "daily_sales", "max_rows": 500},
        {"schema_name": "gold", "table_name": "refund_daily", "max_rows": 500},
    ]

    monkeypatch.setattr(
        analyst.retriever,
        "retrieve",
        lambda *a, **k: [
            {"chunk_id": "ctx-1", "title": "Sales", "similarity": 0.9, "content": "Sales context"}
        ],
    )
    monkeypatch.setattr(fake_db, "semantic_catalog_snapshot", lambda *a: snapshot)
    monkeypatch.setattr(fake_db, "create_query_run", lambda *a, **k: {"id": "run-multi"})
    monkeypatch.setattr(fake_db, "save_generated_query", lambda *a, **k: {"id": "generated"})
    monkeypatch.setattr(fake_db, "save_dashboard_spec", lambda *a, **k: {"id": "dash-multi"})
    monkeypatch.setattr(fake_db, "update_query_run", lambda *a, **k: None)
    monkeypatch.setattr(
        fake_db,
        "get_data_coverage",
        lambda *a, **k: {"first_date": None, "last_date": None, "days_with_data": 0},
    )
    def execute_readonly_query(sql, tenant_id):
        fake_db.executed_sql.append(sql)
        rows = result_rows(sql) if callable(result_rows) else result_rows
        if rows is not None:
            return rows
        return [{"net_sales": 400, "orders": 8, "average_order_value": 50}]

    monkeypatch.setattr(fake_db, "execute_readonly_query", execute_readonly_query)

    def generate_json(prompt, **kwargs):
        if kwargs.get("schema_name") == "analytics_query_plan":
            return planner(prompt)
        return final(prompt)

    monkeypatch.setattr(fake_llm, "generate_json", generate_json)
    return analyst


def _metric_plan(sql, metric="average_order_value", title="Sales KPIs"):
    return {
        "route": "metric",
        "intent": {
            "metric": metric,
            "dimensions": [],
            "date_range": "last_30_days",
            "comparison": "none",
            "filters": [],
        },
        "sql": sql,
        "title": title,
    }


def _multi_kpi_final(prompt):
    return {
        "answer": "The verified KPI results are ready.",
        "dashboard": {
            "title": "Sales Overview",
            "kpis": [
                {"label": "Net sales", "column": "net_sales", "aggregation": "value"},
                {"label": "Orders", "column": "orders", "aggregation": "value"},
                {
                    "label": "Average order value",
                    "column": "average_order_value",
                    "aggregation": "value",
                },
            ],
            "charts": [],
            "filters": [],
        },
    }


_VALID_REAL_KPI_SQL = (
    "select sum(ds.net_sales) as net_sales, sum(ds.orders_count) as orders, "
    "case when sum(ds.orders_count)=0 then null else sum(ds.net_sales)/sum(ds.orders_count) end "
    "as average_order_value from gold.daily_sales ds where ds.tenant_id = :tenant_id "
    "and ds.metric_date >= current_date - interval '30 day'"
)
_ORIGINAL_SALES_QUESTION = (
    "Give me a full sales overview for the last 30 days including total revenue, number of orders, "
    "average order value, and top-selling products broken down by category."
)


def test_analyst_retries_invalid_subquery_then_returns_success(monkeypatch):
    from commerce_connector.platform.analytics.metric_resolver import enforce_verified_metric_sql as enforce

    answers = iter([
        _metric_plan(_VALID_REAL_KPI_SQL.replace("ds.tenant_id = :tenant_id ", "")),
        _metric_plan(_VALID_REAL_KPI_SQL),
    ])
    analyst = _new_multi_query_analyst(
        monkeypatch,
        lambda prompt: next(answers),
        _multi_kpi_final,
    )

    response = analyst.ask("tenant-1", _ORIGINAL_SALES_QUESTION)

    assert "verified KPI results" in response["answer"]
    assert "category breakdown is not available yet" in response["answer"].lower()
    assert response["dashboard"]["kpis"][0]["value"] == 400
    assert response["sql"] == _VALID_REAL_KPI_SQL


def test_analyst_returns_friendly_partial_result_after_subquery_retries(monkeypatch):
    prompts = []
    invalid_sql = _VALID_REAL_KPI_SQL.replace("ds.tenant_id = :tenant_id ", "")

    def planner(prompt):
        prompts.append(prompt)
        return _metric_plan(invalid_sql)

    analyst = _new_multi_query_analyst(monkeypatch, planner, _multi_kpi_final)
    response = analyst.ask("tenant-1", _ORIGINAL_SALES_QUESTION)

    assert len(prompts) == 3
    assert "Failed SQL:" in prompts[1]
    assert invalid_sql in prompts[1]
    assert "Validation error:" in prompts[1]
    assert response["dashboard"]["no_data"] is True
    assert "couldn't produce one requested section" in response["answer"]
    assert "category breakdown is not available yet" in response["answer"].lower()
    assert "tenant filter missing" not in response["answer"].lower()
    assert "runtimeerror" not in response["answer"].lower()
    assert "traceback" not in response["answer"].lower()


def test_subquery_planner_caps_requests_at_four():
    from types import SimpleNamespace

    from commerce_connector.platform.ai_analyst import _build_subquery_tasks

    metrics = [
        MetricDefinition(
            code=f"metric_{index}",
            name=f"Metric {index}",
            preferred_source_schema="gold",
            preferred_source_table=f"table_{index}",
        )
        for index in range(6)
    ]
    tasks, capped, notice = _build_subquery_tasks(
        "Show those metrics",
        SimpleNamespace(matched=metrics),
    )

    assert len(tasks) == 4
    assert capped is True
    assert notice is None


def test_each_subquery_passes_metric_validator_and_sql_guard(monkeypatch):
    import commerce_connector.platform.ai_analyst as ai_analyst_module

    valid_sql_by_metric = {
        "net_sales": (
            "select sum(ds.net_sales) as net_sales from gold.daily_sales ds "
            "where ds.tenant_id = :tenant_id"
        ),
        "refund_rate": (
            "select rd.refund_rate as refund_rate from gold.refund_daily rd "
            "where rd.tenant_id = :tenant_id"
        ),
    }
    planner_answers = iter([
        _metric_plan(
            valid_sql_by_metric["refund_rate"].replace(
                "where rd.tenant_id = :tenant_id",
                "where true",
            ),
            metric="refund_rate",
            title="Refund Rate",
        ),
        _metric_plan(
            valid_sql_by_metric["refund_rate"],
            metric="refund_rate",
            title="Refund Rate",
        ),
        _metric_plan(
            valid_sql_by_metric["net_sales"],
            metric="net_sales",
            title="Net Sales",
        ),
    ])
    validation_calls = []
    guard_calls = []
    original_enforce = ai_analyst_module.enforce_verified_metric_sql
    original_guard = SQLGuard.validate

    def tracked_enforce(*args, **kwargs):
        validation_calls.append(args[0])
        return original_enforce(*args, **kwargs)

    def tracked_guard(guard, sql):
        result = original_guard(guard, sql)
        guard_calls.append(result)
        return result

    monkeypatch.setattr(ai_analyst_module, "enforce_verified_metric_sql", tracked_enforce)
    monkeypatch.setattr(SQLGuard, "validate", tracked_guard)

    def final(prompt):
        if "refund_daily" in prompt:
            return {
                "answer": "Refund rate verified.",
                "dashboard": {
                    "title": "Refund Rate",
                    "kpis": [{"label": "Refund rate", "column": "refund_rate", "aggregation": "value"}],
                    "charts": [],
                    "filters": [],
                },
            }
        return {
            "answer": "Net sales verified.",
            "dashboard": {
                "title": "Net Sales",
                "kpis": [{"label": "Net sales", "column": "net_sales", "aggregation": "value"}],
                "charts": [],
                "filters": [],
            },
        }

    def query_rows(sql):
        return (
            [{"refund_rate": 0.1}]
            if "refund_daily" in sql
            else [{"net_sales": 400}]
        )

    analyst = _new_multi_query_analyst(
        monkeypatch,
        lambda prompt: next(planner_answers),
        final,
        result_rows=query_rows,
    )
    response = analyst.ask("tenant-1", "Show revenue and refund percentage")

    assert len(validation_calls) == 3
    assert len(guard_calls) == 3
    assert [call.ok for call in guard_calls].count(False) == 1
    assert [call.ok for call in guard_calls].count(True) == 2
    assert len(response["dashboard"]["kpis"]) == 2


def test_merged_dashboard_preserves_existing_keys(monkeypatch):
    plans = iter([
        _metric_plan(
            "select rd.refund_rate as refund_rate from gold.refund_daily rd "
            "where rd.tenant_id = :tenant_id",
            metric="refund_rate",
            title="Refund Rate",
        ),
        _metric_plan(
            "select sum(ds.net_sales) as net_sales from gold.daily_sales ds "
            "where ds.tenant_id = :tenant_id",
            metric="net_sales",
            title="Net Sales",
        ),
    ])
    analyst = _new_multi_query_analyst(
        monkeypatch,
        lambda prompt: next(plans),
        lambda prompt: (
            {
                "answer": "Refund metric.",
                "dashboard": {
                    "title": "Refunds",
                    "kpis": [{"label": "Refunds", "column": "refund_rate", "aggregation": "value"}],
                    "charts": [],
                    "filters": [],
                },
            }
            if "refund_daily" in prompt
            else {
                "answer": "Sales metric.",
                "dashboard": {
                    "title": "Sales",
                    "kpis": [{"label": "Sales", "column": "net_sales", "aggregation": "value"}],
                    "charts": [],
                    "filters": [],
                },
            }
        ),
        result_rows=lambda sql: (
            [{"refund_rate": 0.1}]
            if "refund_daily" in sql
            else [{"net_sales": 400}]
        ),
    )

    response = analyst.ask("tenant-1", "Show revenue and refund percentage")

    assert set(response["dashboard"]) == {
        "title",
        "kpis",
        "charts",
        "filters",
        "no_data",
    }
    assert len(response["dashboard"]["kpis"]) == 2
    assert {"answer", "dashboard", "rows", "sql"} <= set(response)


def test_original_sales_overview_returns_kpis_and_category_unavailable_notice(monkeypatch):
    analyst = _new_multi_query_analyst(
        monkeypatch,
        lambda prompt: _metric_plan(_VALID_REAL_KPI_SQL),
        _multi_kpi_final,
    )

    response = analyst.ask("tenant-1", _ORIGINAL_SALES_QUESTION)

    assert {kpi["column"] for kpi in response["dashboard"]["kpis"]} == {
        "net_sales",
        "orders",
        "average_order_value",
    }
    assert "category breakdown is not available yet" in response["answer"].lower()
    assert len(response["rows"]) == 1
    assert len(response["sql"]) > 0
    assert "gold.product_daily" not in response["sql"]


def test_one_row_kpi_is_displayed_as_value_not_reaggregated():
    rows = [{"total_revenue": 6230.83}]
    dashboard = {
        "title": "Revenue",
        "kpis": [{"label": "Total revenue", "column": "total_revenue", "aggregation": "sum"}],
        "charts": [],
        "filters": [],
    }

    result = _normalise_dashboard(dashboard, rows)

    assert result["kpis"][0]["aggregation"] == "value"
    assert result["kpis"][0]["value"] == 6230.83
    assert result["kpis"][0]["column"] == "total_revenue"
    assert result["kpis"][0]["source_column"] == "total_revenue"
    assert result["kpis"][0]["format"] == "currency"


def test_dashboard_columns_not_in_sql_result_are_removed():
    rows = [{"metric_date": "2026-09-29", "net_sales": 100}]
    dashboard = {
        "title": "Sales",
        "kpis": [
            {"label": "Sales", "column": "net_sales", "aggregation": "sum"},
            {"label": "Fake", "column": "not_in_result", "aggregation": "sum"},
        ],
        "charts": [
            {"type": "line", "title": "Sales", "x": "metric_date", "y": "not_in_result", "series": None}
        ],
        "filters": [{"field": "metric_date", "type": "date_range"}],
    }

    result = _normalise_dashboard(dashboard, rows)

    assert len(result["kpis"]) == 1
    assert result["kpis"][0]["value"] == 100
    assert result["kpis"][0]["column"] == "net_sales"
    assert all(chart.get("y") != "not_in_result" for chart in result["charts"])
    for chart in result["charts"]:
        if chart["type"] in {"line", "bar", "area"}:
            assert chart["x"] == "metric_date"
            assert chart["y"] == "net_sales"
    assert result["filters"] == [{"field": "metric_date", "type": "date_range"}]


def test_dashboard_normalisation_preserves_multi_row_chart_grain():
    rows = [
        {"metric_date": "2026-09-28", "net_sales": 100},
        {"metric_date": "2026-09-29", "net_sales": 150},
    ]
    dashboard = {
        "title": "Daily sales",
        "kpis": [{"label": "Sales", "column": "net_sales", "aggregation": "sum"}],
        "charts": [{"type": "line", "title": "Sales by day", "x": "metric_date", "y": "net_sales", "series": None}],
        "filters": [{"field": "metric_date", "type": "date_range"}],
    }

    result = _normalise_dashboard(dashboard, rows)

    assert result["kpis"] == []
    assert result["charts"][0]["type"] == "line"
    assert result["charts"][0]["x"] == "metric_date"
    assert result["charts"][0]["y"] == "net_sales"
    assert result["charts"][0]["data"] == rows
    assert result["filters"] == [{"field": "metric_date", "type": "date_range"}]


def test_dashboard_normalisation_coerces_unsupported_chart_type():
    rows = [
        {"category": "A", "net_sales": 100},
        {"category": "B", "net_sales": 80},
    ]
    dashboard = {
        "title": "Sales",
        "kpis": [],
        "charts": [{"type": "pie", "title": "Share", "x": "category", "y": "net_sales", "series": None}],
        "filters": [],
    }

    result = _normalise_dashboard(dashboard, rows)

    assert result["charts"][0]["type"] == "bar"
    assert result["charts"][0]["data"] == rows


def test_ai_analyst_ask_separates_public_and_debug_response(monkeypatch):
    from commerce_connector.platform.ai_analyst import AIAnalyst
    from commerce_connector.platform.db import PostgresGateway
    from commerce_connector.platform.llm import LLMClient

    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"

    analyst = AIAnalyst(fake_db, fake_llm)

    # Mock dependencies
    monkeypatch.setattr(analyst.retriever, "retrieve", lambda *a, **k: [
        {"chunk_id": "c-1", "title": "Sales Doc", "similarity": 0.95, "content": "Revenue docs"}
    ])
    monkeypatch.setattr(fake_db, "semantic_catalog_snapshot", lambda *a: {
        "metrics": [{
            "code": "revenue",
            "name": "Revenue",
            "description": "Total sales",
            "sql_expression": "SUM(net_sales)",
            "aggregation": "sum",
            "data_type": "currency",
            "default_time_column": "metric_date",
            "allowed_dimensions": ["date"],
            "preferred_source_schema": "gold",
            "preferred_source_table": "daily_sales",
        }],
        "columns": [{
            "table_schema": "gold",
            "table_name": "daily_sales",
            "column_name": "net_sales",
            "data_type": "numeric",
        }],
        "permissions": [{
            "schema_name": "gold",
            "table_name": "daily_sales",
            "max_rows": 500,
        }],
    })
    monkeypatch.setattr(fake_db, "create_query_run", lambda *a, **k: {"id": "run-123"})
    monkeypatch.setattr(fake_db, "save_generated_query", lambda *a, **k: {"id": "gq-123"})
    monkeypatch.setattr(fake_db, "save_dashboard_spec", lambda *a, **k: {"id": "dash-123"})
    monkeypatch.setattr(fake_db, "update_query_run", lambda *a, **k: None)
    monkeypatch.setattr(fake_db, "execute_readonly_query", lambda sql, tid: [{"revenue": 50000.0}])

    call_count = 0
    def fake_generate_json(prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "route": "metric",
                "intent": {
                    "metric": "revenue",
                    "dimensions": [],
                    "date_range": "all",
                    "comparison": "none",
                    "filters": [],
                },
                "sql": "SELECT SUM(net_sales) AS revenue FROM gold.daily_sales WHERE daily_sales.tenant_id = :tenant_id",
                "title": "Total Revenue",
            }
        return {
            "answer": "Total revenue is $50,000.",
            "dashboard": {
                "title": "Revenue Overview",
                "kpis": [{"label": "Revenue", "column": "revenue", "aggregation": "value"}],
                "charts": [],
                "filters": [],
            },
        }

    monkeypatch.setattr(fake_llm, "generate_json", fake_generate_json)

    # 1. Ask without include_debug (standard user-facing response)
    res_public = analyst.ask("tenant-1", "What was total revenue?", include_debug=False)

    assert "conversation_id" in res_public
    assert "query_run_id" in res_public
    assert res_public["query_run_id"] == "run-123"
    assert res_public["dashboard_id"] == "dash-123"
    assert res_public["answer"] == "Total revenue is $50,000."
    assert "dashboard" in res_public
    assert res_public["dashboard"]["kpis"][0]["value"] == 50000.0
    assert "debug" not in res_public

    # 2. Ask with include_debug=True
    call_count = 0
    res_debug = analyst.ask("tenant-1", "What was total revenue?", include_debug=True)

    assert "debug" in res_debug
    assert "sql" in res_debug["debug"]
    assert "execution_ms" in res_debug["debug"]
    assert "result_shape" in res_debug["debug"]
    assert res_debug["debug"]["result_shape"] == "one_row_aggregate"
    assert res_debug["debug"]["already_aggregated"] is True
    assert res_debug["debug"]["retrieved_context_ids"] == ["c-1"]


def test_empty_subquery_with_data_coverage(monkeypatch):
    from datetime import date

    planner = lambda prompt: _metric_plan(_VALID_REAL_KPI_SQL, metric="net_sales")
    llm_called = False
    def final(prompt):
        nonlocal llm_called
        llm_called = True
        return {}

    analyst = _new_multi_query_analyst(
        monkeypatch,
        planner,
        final,
        result_rows=[],
    )
    monkeypatch.setattr(
        analyst.db,
        "get_data_coverage",
        lambda tid: {
            "first_date": date(2026, 1, 1),
            "last_date": date(2026, 3, 15),
            "days_with_data": 74,
        },
    )

    res = analyst.ask("tenant-1", "What was revenue for April 2026?")

    assert llm_called is False
    assert "1 January 2026" in res["answer"]
    assert "15 March 2026" in res["answer"]
    assert res["dashboard"]["no_data"] is True
    assert res["dashboard"]["data_range"] == {
        "first_date": "2026-01-01",
        "last_date": "2026-03-15",
    }


def test_empty_subquery_without_data_coverage(monkeypatch):
    planner = lambda prompt: _metric_plan(_VALID_REAL_KPI_SQL, metric="net_sales")
    llm_called = False
    def final(prompt):
        nonlocal llm_called
        llm_called = True
        return {}

    analyst = _new_multi_query_analyst(
        monkeypatch,
        planner,
        final,
        result_rows=[],
    )
    monkeypatch.setattr(
        analyst.db,
        "get_data_coverage",
        lambda tid: {
            "first_date": None,
            "last_date": None,
            "days_with_data": 0,
        },
    )

    res = analyst.ask("tenant-1", "What was revenue for April 2026?")

    assert llm_called is False
    assert "No data has been synced or uploaded for this workspace yet." in res["answer"]
    assert res["dashboard"]["no_data"] is True
    assert res["dashboard"]["data_range"] == {
        "first_date": None,
        "last_date": None,
    }


def test_empty_subquery_returns_empty_rows_and_no_data(monkeypatch):
    planner = lambda prompt: _metric_plan(_VALID_REAL_KPI_SQL, metric="net_sales")
    llm_called = False
    def final(prompt):
        nonlocal llm_called
        llm_called = True
        return {}

    # 1. All-null single row -> shape is "empty"
    all_null_analyst = _new_multi_query_analyst(
        monkeypatch,
        planner,
        final,
        result_rows=[{"net_sales": None, "orders": None, "average_order_value": None}],
    )
    res_empty = all_null_analyst.ask("tenant-1", "What was revenue for April 2026?", include_debug=True)

    assert res_empty["rows"] == []
    assert res_empty["dashboard"]["no_data"] is True
    assert res_empty["debug"]["row_count"] == 0

    # 2. Normal non-empty single row -> returns rows and no_data is False
    normal_analyst = _new_multi_query_analyst(
        monkeypatch,
        planner,
        _multi_kpi_final,
        result_rows=[{"net_sales": 500, "orders": 10, "average_order_value": 50}],
    )
    res_normal = normal_analyst.ask("tenant-1", "What was revenue for April 2026?", include_debug=True)

    assert len(res_normal["rows"]) == 1
    assert res_normal["rows"][0]["net_sales"] == 500
    assert res_normal["dashboard"]["no_data"] is False
    assert res_normal["debug"]["row_count"] == 1


