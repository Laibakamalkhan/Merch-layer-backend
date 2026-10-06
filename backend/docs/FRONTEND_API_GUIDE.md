# Frontend API Guide

Base URL (local): `http://localhost:8000`  ·  Prefix: `/api/v1`  ·  Interactive docs: `/docs` (Swagger)

Auth = **Supabase**. The backend wraps it, so the frontend never needs Supabase keys.

## 1. Auth flow (do this first)

| Step | Call | Notes |
|---|---|---|
| Sign up | `POST /api/v1/auth/signup` `{email, password(min 8), display_name?}` | |
| Login | `POST /api/v1/auth/login` `{email, password}` | Returns `access_token`, `refresh_token`, `expires_in`, `user` |
| Refresh | `POST /api/v1/auth/refresh` `{refresh_token}` | Call before/when a request returns 401 |

Send on **every** protected call: `Authorization: Bearer <access_token>`

Only `GET /platforms` and `GET /health` work without a token.

## 2. The `tenant_id` rule (most important)

Almost every call needs a **`tenant_id`** (= the user's workspace).

1. After login call `GET /me` → `workspaces[]`. Use `workspaces[0].id` as `tenant_id`.
2. If `workspaces` is empty: `POST /me/workspaces` `{name, slug}` → 201, returns the new workspace (`id` = tenant_id).
3. Store `tenant_id` in app state. GET endpoints take it as a **query param** (`?tenant_id=...`); POST endpoints take it in the **JSON body**.
4. A tenant the user does not belong to → **403**.

## 3. The 15 endpoints

### Read-only

| # | Endpoint | Query params | Response |
|---|---|---|---|
| 1 | `GET /me` | — | `{id, email, profile, workspaces:[{id,name,slug,timezone,role,...}]}` |
| 2 | `GET /platforms` | — (no token needed) | `{items:[{code,name,protocol,category,connectable,availability("available"/"coming_soon"),resources[],connection_fields,...}]}` — only show a Connect button when `connectable=true` |
| 3 | `GET /connections` | `tenant_id` | `{items:[{id,name,platform_code,platform_name,status,last_synced_at,...}]}` (secrets are never returned) |
| 4 | `GET /library` | `tenant_id`, `q?`, `item_type?` (`task`\|`file`\|`dashboard`), `limit?` | `{items:[{type,id,title,created_at,updated_at,metadata}]}` |
| 5 | `GET /files` | `tenant_id`, `q?`, `limit?`, `offset?` | `{items:[{id,title,metadata{filename,mime_type,size_bytes,index_status},created_at}]}` |
| 6 | `GET /models` | — | `{default:"merchlayer-2.0", items:[{id,name,supports_reasoning,supports_files,available}]}` — if `available=false` the AI key is missing on the server |
| 7 | `GET /prompts` | `tenant_id?`, `category?` | `{items:[{id,category,title,text}], categories, context:{connections, connected_platforms}}` — if `context.connections == 0` show "Connect a store first" |
| 8 | `GET /subscription` | `tenant_id` | `{tenant_id, plan:{code,name,store_limit,ai_query_limit_monthly}, usage:{...}}` |
| 9 | `GET /usage` | `tenant_id`, `days?` (default 30) | `{ai_queries, api_requests, connections, days, ...}` |
| 10 | `GET /health` | — | `{status:"ok"}` (server alive; `GET /health/ready` also checks the DB) |

### Conversations (chat)

| # | Endpoint | Body / params | Response |
|---|---|---|---|
| 11 | `POST /conversations` | `{tenant_id, title?}` | **201** conversation row `{id, tenant_id, title, ...}` |
| 12 | `GET /conversations` | `tenant_id`, `q?`, `archived?`, `limit?`, `offset?` | `{items:[{id,title,message_count,last_message_at,...}]}` |
| 13 | `GET /conversations/{id}` | `tenant_id` | conversation row. 404 if not found / not yours |
| 14 | `POST /conversations/{id}/messages` | `{tenant_id, content, reasoning?:false, model_id?:"merchlayer-2.0", file_ids?:[]}` | **201** `{conversation_id, query_run_id, answer, sql, rows, dashboard, dashboard_id, route, reasoning}` |
| 15 | `POST /conversations/{id}/stream` | same body as #14 | Server-Sent Events (see below) |

Extra chat endpoints you will likely need: `GET /conversations/{id}/messages?tenant_id=` (history, `{items:[{role,content,metadata,created_at}]}`), `PATCH /conversations/{id}` (rename/pin/archive), `DELETE /conversations/{id}?tenant_id=` (204).

**Important:** the server saves both the user question and the AI answer. The frontend must **not** save messages itself. There is no `role` in the request.

## 4. Streaming (endpoint 15)

Events arrive in this order: `started` → `status` → `result` → `done` (or `error` → `done`). The full answer comes in **one** `result` event (not word-by-word).

```js
const res = await fetch(`${API}/conversations/${id}/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: JSON.stringify({ tenant_id, content: question }),
});
const reader = res.body.getReader();
const dec = new TextDecoder();
let buf = "";
for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  buf += dec.decode(value, { stream: true });
  const blocks = buf.split("\n\n");
  buf = blocks.pop();
  for (const b of blocks) {
    const [ev, data] = b.split("\n");
    const name = ev.replace("event: ", "");
    const payload = JSON.parse(data.replace("data: ", ""));
    // name: started | status | result | error | done
  }
}
```
(Use `fetch`, not `EventSource` — EventSource cannot send POST bodies or the Authorization header.)

## 5. Rendering an AI answer

`answer` = text · `rows` = table data (array of objects) · `sql` = executed query (optional "Show SQL") · `dashboard` = `{title, kpis:[{label,column,aggregation}], charts:[{type:"line|bar|area|table",title,x,y,series}], filters}` — build KPI cards/charts from `rows` using the column names in `dashboard`.

## 6. Errors (JSON: `{"detail": "..."}`)

| Code | Meaning | UI action |
|---|---|---|
| 400 | Bad input / unsupported model | Show message |
| 401 | Missing/expired token | Refresh token, else login |
| 402 | Free plan limit reached (AI queries or stores) | Show upgrade prompt |
| 403 | Not a member of that workspace | Re-fetch `/me` |
| 404 | Conversation/file not found | |
| 422 | Request body/params invalid (FastAPI validation) | Fix field shown in `detail` |
| 502 / 504 | AI provider unreachable / timed out | "Try again" |
| 503 | AI/DB not configured or **RAG index empty** | "Data not ready yet" |
| 500 | Unexpected server error | Generic error + retry |

## 7. When will the AI return a real answer?

AI answers need data. A brand-new workspace has none. Order of setup (backend/admin side):
1. `POST /connections` (add a store) → `POST /connections/{id}/test`
2. `POST /sync/run` `{tenant_id, connection_ids:[...], rebuild_rag_after_sync:true}` (loads data + builds the AI index)
3. Otherwise a one-time `POST /ai/rag/rebuild` `{tenant_id}`

## 8. CORS

Backend allows `http://localhost:3000` by default. For another frontend URL set `CORS_ORIGINS` in the backend `.env` (comma separated) and restart.

