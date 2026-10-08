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
