from __future__ import annotations

from commerce_connector.platform.analytics.visualization import (
    coerce_chart_type,
    recommend_visualizations,
)


def test_one_aggregated_value_recommends_kpi_with_table_fallback():
    rec = recommend_visualizations([{"total_revenue": 6230.83}])
    assert rec.show_kpis is True
    assert rec.preferred_chart_type == "table"
    assert rec.allowed_chart_types == ("table",)
    assert rec.candidates[0].role == "kpi"
    assert coerce_chart_type("line", rec) == "table"
    assert coerce_chart_type("pie", rec) == "table"


def test_time_plus_metric_recommends_line_with_area_fallback():
    rec = recommend_visualizations(
        [
            {"metric_date": "2026-01-01", "revenue": 20000},
            {"metric_date": "2026-02-01", "revenue": 25000},
        ]
    )
    assert rec.preferred_chart_type == "line"
    assert rec.allowed_chart_types == ("line", "area", "table")
    assert rec.candidates[0].fallback == "area"
    assert rec.candidates[0].x_field == "metric_date"
    assert rec.candidates[0].y_field == "revenue"
    assert coerce_chart_type("area", rec) == "area"
    assert coerce_chart_type("bar", rec) == "line"
    assert coerce_chart_type("scatter", rec) == "line"


def test_category_plus_metric_recommends_bar_with_table_fallback():
    rec = recommend_visualizations(
        [
            {"category": "A", "revenue": 100},
            {"category": "B", "revenue": 80},
            {"category": "C", "revenue": 40},
        ]
    )
    assert rec.preferred_chart_type == "bar"
    assert rec.allowed_chart_types == ("bar", "table")
    assert rec.candidates[0].fallback == "table"
    assert coerce_chart_type("bar", rec) == "bar"
    assert coerce_chart_type("pie", rec) == "bar"


def test_high_cardinality_categories_fall_back_to_table():
    rows = [{"category": f"c{i}", "revenue": i} for i in range(30)]
    rec = recommend_visualizations(rows)
    assert rec.preferred_chart_type == "table"
    assert rec.allowed_chart_types == ("table",)


def test_top_n_categories_use_table_because_horizontal_bar_is_unsupported():
    rec = recommend_visualizations(
        [
            {"product": "Shirt", "revenue": 500},
            {"product": "Pants", "revenue": 300},
            {"product": "Hat", "revenue": 100},
        ],
        intent={"comparison": "top 5 products", "metric": "revenue"},
    )
    assert rec.intent == "top_n"
    assert rec.preferred_chart_type == "table"
    assert "horizontal_bar" not in rec.allowed_chart_types
    assert coerce_chart_type("horizontal_bar", rec) == "table"


def test_detailed_records_recommend_table():
    rec = recommend_visualizations(
        [
            {"order_id": "1001", "email": "a@example.com", "status": "paid"},
            {"order_id": "1002", "email": "b@example.com", "status": "paid"},
        ]
    )
    assert rec.preferred_chart_type == "table"
    assert rec.allowed_chart_types == ("table",)
    assert rec.show_kpis is False


def test_multiple_numeric_variables_do_not_emit_scatter():
    rec = recommend_visualizations(
        [
            {"units": 10, "revenue": 100},
            {"units": 12, "revenue": 140},
        ]
    )
    assert rec.preferred_chart_type == "table"
    assert "scatter" not in rec.allowed_chart_types
    assert coerce_chart_type("scatter", rec) == "table"


def test_geographic_dimension_does_not_emit_map():
    rec = recommend_visualizations(
        [
            {"city": "Lahore", "revenue": 100},
            {"city": "Karachi", "revenue": 180},
        ]
    )
    assert rec.preferred_chart_type == "bar"
    assert "map" not in rec.allowed_chart_types
    assert coerce_chart_type("map", rec) == "bar"


def test_composition_intent_rejects_pie_in_favor_of_bar():
    rec = recommend_visualizations(
        [
            {"channel": "online", "revenue": 70},
            {"channel": "retail", "revenue": 30},
        ],
        intent={"comparison": "share / composition"},
    )
    assert rec.intent == "composition"
    assert rec.preferred_chart_type == "bar"
    assert coerce_chart_type("pie", rec) == "bar"
    assert coerce_chart_type("donut", rec) == "bar"


def test_empty_result_has_no_chart_candidates():
    rec = recommend_visualizations([])
    assert rec.shape == "empty"
    assert rec.candidates == ()
    assert rec.show_kpis is False
    assert rec.preferred_chart_type == "table"
    assert coerce_chart_type("line", rec) == "table"
