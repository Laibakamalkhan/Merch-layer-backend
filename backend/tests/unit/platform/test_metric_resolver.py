from __future__ import annotations

import pytest

from commerce_connector.platform.analytics.metric_resolver import (
    compact_semantic_context,
    enforce_verified_metric_sql,
    lookup_metric,
    resolve_metrics,
)


REVENUE = {
    "code": "revenue",
    "name": "Revenue",
    "description": "Total sales value",
    "sql_expression": "SUM(net_sales)",
    "aggregation": "sum",
    "data_type": "currency",
    "default_time_column": "metric_date",
    "allowed_dimensions": ["date", "product", "category"],
    "preferred_source_schema": "gold",
    "preferred_source_table": "daily_sales",
    "synonyms": ["sales", "net sales"],
}

ORDERS = {
    "code": "orders_count",
    "name": "Orders",
    "description": "Number of orders",
    "sql_expression": "COUNT(*)",
    "aggregation": "count",
    "data_type": "integer",
    "default_time_column": "metric_date",
    "allowed_dimensions": ["date"],
    "preferred_source_schema": "gold",
    "preferred_source_table": "daily_sales",
    "synonyms": ["orders"],
}

SNAPSHOT = {
    "metrics": [REVENUE, ORDERS],
    "columns": [
        {
            "table_schema": "gold",
            "table_name": "daily_sales",
            "column_name": "net_sales",
            "data_type": "numeric",
        },
        {
            "table_schema": "gold",
            "table_name": "daily_sales",
            "column_name": "metric_date",
            "data_type": "date",
        },
        {
            "table_schema": "silver",
            "table_name": "orders",
            "column_name": "email",
            "data_type": "text",
        },
    ],
    "permissions": [
        {
            "schema_name": "gold",
            "table_name": "daily_sales",
            "max_rows": 5000,
        }
    ],
    "connections": [
        {
            "name": "Main store",
            "platform_code": "shopify",
            "base_url": "https://secret.example/admin",
        }
    ],
}


def test_verified_metric_lookup_by_code_and_synonym():
    by_code = lookup_metric(SNAPSHOT, "revenue")
    assert by_code is not None
    assert by_code.sql_expression == "SUM(net_sales)"
    assert by_code.aggregation == "sum"
    assert by_code.data_type == "currency"
    assert by_code.default_time_column == "metric_date"
    assert "product" in by_code.allowed_dimensions

    by_synonym = lookup_metric(SNAPSHOT, "net sales")
    assert by_synonym is not None
    assert by_synonym.code == "revenue"


def test_resolve_metrics_binds_verified_definition_from_question():
    resolution = resolve_metrics("What was revenue last month?", SNAPSHOT)
    assert resolution.ok is True
    assert [m.code for m in resolution.matched] == ["revenue"]
    assert resolution.matched[0].sql_expression == "SUM(net_sales)"


def test_unsupported_profit_is_rejected_when_not_in_catalog():
    resolution = resolve_metrics("What is my profit margin?", SNAPSHOT)
    assert resolution.ok is False
    assert resolution.unsupported_code in {"profit_margin", "margin", "profit"}
    assert "cost" in (resolution.message or "").lower() or "catalog" in (resolution.message or "").lower()


def test_dataset_unavailable_metric_is_rejected():
    profile = {"unavailable_metrics": ["revenue", "aov"]}
    resolution = resolve_metrics(
        "Show revenue",
        SNAPSHOT,
        dataset_profile=profile,
    )
    assert resolution.ok is False
    assert resolution.unsupported_code == "revenue"


def test_invented_sql_expression_is_rejected_when_definition_exists():
    resolution = resolve_metrics("Show revenue", SNAPSHOT)
    with pytest.raises(RuntimeError, match="Invented metric expression"):
        enforce_verified_metric_sql(
            "select SUM(magic) as revenue from gold.daily_sales where tenant_id = :tenant_id",
            snapshot=SNAPSHOT,
            resolution=resolution,
            intent={"metric": "revenue"},
        )


def test_verified_sql_expression_is_accepted():
    resolution = resolve_metrics("Show revenue", SNAPSHOT)
    enforce_verified_metric_sql(
        "select metric_date, SUM(net_sales) as revenue from gold.daily_sales "
        "where tenant_id = :tenant_id group by 1",
        snapshot=SNAPSHOT,
        resolution=resolution,
        intent={"metric": "revenue"},
    )


def test_preaggregated_gold_column_is_accepted_without_reinventing_sum():
    resolution = resolve_metrics("Show revenue", SNAPSHOT)
    enforce_verified_metric_sql(
        "select metric_date, net_sales from gold.daily_sales where tenant_id = :tenant_id",
        snapshot=SNAPSHOT,
        resolution=resolution,
        intent={"metric": "revenue"},
    )


def test_exploratory_question_without_named_kpi_is_not_blocked():
    resolution = resolve_metrics("List products by title", SNAPSHOT)
    assert resolution.ok is True
    assert resolution.matched == []


def test_compact_semantic_context_includes_definitions_not_secrets():
    resolution = resolve_metrics("Show revenue", SNAPSHOT)
    text = compact_semantic_context(SNAPSHOT, resolution)
    assert "sql_expression: SUM(net_sales)" in text
    assert "code=revenue" in text
    assert "REQUIRED for this question" in text
    assert "gold.daily_sales.net_sales" in text
    assert "silver.orders.email" not in text
    assert "secret.example" not in text
    assert "Never invent a metric SQL expression" in text


def test_planner_intent_cannot_switch_to_unsupported_metric():
    resolution = resolve_metrics("How are sales?", SNAPSHOT)
    post = resolve_metrics(
        "How are sales?",
        SNAPSHOT,
        intent={"metric": "profit"},
    )
    assert resolution.ok is True
    assert post.ok is False
    assert post.unsupported_code == "profit"
