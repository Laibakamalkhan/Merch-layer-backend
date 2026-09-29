# Complete Supabase Table API

V6 exposes every application table from the finalized Supabase schema through FastAPI while keeping pipeline-owned writes behind business services. All routes require a Supabase user bearer token; tenant/user scope is checked by FastAPI before database access.

## Authentication

```http
Authorization: Bearer <SUPABASE_USER_ACCESS_TOKEN>
```

## Route pattern

For each registered table:

```text
GET /api/v1/database/<schema>/<table>
GET /api/v1/database/<schema>/<table>/_count
GET /api/v1/database/<schema>/<table>/<record_id>   (when table has `id`)
```

Advanced query endpoint:

```text
POST /api/v1/database/query/<schema>/<table>
```

Request body example:

```json
{
  "tenant_id": "TENANT_UUID",
  "filters": {
    "connection_id": "CONNECTION_UUID",
    "status": "completed"
  },
  "limit": 100,
  "offset": 0,
  "order_by": "created_at",
  "order_dir": "desc",
  "include_large_fields": false
}
```

The database catalog endpoint returns the authoritative runtime table/column contract:

```text
GET /api/v1/database/catalog
```

## Table coverage

### iam
- profiles
- tenants
- tenant_members

### control
- platforms
- platform_versions
- platform_resources
- connections
- connection_credentials
- connection_resources
- sync_schedules

### ingestion
- sync_jobs
- sync_job_connections
- sync_runs
- pipeline_stage_runs
- checkpoints
- webhook_events
- extraction_pages

### bronze
- raw_objects
- records
- schema_snapshots

### silver
- customers
- customer_addresses
- products
- product_variants
- categories
- product_categories
- locations
- inventory_levels
- orders
- order_items
- order_addresses
- payments
- refunds
- refund_items
- fulfillments
- fulfillment_items
- returns
- return_items

### gold
- daily_sales
- product_daily
- customer_metrics
- inventory_snapshot_daily
- refund_daily
- fulfillment_daily
- channel_daily

### ai
- metric_definitions
- semantic_columns
- query_permissions
- documents
- document_chunks
- conversations
- messages
- query_runs
- generated_queries
- dashboard_specs
- embedding_jobs

### ops
- errors
- job_events
- audit_logs
- data_quality_runs
- data_quality_results
- usage_daily

## Scope rules

- Tenant-owned tables require `tenant_id`.
- Global platform catalog tables are global.
- Global + tenant semantic rows return global rows plus the requested tenant's overrides.
- `iam.profiles` requires `user_id` rather than permitting a full user directory dump.
- `control.connection_credentials` never exposes `vault_secret_id` through the generic frontend API.
- `ai.document_chunks` never exposes the raw embedding vector.
- Large fields such as Bronze payloads are omitted by default and can be requested with `include_large_fields=true` when permitted.

## Write rules

Bronze, Silver, Gold, ingestion runs, RAG chunks, operational logs and other pipeline-owned tables must not be written directly by the browser/frontend. Their write path is:

```text
Frontend → FastAPI domain endpoint → service/orchestrator → Supabase tables
```

This prevents the frontend from bypassing transformation, quality, tenant, checkpoint and audit logic.
