# Front-page API map — Merchlayer / Universal Commerce V6

All protected endpoints expect:

```http
Authorization: Bearer <SUPABASE_USER_ACCESS_TOKEN>
```

The browser never receives the Supabase service-role key, database password, commerce API secrets, or Gemini API key.

## Screen mapping

| UI element | Endpoint |
|---|---|
| Sign up | `POST /api/v1/auth/signup` |
| Sign in | `POST /api/v1/auth/login` |
| Refresh session | `POST /api/v1/auth/refresh` |
| Sign out | `POST /api/v1/auth/logout` |
| Current user + workspaces | `GET /api/v1/me` |
| Update profile | `PATCH /api/v1/me/profile` |
| Create first workspace | `POST /api/v1/me/workspaces` |
| New conversation | `POST /api/v1/conversations` (older alias: `POST /api/v1/tasks`) |
| Recent conversations | `GET /api/v1/conversations?tenant_id=...` |
| Search conversations | `GET /api/v1/conversations?tenant_id=...&q=...` |
| Open one conversation | `GET /api/v1/conversations/{id}?tenant_id=...` |
| Conversation history | `GET /api/v1/conversations/{id}/messages?tenant_id=...` |
| Send question, get answer | `POST /api/v1/conversations/{id}/messages` |
| Streaming answer (SSE) | `POST /api/v1/conversations/{id}/stream` |
| Rename / pin / archive | `PATCH /api/v1/conversations/{id}` |
| Delete conversation | `DELETE /api/v1/conversations/{id}?tenant_id=...` |
| Suggested prompts | `GET /api/v1/prompts?tenant_id=...` |
| Library | `GET /api/v1/library?tenant_id=...` |
| Library filter | `GET /api/v1/library?tenant_id=...&item_type=task|file|dashboard&q=...` |
| Files | `GET /api/v1/files?tenant_id=...` |
| Upload attachment | `POST /api/v1/files/upload` multipart |
| Delete file | `DELETE /api/v1/files/{file_id}?tenant_id=...` |
| Platform cards | `GET /api/v1/platforms` |
| Connected stores | `GET /api/v1/connections?tenant_id=...` |
| Add store | `POST /api/v1/connections` |
| Test store | `POST /api/v1/connections/{connection_id}/test` |
| Model dropdown | `GET /api/v1/models` |
| Free-plan badge | `GET /api/v1/subscription?tenant_id=...` |
| Usage | `GET /api/v1/usage?tenant_id=...&days=30` (alias of `/subscription/usage`) |
| Upgrade button | `POST /api/v1/subscription/upgrade-intent` |
| Main AI prompt (older, body carries `conversation_id`) | `POST /api/v1/ai/ask` |
| Streaming (older) | `POST /api/v1/ai/stream` |
| Server alive? | `GET /api/v1/health` (no DB) |
| Database ready? | `GET /api/v1/health/ready` |
| Dashboards | `GET /api/v1/dashboards?tenant_id=...` |

## AI request

```json
{
  "tenant_id": "TENANT_UUID",
  "conversation_id": "TASK_UUID_OR_NULL",
  "question": "Compare Shopify and Amazon sales for the last 90 days",
  "reasoning": true,
  "model_id": "merchlayer-2.0",
  "file_ids": []
}
```

The backend creates/continues the conversation, writes the user/assistant messages to `ai.messages`, retrieves the semantic catalog, validates generated SQL, executes calculations in PostgreSQL, stores the query run and dashboard specification, and returns the result.

## Platform availability

`GET /api/v1/platforms` now adds:

```json
{
  "connectable": true,
  "availability": "available",
  "manifest_id": "shopify-admin-graphql",
  "resource_count": 6,
  "resources": ["orders", "products", "customers", "inventory", "fulfillments", "refunds"]
}
```

Platforms that are seeded in the DB but do not yet have a working local manifest/resources return `connectable: false` and `availability: "coming_soon"` so the frontend does not advertise a non-working connector.

## Files

User files are uploaded to a private Supabase Storage bucket (`commerce-files` by default). File metadata and extracted text use the existing `ai.documents` table with `source_type='file'`. TXT/Markdown/JSON/CSV/PDF text can be indexed; other files remain safely stored but are marked `stored_only`.

File chunks are excluded from the tenant-wide semantic catalog search and are only used when explicitly attached to the AI request, preventing one user's uploaded file from silently influencing another user's analytics prompt.

## Plans

The API ships with provider-neutral entitlement endpoints. Defaults are controlled by environment variables:

```env
FREE_STORE_LIMIT=1
FREE_AI_QUERY_LIMIT_MONTHLY=100
```

`POST /subscription/upgrade-intent` returns a configured billing checkout URL only when `BILLING_CHECKOUT_URL` is set. Direct plan mutation is disabled by default (`ALLOW_DIRECT_PLAN_CHANGE=false`). This avoids granting paid access without a real billing confirmation flow.


## Conversations (chat) — how sending a message works

`POST /api/v1/conversations/{id}/messages`

```json
{
  "tenant_id": "TENANT_UUID",
  "content": "Compare Shopify and Amazon sales for the last 90 days",
  "reasoning": false,
  "model_id": "merchlayer-2.0",
  "file_ids": []
}
```

- One call does everything: it checks the conversation belongs to the user, checks the free-plan AI limit, asks the AI, and returns the answer (`answer`, `sql`, `rows`, `dashboard`, `dashboard_id`, ...).
- The user question **and** the assistant answer are saved by the AI analyst. The frontend must **not** also save them through `/tasks/.../messages`, or they would be stored twice.
- There is no `role` in the request. The server decides the roles, so a client cannot fake an assistant message.
- `POST /conversations/{id}/stream` takes the same body and returns Server-Sent Events: `started` -> `status` -> `result` -> `done` (or `error` -> `done`). The answer arrives as one `result` event, not word by word, because the planner returns validated structured JSON.
- Errors: 402 free-plan AI limit reached, 403 not a member of the workspace, 404 conversation not found (or not yours), 400 unsupported model, 503 Gemini/DB not configured.

## Prompts

`GET /api/v1/prompts` returns suggested starter prompts. With `tenant_id` the list is tailored to the workspace (for example "Compare my stores" only appears when 2+ stores are connected) and `context.connections` tells the UI whether to show a "connect a store first" message. Optional `category` filter: sales, products, customers, inventory, refunds, fulfillment, channels. The list lives in `api/prompt_library.py`.

## Health

- `GET /api/v1/health` only says the server is running (works even if the database is down or not configured).
- `GET /api/v1/health/ready` checks the database and returns 503 when it is unreachable.
