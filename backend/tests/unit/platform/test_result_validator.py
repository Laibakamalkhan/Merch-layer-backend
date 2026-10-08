from __future__ import annotations

from decimal import Decimal

from commerce_connector.platform.analytics.metric_resolver import MetricDefinition
from commerce_connector.platform.analytics.result_validator import validate_query_result


REVENUE = MetricDefinition(
    code="revenue",
    name="Revenue",
    sql_expression="SUM(net_sales)",
    aggregation="sum",
    data_type="currency",
    synonyms=("sales",),
)


def test_one_row_aggregate_result_is_recognized_and_not_recalculated():
    verified = validate_query_result(
        [{"total_revenue": Decimal("6230.83")}],
        expected_metrics=[REVENUE],
        max_rows=5000,
    )

    assert verified.ok is True
    assert verified.shape == "one_row_aggregate"
    assert verified.already_aggregated is True
    assert verified.row_count == 1
    assert verified.rows == ({"total_revenue": 6230.83},)
    assert verified.metric_columns == ("total_revenue",)
    assert verified.dimension_columns == ()


def test_multi_row_grouped_result_preserves_database_values():
    rows = [
        {"month": "2026-01-01", "revenue": Decimal("100.50")},
        {"month": "2026-02-01", "revenue": Decimal("150.25")},
    ]
    verified = validate_query_result(
        rows,
        expected_metrics=[REVENUE],
        expected_dimensions=["month"],
        max_rows=5000,
    )

    assert verified.ok is True
    assert verified.shape == "grouped"
    assert verified.already_aggregated is True
    assert verified.row_count == 2
    assert verified.rows == (
        {"month": "2026-01-01", "revenue": 100.5},
        {"month": "2026-02-01", "revenue": 150.25},
    )
    assert verified.metric_columns == ("revenue",)
    assert verified.dimension_columns == ("month",)
    # PostgreSQL already returned grain-level values; Python must not total them.
    assert sum(row["revenue"] for row in verified.rows) not in verified.rows[0].values()


def test_missing_metric_column_fails_without_fabricating_a_value():
    verified = validate_query_result(
        [{"month": "2026-01-01"}],
        expected_metrics=[REVENUE],
        expected_dimensions=["month"],
        max_rows=5000,
    )

    assert verified.ok is False
    assert verified.rows == ()
    assert verified.message is not None
    assert "revenue" in verified.message.lower()
    assert "no replacement" in verified.message.lower()


def test_empty_result_is_handled_explicitly():
    verified = validate_query_result(
        [],
        expected_metrics=[REVENUE],
        expected_dimensions=["month"],
        max_rows=5000,
    )

    assert verified.ok is True
    assert verified.shape == "empty"
    assert verified.row_count == 0
    assert verified.rows == ()
    assert verified.already_aggregated is False
    assert verified.message == "Query returned no matching rows."
    assert 0 not in (verified.rows or ())


def test_invalid_numeric_value_is_rejected():
    verified = validate_query_result(
        [{"revenue": float("inf")}],
        expected_metrics=[REVENUE],
        max_rows=5000,
    )

    assert verified.ok is False
    assert verified.rows == ()
    assert verified.message is not None
    assert "finite" in verified.message.lower()
    assert "no replacement" in verified.message.lower()


def test_oversized_result_is_rejected():
    rows = [{"category": f"c{i}", "revenue": i} for i in range(4)]
    verified = validate_query_result(
        rows,
        expected_metrics=[REVENUE],
        expected_dimensions=["category"],
        max_rows=3,
    )

    assert verified.ok is False
    assert verified.rows == ()
    assert verified.message is not None
    assert "exceeds the allowed maximum of 3" in verified.message
    assert "no replacement" in verified.message.lower()