## 9. Frontend Tables (read-only)

Table data for **orders**, **products** and **customers** from the Silver layer. Rows from API stores (Shopify, WooCommerce, Amazon) and uploaded files (CSV/XLSX/JSON) appear together; `source_type` (`api` | `file`) tells them apart. Both routes need `Authorization: Bearer <token>` and a `tenant_id` the user belongs to (otherwise **403**).

### 9.1 `GET /api/v1/tables/sources?tenant_id=`

Returns one item per connection (newest first), for a source filter dropdown.

```json
{
  "items": [
    {
      "connection_id": "7f1c0f0e-1111-4c1a-9d55-0a1b2c3d4e5f",
      "name": "My Shopify Store",
      "platform_code": "shopify",
      "platform_name": "Shopify",
      "source_type": "api",
      "status": "active",
      "last_synced_at": "2026-10-05T09:30:00Z",
      "dataset": null,
      "counts": {"orders": 120, "products": 45, "customers": 80}
    },
    {
      "connection_id": "2b9d7a10-2222-4f3b-8c66-1a2b3c4d5e6f",
      "name": "sales_oct.csv",
      "platform_code": "file_upload",
      "platform_name": "File Upload",
      "source_type": "file",
      "status": "active",
      "last_synced_at": null,
      "dataset": {
        "id": "c3e5...", "filename": "sales_oct.csv", "file_type": "csv",
        "status": "completed", "row_count": 300, "created_at": "2026-10-04T12:00:00Z"
      },
      "counts": {"orders": 300, "products": 0, "customers": 0}
    }
  ]
}
```

`dataset` is `null` for API sources. Secrets, config and credentials are never returned.

### 9.2 `GET /api/v1/tables/{entity}`

