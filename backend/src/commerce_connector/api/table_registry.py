from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Scope = Literal["global", "tenant", "tenant_or_global", "user"]


@dataclass(frozen=True, slots=True)
class TableSpec:
    schema: str
    table: str
    scope: Scope = "tenant"
    tenant_column: str = "tenant_id"
    has_id: bool = True
    hidden_columns: tuple[str, ...] = ()
    large_columns: tuple[str, ...] = ()
    write_mode: str = "pipeline"
    # Parent-table ownership: when set, all reads add an EXISTS subquery
    # joining through the parent row to enforce user_id ownership.
    parent_schema: str | None = None
    parent_table: str | None = None
    parent_fk: str | None = None
    parent_user_column: str = "user_id"

    @property
    def key(self) -> str:
        return f"{self.schema}.{self.table}"


# Every application table in the finalized Supabase SQL.  These are the only
# tables exposed by the generic frontend data API.  System schemas, Vault,
# pgmq internals, auth.users and storage internals are intentionally excluded.
TABLE_SPECS: tuple[TableSpec, ...] = (
    # IAM
    TableSpec("iam", "profiles", scope="user", write_mode="auth"),
    TableSpec("iam", "tenants", scope="tenant", tenant_column="id", write_mode="control"),
    TableSpec("iam", "tenant_members", scope="tenant", has_id=False, write_mode="control"),

    # Control plane
    TableSpec("control", "platforms", scope="global", write_mode="catalog"),
    TableSpec("control", "platform_versions", scope="global", write_mode="catalog"),
    TableSpec("control", "platform_resources", scope="global", write_mode="catalog"),
    TableSpec("control", "connections", scope="tenant", write_mode="control"),
    TableSpec(
        "control",
        "connection_credentials",
        scope="tenant",
        hidden_columns=("vault_secret_id",),
        write_mode="vault_only",
    ),
    TableSpec("control", "connection_resources", scope="tenant", write_mode="control"),
    TableSpec("control", "sync_schedules", scope="tenant", write_mode="control"),

    # Ingestion
    TableSpec("ingestion", "sync_jobs"),
    TableSpec("ingestion", "sync_job_connections"),
    TableSpec("ingestion", "sync_runs"),
    TableSpec("ingestion", "pipeline_stage_runs"),
    TableSpec("ingestion", "checkpoints"),
    TableSpec("ingestion", "webhook_events", large_columns=("headers", "payload")),
    TableSpec("ingestion", "extraction_pages", large_columns=("response_metadata",)),
    TableSpec("ingestion", "uploaded_datasets", large_columns=("profile_summary", "mapping_config", "quality_summary")),

    # Bronze
    TableSpec("bronze", "raw_objects", large_columns=("source_metadata",)),
    TableSpec("bronze", "records", large_columns=("payload",)),
    TableSpec("bronze", "schema_snapshots", large_columns=("inferred_schema", "sample_record_ids")),

    # Silver
    TableSpec("silver", "customers", large_columns=("attributes",)),
    TableSpec("silver", "customer_addresses"),
    TableSpec("silver", "products", large_columns=("description", "attributes")),
    TableSpec("silver", "product_variants", large_columns=("option_values", "attributes")),
    TableSpec("silver", "categories", large_columns=("attributes",)),
    TableSpec("silver", "product_categories", has_id=False),
    TableSpec("silver", "locations", large_columns=("address",)),
    TableSpec("silver", "inventory_levels"),
    TableSpec("silver", "orders", large_columns=("attributes",)),
    TableSpec("silver", "order_items", large_columns=("attributes",)),
    TableSpec("silver", "order_addresses"),
    TableSpec("silver", "payments", large_columns=("attributes",)),
    TableSpec("silver", "refunds", large_columns=("attributes",)),
    TableSpec("silver", "refund_items"),
    TableSpec("silver", "fulfillments", large_columns=("attributes",)),
    TableSpec("silver", "fulfillment_items"),
    TableSpec("silver", "returns", large_columns=("attributes",)),
    TableSpec("silver", "return_items"),

    # Gold
    TableSpec("gold", "daily_sales"),
    TableSpec("gold", "product_daily"),
    TableSpec("gold", "customer_metrics"),
    TableSpec("gold", "inventory_snapshot_daily"),
    TableSpec("gold", "refund_daily"),
    TableSpec("gold", "fulfillment_daily"),
    TableSpec("gold", "channel_daily"),

    # AI / semantic / RAG
    TableSpec("ai", "metric_definitions", scope="tenant_or_global", write_mode="semantic"),
    TableSpec("ai", "semantic_columns", scope="tenant_or_global", write_mode="semantic"),
    TableSpec("ai", "query_permissions", scope="tenant_or_global", write_mode="semantic"),
    TableSpec("ai", "documents", scope="tenant_or_global", large_columns=("content",), write_mode="semantic"),
    TableSpec(
        "ai",
        "document_chunks",
        scope="tenant_or_global",
        hidden_columns=("embedding",),
        large_columns=("content", "metadata"),
        write_mode="rag",
    ),
    TableSpec("ai", "conversations", scope="user", write_mode="chat"),
    TableSpec("ai", "messages", large_columns=("content", "metadata"), write_mode="chat",
              parent_schema="ai", parent_table="conversations", parent_fk="conversation_id"),
    TableSpec("ai", "query_runs", scope="user", large_columns=("user_prompt", "intent", "selected_context")),
    TableSpec(
        "ai",
        "generated_queries",
        large_columns=("sql_text", "result_preview"),
    ),
    TableSpec("ai", "dashboard_specs", large_columns=("spec",), write_mode="dashboard"),
    TableSpec("ai", "embedding_jobs"),

    # Operations
    TableSpec("ops", "errors", large_columns=("detail",)),
    TableSpec("ops", "job_events", large_columns=("payload",)),
    TableSpec("ops", "audit_logs", large_columns=("changes",)),
    TableSpec("ops", "data_quality_runs", large_columns=("metadata",)),
    TableSpec("ops", "data_quality_results", large_columns=("detail", "sample_record_ids")),
    TableSpec("ops", "usage_daily"),
)

TABLE_REGISTRY = {spec.key: spec for spec in TABLE_SPECS}


def get_table_spec(schema: str, table: str) -> TableSpec:
    key = f"{schema}.{table}"
    try:
        return TABLE_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Table is not exposed by the frontend API: {key}") from exc


def grouped_table_specs() -> dict[str, list[TableSpec]]:
    grouped: dict[str, list[TableSpec]] = {}
    for spec in TABLE_SPECS:
        grouped.setdefault(spec.schema, []).append(spec)
    return grouped
