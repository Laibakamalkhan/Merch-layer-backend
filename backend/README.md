# Universal Commerce Enterprise V6 — Product FastAPI Backend

V6 keeps the existing universal ecommerce connector, Supabase Bronze/Silver/Gold pipeline, Gemini RAG/SQL analytics, and complete 62-table database API, then adds the product APIs required by the current frontend design.

```text
Frontend (React / Next.js)
        ↓
Supabase Auth access token
        ↓
FastAPI V6
        ├── Auth / Me / Workspaces
        ├── Tasks / Conversations / Library
        ├── Files / Attachments
        ├── Platforms / Store Connections
        ├── Multi-store Sync
        ├── Bronze → Silver → Gold
        ├── Groq + RAG + SQL Guard
        ├── AI chat + SSE lifecycle stream
        ├── Dashboard JSON
        └── Plans / Usage / Upgrade Intent
                ↓
             Supabase
```

## No Streamlit

Streamlit/pandas are not application dependencies. The frontend talks only to FastAPI.

## Configuration

No real credentials are included. Copy `.env.example` and provide server-side values during deployment.

```env
DATABASE_URL=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
EMBEDDING_DIMENSIONS=768
BRONZE_BUCKET=commerce-bronze
USER_FILES_BUCKET=commerce-files
MAX_USER_FILE_BYTES=20971520
FREE_STORE_LIMIT=1
FREE_AI_QUERY_LIMIT_MONTHLY=100
ALLOW_DIRECT_PLAN_CHANGE=false
BILLING_CHECKOUT_URL=
CORS_ORIGINS=http://localhost:3000
```

The browser uses only the Supabase user access token returned by `/api/v1/auth/login`. Service-role/database/Groq/ecommerce credentials remain server-side.

## Install and run

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
uvicorn api_main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/docs
http://localhost:8000/redoc
http://localhost:8000/openapi.json
```

## Product API groups

```text
/api/v1/auth/*           Supabase Auth wrapper
/api/v1/me/*             Current user/profile/workspaces
/api/v1/tasks/*          New Task + conversation history
/api/v1/library          Tasks/files/dashboards library search
/api/v1/files/*          Private file upload/list/delete/reindex
/api/v1/models           Model dropdown
/api/v1/subscription/*   Plan, usage, upgrade intent
/api/v1/platforms        Store cards + connectability
/api/v1/connections/*    Store connection + Vault credentials
/api/v1/sync/*           Multi-store pipeline
/api/v1/data/*           Bronze/Silver/Gold explorer
/api/v1/database/*       Explicit API for all 62 application tables
/api/v1/ai/ask           RAG + dynamic SQL + database calculation
/api/v1/ai/stream        SSE lifecycle stream for chat UI
/api/v1/dashboards/*     Saved dashboard specifications
/api/v1/analytics/*      Gold analytics endpoints
/api/v1/ops/*            Pipeline errors/events/data quality
```

See `docs/frontpage-api.md` for the current home-screen mapping and `docs/frontend-api.md` for the full integration flow.

## Authentication and tenant isolation

V6 verifies Supabase bearer access tokens through the Supabase Auth API. Tenant-scoped product/domain/database routes verify that the authenticated user has an active `iam.tenant_members` membership before returning tenant data. Generic `iam.profiles` database routes force the authenticated user's ID instead of trusting a `user_id` supplied by the browser.

The database RLS remains defense-in-depth, while FastAPI is the application security boundary because backend DB access uses server credentials.

## Files

File bytes are stored in a private Supabase Storage bucket (`commerce-files`). Metadata/extracted text use the existing `ai.documents` table, so no extra product-table migration is required. Supported extracted text formats include text/Markdown, JSON, CSV and PDF. Unsupported file types are stored but are not injected into AI context.

## AI flow

```text
Prompt + optional task + optional file IDs
        ↓
conversation history
        ↓
semantic RAG (schema / metrics / stores)
        ↓
Groq query plan
        ↓
SQL Guard
        ↓
PostgreSQL calculation over Gold/Silver
        ↓
Groq explanation + dashboard JSON
        ↓
ai.query_runs / generated_queries / messages / dashboard_specs
```

User-file chunks are excluded from tenant-wide semantic retrieval and only supplied when explicitly attached.

## Plans / billing

V6 includes entitlement and usage APIs, not a fake payment processor. Free limits are configurable by env. The upgrade button can call `/api/v1/subscription/upgrade-intent`; once a real billing checkout URL/provider is configured the endpoint returns the checkout target. Direct plan mutation is disabled by default.

## Tests

```powershell
pytest -q
```
