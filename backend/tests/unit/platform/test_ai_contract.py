from __future__ import annotations

from commerce_connector.platform.ai_analyst import _normalise_dashboard


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

