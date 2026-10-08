from __future__ import annotations

from commerce_connector.platform.analytics.dashboard_builder import (
    build_verified_dashboard,
    copy_metric_value,
)
from commerce_connector.platform.analytics.metric_resolver import MetricDefinition


REVENUE_METRIC = MetricDefinition(
    code="revenue",
    name="Revenue",
    sql_expression="SUM(net_sales)",
    aggregation="sum",
    data_type="currency",
    default_time_column="metric_date",
    allowed_dimensions=("date",),
)


def test_one_row_kpi_value_is_copied_from_database_cell():
    dashboard = build_verified_dashboard(
        [{"total_revenue": 6230.83}],
        title="Revenue",
        llm_dashboard={
            "title": "Revenue",
            "kpis": [{"label": "Total revenue", "column": "total_revenue", "aggregation": "sum", "value": 999}],
            "charts": [],
            "filters": [],
        },
        metrics=[REVENUE_METRIC],
    )

    assert dashboard["no_data"] is False
    assert dashboard["kpis"] == [
        {
            "id": "total_revenue",
            "label": "Total revenue",
            "value": 6230.83,
            "format": "currency",
            "source_column": "total_revenue",
            "column": "total_revenue",
            "aggregation": "value",
        }
    ]


def test_unknown_kpi_column_is_dropped():
    dashboard = build_verified_dashboard(
        [{"net_sales": 100}],
        llm_dashboard={
            "kpis": [
                {"label": "Sales", "column": "net_sales", "aggregation": "value"},
                {"label": "Fake", "column": "not_in_result", "aggregation": "sum"},
            ],
            "charts": [],
        },
    )
    assert [kpi["column"] for kpi in dashboard["kpis"]] == ["net_sales"]


def test_chart_data_is_copied_at_database_grain():
    rows = [
        {"metric_date": "2026-09-28", "net_sales": 100},
        {"metric_date": "2026-09-29", "net_sales": 150},
    ]
    dashboard = build_verified_dashboard(
        rows,
        llm_dashboard={
            "title": "Daily sales",
            "kpis": [{"label": "Sales", "column": "net_sales", "aggregation": "sum"}],
            "charts": [
                {"type": "line", "title": "Sales by day", "x": "metric_date", "y": "net_sales", "series": None}
            ],
        },
    )

    assert dashboard["kpis"] == []
    assert dashboard["charts"][0]["type"] == "line"
    assert dashboard["charts"][0]["x"] == "metric_date"
    assert dashboard["charts"][0]["y"] == "net_sales"
    assert dashboard["charts"][0]["x_field"] == "metric_date"
    assert dashboard["charts"][0]["y_field"] == "net_sales"
    assert dashboard["charts"][0]["data"] == rows


def test_copy_metric_value_does_not_sum_a_series():
    rows = [
        {"metric_date": "2026-09-28", "net_sales": 100},
        {"metric_date": "2026-09-29", "net_sales": 150},
    ]
    value, ok = copy_metric_value(rows, "net_sales")
    assert ok is False
    assert value is None


def test_repeated_window_total_is_copied_not_recalculated():
    rows = [
        {"month": "2026-01", "revenue": 20, "total_revenue": 45},
        {"month": "2026-02", "revenue": 25, "total_revenue": 45},
    ]
    value, ok = copy_metric_value(rows, "total_revenue")
    assert ok is True
    assert value == 45

    dashboard = build_verified_dashboard(
        rows,
        llm_dashboard={
            "kpis": [{"label": "Revenue", "column": "total_revenue", "aggregation": "sum"}],
            "charts": [{"type": "line", "title": "Trend", "x": "month", "y": "revenue", "series": None}],
        },
    )
    assert dashboard["kpis"][0]["value"] == 45
    assert dashboard["kpis"][0]["aggregation"] == "value"
    assert dashboard["charts"][0]["data"] == [
        {"month": "2026-01", "revenue": 20},
        {"month": "2026-02", "revenue": 25},
    ]


def test_missing_chart_fields_drop_the_widget():
    dashboard = build_verified_dashboard(
        [{"metric_date": "2026-09-29", "net_sales": 100}],
        llm_dashboard={
            "charts": [
                {"type": "line", "title": "Sales", "x": "metric_date", "y": "not_in_result", "series": None}
            ],
        },
    )
    assert all(chart.get("y") != "not_in_result" for chart in dashboard["charts"])
    assert all(
        chart.get("x") in {"metric_date", None} and chart.get("y") in {"net_sales", None}
        for chart in dashboard["charts"]
    )
    for chart in dashboard["charts"]:
        if chart["type"] in {"line", "bar", "area"}:
            assert chart["x"] == "metric_date"
            assert chart["y"] == "net_sales"
            assert chart["data"][0]["net_sales"] == 100


def test_unsupported_chart_type_falls_back():
    dashboard = build_verified_dashboard(
        [
            {"category": "A", "net_sales": 100},
            {"category": "B", "net_sales": 80},
        ],
        llm_dashboard={
            "charts": [{"type": "pie", "title": "Share", "x": "category", "y": "net_sales", "series": None}],
        },
    )
    assert dashboard["charts"][0]["type"] == "bar"
    assert dashboard["charts"][0]["data"] == [
        {"category": "A", "net_sales": 100},
        {"category": "B", "net_sales": 80},
    ]


def test_empty_result_is_valid_no_data_state():
    dashboard = build_verified_dashboard(
        [],
        title="Sales Overview",
        llm_dashboard={
            "title": "Sales Overview",
            "kpis": [{"label": "Sales", "column": "net_sales", "aggregation": "sum"}],
            "charts": [{"type": "bar", "title": "Sales", "x": "category", "y": "net_sales", "series": None}],
        },
    )
    assert dashboard == {
        "title": "Sales Overview",
        "kpis": [],
        "charts": [],
        "filters": [],
        "no_data": True,
    }