`entity` = `orders` | `products` | `customers` (anything else -> 422).

| Param | Type | Notes |
|---|---|---|
| `tenant_id` | UUID | **required** |
| `connection_id` | UUID | optional; must belong to the tenant, else **404** |
| `source_type` | `api` \| `file` | optional |
| `search` | string (max 100) | case-insensitive; `%`, `_` and `\` are treated as normal characters |
| `status` | string (max 50) | normalized lowercase, e.g. `paid`, `active` |
| `fulfillment_status` | string (max 50) | **orders only** |
| `date_from`, `date_to` | `YYYY-MM-DD` | **orders only**; `date_to` is inclusive; `date_from` after `date_to` -> 400 |
| `sort_by` | string | must be a `sortable` column key of that entity, else **400** |
| `sort_dir` | `asc` \| `desc` | default `desc`; other value -> 422 |
| `limit` | int 1..200 | default 50 (0 or 201 -> 422) |
| `offset` | int >= 0 | default 0 |

**Searchable fields:** orders = `order_number`, `source_id`; products = `title`, `vendor`, `handle`; customers = `display_name`, `first_name`, `last_name`, `email`, `phone`.

**Default sort:** orders `order_date`, products `product_date`, customers `customer_since` (all newest first). Nulls are always last; ties are broken by row id so pages never overlap.

**Columns** (use the `columns` array in the response to build the table header):

| Entity | Column keys |
|---|---|
| orders | `order_number`, `source_name`, `source`, `sales_channel`, `status`, `fulfillment_status`, `total_amount` (money), `net_amount` (money), `order_date` |
| products | `title`, `vendor`, `product_type`, `status`, `source_name`, `source`, `product_date` |
| customers | `name`, `email`, `phone`, `orders_count`, `total_spent` (plain number, no currency), `source_name`, `source`, `customer_since` |

Column `type` is one of `text`, `status`, `money`, `datetime`, `number`. A `money` column has `currency_key` (name of the item field holding the currency, e.g. `currency_code`). **Never add up money across different currencies.**

**Extra item fields (not columns):** all entities: `id`, `connection_id`, `source_type`; orders: `currency_code`, `source_order_id`, `refunded_amount`; products: `source_product_id`. The same order can appear under two connections if the same store was connected twice - use `connection_id` / `source_name` to tell them apart. Missing values are `null` (for example WooCommerce products have no vendor).

**Pagination:** `total` is the number of rows matching the filters (also correct for an empty page). `has_more` = `offset + items.length < total`. Next page: `offset += limit`.

**Errors:** 400 invalid `sort_by` / date range, 401 no token, 403 not a workspace member, 404 unknown connection for this tenant, 422 invalid parameter, 500 `{"detail": "Query failed"}`.

**Example:** `GET /api/v1/tables/orders?tenant_id=...&search=10&sort_by=total_amount&sort_dir=desc&limit=2`

```json
{
  "entity": "orders",
  "columns": [
    {"key": "order_number", "label": "Order", "type": "text", "sortable": true},
    {"key": "source_name", "label": "Store / File", "type": "text", "sortable": true},
    {"key": "source", "label": "Platform", "type": "text", "sortable": false},
    {"key": "sales_channel", "label": "Channel", "type": "text", "sortable": false},
    {"key": "status", "label": "Status", "type": "status", "sortable": true},
    {"key": "fulfillment_status", "label": "Fulfillment", "type": "status", "sortable": true},
    {"key": "total_amount", "label": "Total", "type": "money", "sortable": true, "currency_key": "currency_code"},
    {"key": "net_amount", "label": "Net", "type": "money", "sortable": false, "currency_key": "currency_code"},
    {"key": "order_date", "label": "Order Date", "type": "datetime", "sortable": true}
  ],
  "items": [
    {
      "order_number": "#1010", "source_name": "My Shopify Store", "source": "Shopify",
      "sales_channel": null, "status": "paid", "fulfillment_status": "unfulfilled",
      "total_amount": "249.90", "net_amount": "249.90", "order_date": "2026-10-03T14:21:00Z",
      "id": "a1b2c3d4-0000-4000-8000-000000000001",
      "connection_id": "7f1c0f0e-1111-4c1a-9d55-0a1b2c3d4e5f",
      "currency_code": "USD", "source_type": "api",
      "source_order_id": "gid://shopify/Order/1010", "refunded_amount": "0.00"
    }
  ],
  "total": 37,
  "limit": 2,
  "offset": 0,
  "has_more": true
}
```