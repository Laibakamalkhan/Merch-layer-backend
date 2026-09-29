# FastAPI Table Route Matrix

Total finalized Supabase application tables: **62**

Every table has authenticated list and count endpoints. Tables with an `id` column also have a detail endpoint. Tenant/user scope is enforced server-side.

## iam

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `profiles` | `user` | `/api/v1/database/iam/profiles` | `/api/v1/database/iam/profiles/_count` | `/api/v1/database/iam/profiles/{record_id}` |
| `tenants` | `tenant` | `/api/v1/database/iam/tenants` | `/api/v1/database/iam/tenants/_count` | `/api/v1/database/iam/tenants/{record_id}` |
| `tenant_members` | `tenant` | `/api/v1/database/iam/tenant_members` | `/api/v1/database/iam/tenant_members/_count` | — |

## control

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `platforms` | `global` | `/api/v1/database/control/platforms` | `/api/v1/database/control/platforms/_count` | `/api/v1/database/control/platforms/{record_id}` |
| `platform_versions` | `global` | `/api/v1/database/control/platform_versions` | `/api/v1/database/control/platform_versions/_count` | `/api/v1/database/control/platform_versions/{record_id}` |
| `platform_resources` | `global` | `/api/v1/database/control/platform_resources` | `/api/v1/database/control/platform_resources/_count` | `/api/v1/database/control/platform_resources/{record_id}` |
| `connections` | `tenant` | `/api/v1/database/control/connections` | `/api/v1/database/control/connections/_count` | `/api/v1/database/control/connections/{record_id}` |
| `connection_credentials` | `tenant` | `/api/v1/database/control/connection_credentials` | `/api/v1/database/control/connection_credentials/_count` | `/api/v1/database/control/connection_credentials/{record_id}` |
| `connection_resources` | `tenant` | `/api/v1/database/control/connection_resources` | `/api/v1/database/control/connection_resources/_count` | `/api/v1/database/control/connection_resources/{record_id}` |
| `sync_schedules` | `tenant` | `/api/v1/database/control/sync_schedules` | `/api/v1/database/control/sync_schedules/_count` | `/api/v1/database/control/sync_schedules/{record_id}` |

## ingestion

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `sync_jobs` | `tenant` | `/api/v1/database/ingestion/sync_jobs` | `/api/v1/database/ingestion/sync_jobs/_count` | `/api/v1/database/ingestion/sync_jobs/{record_id}` |
| `sync_job_connections` | `tenant` | `/api/v1/database/ingestion/sync_job_connections` | `/api/v1/database/ingestion/sync_job_connections/_count` | `/api/v1/database/ingestion/sync_job_connections/{record_id}` |
| `sync_runs` | `tenant` | `/api/v1/database/ingestion/sync_runs` | `/api/v1/database/ingestion/sync_runs/_count` | `/api/v1/database/ingestion/sync_runs/{record_id}` |
| `pipeline_stage_runs` | `tenant` | `/api/v1/database/ingestion/pipeline_stage_runs` | `/api/v1/database/ingestion/pipeline_stage_runs/_count` | `/api/v1/database/ingestion/pipeline_stage_runs/{record_id}` |
| `checkpoints` | `tenant` | `/api/v1/database/ingestion/checkpoints` | `/api/v1/database/ingestion/checkpoints/_count` | `/api/v1/database/ingestion/checkpoints/{record_id}` |
| `webhook_events` | `tenant` | `/api/v1/database/ingestion/webhook_events` | `/api/v1/database/ingestion/webhook_events/_count` | `/api/v1/database/ingestion/webhook_events/{record_id}` |
| `extraction_pages` | `tenant` | `/api/v1/database/ingestion/extraction_pages` | `/api/v1/database/ingestion/extraction_pages/_count` | `/api/v1/database/ingestion/extraction_pages/{record_id}` |

## bronze

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `raw_objects` | `tenant` | `/api/v1/database/bronze/raw_objects` | `/api/v1/database/bronze/raw_objects/_count` | `/api/v1/database/bronze/raw_objects/{record_id}` |
| `records` | `tenant` | `/api/v1/database/bronze/records` | `/api/v1/database/bronze/records/_count` | `/api/v1/database/bronze/records/{record_id}` |
| `schema_snapshots` | `tenant` | `/api/v1/database/bronze/schema_snapshots` | `/api/v1/database/bronze/schema_snapshots/_count` | `/api/v1/database/bronze/schema_snapshots/{record_id}` |

