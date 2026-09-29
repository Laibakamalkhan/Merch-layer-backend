# Frontend API Contract — Universal Commerce Enterprise V6

The browser talks only to FastAPI. It never receives the Supabase service-role key, database password, commerce credentials, or Gemini API key.

## Session

```text
POST /api/v1/auth/signup
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/me
```

Send the returned user access token on protected calls:

```http
Authorization: Bearer <access_token>
```

Create/select a workspace with `GET/POST /api/v1/me/workspaces`. Tenant-scoped routes verify membership server-side.

## Home / chat

```text
POST /api/v1/tasks                         New Task
GET  /api/v1/tasks?tenant_id=&q=           History/search
GET  /api/v1/tasks/{id}/messages           Chat history
GET  /api/v1/models                        Model dropdown
POST /api/v1/ai/ask                        Structured response
POST /api/v1/ai/stream                     SSE lifecycle stream
```

AI request fields:

```json
{
  "tenant_id": "TENANT_UUID",
  "conversation_id": null,
  "question": "Which store grew fastest this month?",
  "reasoning": true,
  "model_id": "merchlayer-2.0",
  "file_ids": []
}
```

## Platform cards / store connectors

```text
GET  /api/v1/platforms
GET  /api/v1/connections?tenant_id=
POST /api/v1/connections
POST /api/v1/connections/{id}/credentials
POST /api/v1/connections/{id}/test
GET  /api/v1/connections/{id}/resources
PATCH /api/v1/connections/{id}/resources/{resource_key}
```

`/platforms` includes `connectable` and `availability`, so seeded but unfinished connectors can render as Coming Soon instead of opening a broken credential flow.

## Files / attachments

```text
GET    /api/v1/files?tenant_id=
POST   /api/v1/files/upload
POST   /api/v1/files/{id}/reindex?tenant_id=
DELETE /api/v1/files/{id}?tenant_id=
```

Upload is `multipart/form-data` with `tenant_id` and `upload` fields. Pass returned file document IDs in `file_ids` on `/ai/ask` or `/ai/stream`.

## Library

```text
GET /api/v1/library?tenant_id=
GET /api/v1/library?tenant_id=&q=keyword
GET /api/v1/library?tenant_id=&item_type=task|file|dashboard
```

## Plan banner / usage / upgrade

```text
GET  /api/v1/subscription/plans
GET  /api/v1/subscription?tenant_id=
GET  /api/v1/subscription/usage?tenant_id=
POST /api/v1/subscription/upgrade-intent
```

A real billing provider is intentionally not faked. Configure `BILLING_CHECKOUT_URL` when checkout exists.

## Multi-store data pipeline

```text
POST /api/v1/sync/run
POST /api/v1/sync/background
GET  /api/v1/sync/jobs/{job_id}
```

Pipeline:

```text
Vault credentials
  → platform manifests
  → Universal Connector
  → ingestion jobs/runs/checkpoints/pages
  → Bronze Storage + bronze tables
  → Silver standardized ecommerce model
  → data-quality results
  → Gold marts
  → optional semantic/RAG refresh
```

## Analytics / dashboards

```text
GET /api/v1/analytics/sales-summary?tenant_id=
GET /api/v1/analytics/channel-performance?tenant_id=
GET /api/v1/dashboards?tenant_id=
GET /api/v1/dashboards/{dashboard_id}
```

## Complete finalized database API

All 62 finalized application tables remain available through explicit read routes:

```text
GET  /api/v1/database/catalog
GET  /api/v1/database/{schema}/{table}
GET  /api/v1/database/{schema}/{table}/_count
GET  /api/v1/database/{schema}/{table}/{record_id}
POST /api/v1/database/query/{schema}/{table}
```

Tenant/user scope is enforced against the authenticated user. Vault secret values and vector embeddings are never returned.
