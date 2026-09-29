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

    assert result["kpis"] == [
        {"label": "Total revenue", "column": "total_revenue", "aggregation": "value"}
    ]


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
    assert result["charts"][0]["y"] is None
    assert result["filters"] == [{"field": "metric_date", "type": "date_range"}]

def test_dashboard_normalisation_preserves_valid_multi_row_aggregation():
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

    assert result["kpis"][0]["aggregation"] == "sum"
    assert result["charts"][0]["x"] == "metric_date"
    assert result["charts"][0]["y"] == "net_sales"
    assert result["filters"] == [{"field": "metric_date", "type": "date_range"}]