## silver

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `customers` | `tenant` | `/api/v1/database/silver/customers` | `/api/v1/database/silver/customers/_count` | `/api/v1/database/silver/customers/{record_id}` |
| `customer_addresses` | `tenant` | `/api/v1/database/silver/customer_addresses` | `/api/v1/database/silver/customer_addresses/_count` | `/api/v1/database/silver/customer_addresses/{record_id}` |
| `products` | `tenant` | `/api/v1/database/silver/products` | `/api/v1/database/silver/products/_count` | `/api/v1/database/silver/products/{record_id}` |
| `product_variants` | `tenant` | `/api/v1/database/silver/product_variants` | `/api/v1/database/silver/product_variants/_count` | `/api/v1/database/silver/product_variants/{record_id}` |
| `categories` | `tenant` | `/api/v1/database/silver/categories` | `/api/v1/database/silver/categories/_count` | `/api/v1/database/silver/categories/{record_id}` |
| `product_categories` | `tenant` | `/api/v1/database/silver/product_categories` | `/api/v1/database/silver/product_categories/_count` | — |
| `locations` | `tenant` | `/api/v1/database/silver/locations` | `/api/v1/database/silver/locations/_count` | `/api/v1/database/silver/locations/{record_id}` |
| `inventory_levels` | `tenant` | `/api/v1/database/silver/inventory_levels` | `/api/v1/database/silver/inventory_levels/_count` | `/api/v1/database/silver/inventory_levels/{record_id}` |
| `orders` | `tenant` | `/api/v1/database/silver/orders` | `/api/v1/database/silver/orders/_count` | `/api/v1/database/silver/orders/{record_id}` |
| `order_items` | `tenant` | `/api/v1/database/silver/order_items` | `/api/v1/database/silver/order_items/_count` | `/api/v1/database/silver/order_items/{record_id}` |
| `order_addresses` | `tenant` | `/api/v1/database/silver/order_addresses` | `/api/v1/database/silver/order_addresses/_count` | `/api/v1/database/silver/order_addresses/{record_id}` |
| `payments` | `tenant` | `/api/v1/database/silver/payments` | `/api/v1/database/silver/payments/_count` | `/api/v1/database/silver/payments/{record_id}` |
| `refunds` | `tenant` | `/api/v1/database/silver/refunds` | `/api/v1/database/silver/refunds/_count` | `/api/v1/database/silver/refunds/{record_id}` |
| `refund_items` | `tenant` | `/api/v1/database/silver/refund_items` | `/api/v1/database/silver/refund_items/_count` | `/api/v1/database/silver/refund_items/{record_id}` |
| `fulfillments` | `tenant` | `/api/v1/database/silver/fulfillments` | `/api/v1/database/silver/fulfillments/_count` | `/api/v1/database/silver/fulfillments/{record_id}` |
| `fulfillment_items` | `tenant` | `/api/v1/database/silver/fulfillment_items` | `/api/v1/database/silver/fulfillment_items/_count` | `/api/v1/database/silver/fulfillment_items/{record_id}` |
| `returns` | `tenant` | `/api/v1/database/silver/returns` | `/api/v1/database/silver/returns/_count` | `/api/v1/database/silver/returns/{record_id}` |
| `return_items` | `tenant` | `/api/v1/database/silver/return_items` | `/api/v1/database/silver/return_items/_count` | `/api/v1/database/silver/return_items/{record_id}` |

## gold

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `daily_sales` | `tenant` | `/api/v1/database/gold/daily_sales` | `/api/v1/database/gold/daily_sales/_count` | `/api/v1/database/gold/daily_sales/{record_id}` |
| `product_daily` | `tenant` | `/api/v1/database/gold/product_daily` | `/api/v1/database/gold/product_daily/_count` | `/api/v1/database/gold/product_daily/{record_id}` |
| `customer_metrics` | `tenant` | `/api/v1/database/gold/customer_metrics` | `/api/v1/database/gold/customer_metrics/_count` | `/api/v1/database/gold/customer_metrics/{record_id}` |
| `inventory_snapshot_daily` | `tenant` | `/api/v1/database/gold/inventory_snapshot_daily` | `/api/v1/database/gold/inventory_snapshot_daily/_count` | `/api/v1/database/gold/inventory_snapshot_daily/{record_id}` |
| `refund_daily` | `tenant` | `/api/v1/database/gold/refund_daily` | `/api/v1/database/gold/refund_daily/_count` | `/api/v1/database/gold/refund_daily/{record_id}` |
| `fulfillment_daily` | `tenant` | `/api/v1/database/gold/fulfillment_daily` | `/api/v1/database/gold/fulfillment_daily/_count` | `/api/v1/database/gold/fulfillment_daily/{record_id}` |
| `channel_daily` | `tenant` | `/api/v1/database/gold/channel_daily` | `/api/v1/database/gold/channel_daily/_count` | `/api/v1/database/gold/channel_daily/{record_id}` |

