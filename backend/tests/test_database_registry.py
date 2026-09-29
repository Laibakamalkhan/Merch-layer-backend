from pathlib import Path

from commerce_connector.api.app import create_app
from commerce_connector.api.table_registry import TABLE_SPECS


EXPECTED_TABLES = {
    "iam.profiles", "iam.tenants", "iam.tenant_members",
    "control.platforms", "control.platform_versions", "control.platform_resources",
    "control.connections", "control.connection_credentials", "control.connection_resources", "control.sync_schedules",
    "ingestion.sync_jobs", "ingestion.sync_job_connections", "ingestion.sync_runs", "ingestion.pipeline_stage_runs",
    "ingestion.checkpoints", "ingestion.webhook_events", "ingestion.extraction_pages",
    "bronze.raw_objects", "bronze.records", "bronze.schema_snapshots",
    "silver.customers", "silver.customer_addresses", "silver.products", "silver.product_variants",
    "silver.categories", "silver.product_categories", "silver.locations", "silver.inventory_levels",
    "silver.orders", "silver.order_items", "silver.order_addresses", "silver.payments", "silver.refunds",
    "silver.refund_items", "silver.fulfillments", "silver.fulfillment_items", "silver.returns", "silver.return_items",
    "gold.daily_sales", "gold.product_daily", "gold.customer_metrics", "gold.inventory_snapshot_daily",
    "gold.refund_daily", "gold.fulfillment_daily", "gold.channel_daily",
    "ai.metric_definitions", "ai.semantic_columns", "ai.query_permissions", "ai.documents", "ai.document_chunks",
    "ai.conversations", "ai.messages", "ai.query_runs", "ai.generated_queries", "ai.dashboard_specs", "ai.embedding_jobs",
    "ops.errors", "ops.job_events", "ops.audit_logs", "ops.data_quality_runs", "ops.data_quality_results", "ops.usage_daily",
}


def test_registry_covers_all_final_database_tables():
    assert len(TABLE_SPECS) == 62
    assert {spec.key for spec in TABLE_SPECS} == EXPECTED_TABLES


def test_every_table_has_concrete_openapi_list_and_count_route():
    paths = create_app().openapi()["paths"]
    for spec in TABLE_SPECS:
        base = f"/api/v1/database/{spec.schema}/{spec.table}"
        assert base in paths
        assert f"{base}/_count" in paths
        if spec.has_id:
            assert f"{base}/{{record_id}}" in paths


def test_streamlit_is_not_part_of_backend_package():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "streamlit_app.py").exists()
    deps = (root / "pyproject.toml").read_text().lower()
    assert "streamlit" not in deps
    assert "pandas" not in deps