## ai

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `metric_definitions` | `tenant_or_global` | `/api/v1/database/ai/metric_definitions` | `/api/v1/database/ai/metric_definitions/_count` | `/api/v1/database/ai/metric_definitions/{record_id}` |
| `semantic_columns` | `tenant_or_global` | `/api/v1/database/ai/semantic_columns` | `/api/v1/database/ai/semantic_columns/_count` | `/api/v1/database/ai/semantic_columns/{record_id}` |
| `query_permissions` | `tenant_or_global` | `/api/v1/database/ai/query_permissions` | `/api/v1/database/ai/query_permissions/_count` | `/api/v1/database/ai/query_permissions/{record_id}` |
| `documents` | `tenant_or_global` | `/api/v1/database/ai/documents` | `/api/v1/database/ai/documents/_count` | `/api/v1/database/ai/documents/{record_id}` |
| `document_chunks` | `tenant_or_global` | `/api/v1/database/ai/document_chunks` | `/api/v1/database/ai/document_chunks/_count` | `/api/v1/database/ai/document_chunks/{record_id}` |
| `conversations` | `user` | `/api/v1/database/ai/conversations` | `/api/v1/database/ai/conversations/_count` | `/api/v1/database/ai/conversations/{record_id}` |
| `messages` | `tenant` | `/api/v1/database/ai/messages` | `/api/v1/database/ai/messages/_count` | `/api/v1/database/ai/messages/{record_id}` |
| `query_runs` | `user` | `/api/v1/database/ai/query_runs` | `/api/v1/database/ai/query_runs/_count` | `/api/v1/database/ai/query_runs/{record_id}` |
| `generated_queries` | `tenant` | `/api/v1/database/ai/generated_queries` | `/api/v1/database/ai/generated_queries/_count` | `/api/v1/database/ai/generated_queries/{record_id}` |
| `dashboard_specs` | `tenant` | `/api/v1/database/ai/dashboard_specs` | `/api/v1/database/ai/dashboard_specs/_count` | `/api/v1/database/ai/dashboard_specs/{record_id}` |
| `embedding_jobs` | `tenant` | `/api/v1/database/ai/embedding_jobs` | `/api/v1/database/ai/embedding_jobs/_count` | `/api/v1/database/ai/embedding_jobs/{record_id}` |

## ops

| Table | Scope | List | Count | Detail |
|---|---|---|---|---|
| `errors` | `tenant` | `/api/v1/database/ops/errors` | `/api/v1/database/ops/errors/_count` | `/api/v1/database/ops/errors/{record_id}` |
| `job_events` | `tenant` | `/api/v1/database/ops/job_events` | `/api/v1/database/ops/job_events/_count` | `/api/v1/database/ops/job_events/{record_id}` |
| `audit_logs` | `tenant` | `/api/v1/database/ops/audit_logs` | `/api/v1/database/ops/audit_logs/_count` | `/api/v1/database/ops/audit_logs/{record_id}` |
| `data_quality_runs` | `tenant` | `/api/v1/database/ops/data_quality_runs` | `/api/v1/database/ops/data_quality_runs/_count` | `/api/v1/database/ops/data_quality_runs/{record_id}` |
| `data_quality_results` | `tenant` | `/api/v1/database/ops/data_quality_results` | `/api/v1/database/ops/data_quality_results/_count` | `/api/v1/database/ops/data_quality_results/{record_id}` |
| `usage_daily` | `tenant` | `/api/v1/database/ops/usage_daily` | `/api/v1/database/ops/usage_daily/_count` | `/api/v1/database/ops/usage_daily/{record_id}` |
