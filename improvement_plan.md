# IMPROVEMENT_PLAN.md — Safe hardening & fix plan for "Internship-Proj2" (NexusCommerce / MerchLayer)

> **Audience:** an AI coding agent (Cursor, Google Antigravity, Claude Code, etc.) working inside this repository, supervised by a **beginner developer**.
> **Language rule:** write code, comments and commit messages in **English**. Existing user-facing messages in the repo are partly Roman Urdu — keep that style where a message already exists; do not rewrite messages that are not part of your task.

---

## 0. HOW TO USE THIS FILE (agent: read this section first, completely)

### 0.1 Mandatory working protocol

1. **Understand before editing.** Do **Section 1 (Project Understanding)** and **Section 2 (Reconnaissance checklist)** first. Edit **nothing** until you have posted a short *Understanding Summary* (see 2.3) and the human replied "OK".
2. **One task at a time.** Work through tasks in the order given (Phase 0 → 5). Each task has: *Problem → Files → Steps → Acceptance criteria → Verify → Rollback*. Finish and verify a task before starting the next.
3. **Branch + small commits.** Create branch `improvements/phase-N`. One task = one commit, message format: `fix(T1.4): require tenant access on /sync/tasks`. Never commit to `main` directly.
4. **Green-before-green.** Before the first edit run the baseline test-suite (see 1.6). It currently passes (**56 passed**). It must still pass after every task. Never delete or weaken an existing test to make it pass; if a test is genuinely wrong, stop and ask the human.
5. **Secrets are radioactive.** `backend/.env` and root `.env` contain (or contained) real keys. **Never open, print, quote, log, or commit their values.** Only edit `*.env.example` files. If you need a variable name, read it from `.env.example` or from `backend/src/commerce_connector/api/config.py`.
6. **Never run SQL that changes the real Supabase database.** For any DB change, **write a `.sql` file** under `backend/scripts/sql/` and tell the human to review and run it in the Supabase SQL editor. You may run read-only introspection only if the human gives you a connection.
7. **Do not guess the database schema.** The full DDL is **not** in this repo (only `backend/scripts/check_supabase_schema.sql`, which lists expected tables). When a task depends on a column/enum you cannot see in code, **ask the human** to run an introspection query (templates given in the task) instead of inventing it.
8. **Keep API contracts stable.** The frontend (`src/lib/api.js`) and docs (`backend/docs/*.md`, `backend/docs/openapi.json`) depend on current response shapes. Add fields; do not rename/remove them. Older routes (e.g. `/tasks/*`) must keep working.
9. **Minimal diffs.** No reformatting, no renames, no drive-by refactors, no new frameworks. New Python dependencies must be added to **both** `backend/requirements.txt` **and** `backend/pyproject.toml`.
10. **If reality disagrees with this plan** (file moved, function renamed, different behaviour): stop, explain what you found, propose an adjusted step, wait for the human.
11. **After each task** post: files changed, what you ran, results, and anything you were unsure about. Use the checklist in Section 9.

### 0.2 Things only the HUMAN can do (agent must not attempt; remind the human)

| # | Human action | Why |
|---|---|---|
| H1 | **Rotate** the Groq API key, Supabase `service_role` + `anon` keys, and the Postgres password (they were in a zip that was shared). | Treat them as leaked. |
| H2 | Run any `.sql` file the agent writes, in the Supabase SQL editor, after reading it. | Agent must not mutate the production DB. |
| H3 | Create the `analyst_ro` DB role password and put the resulting URL into `backend/.env` as `ANALYST_DATABASE_URL`. | Secret value. |
| H4 | Decide product questions listed in Section 8 ("Decisions needed"). | Agent must not guess business rules. |
| H5 | Test with two real accounts (A and B) for the cross-tenant checks. | Needs real login. |

### 0.3 Suggested prompts for the human to paste

**Prompt 1 (reconnaissance — use Plan/Ask mode, no edits):**
> Read `improvement_plan.md` fully. Then do Section 2 (reconnaissance) and reply with the *Understanding Summary* from 2.3. Do not modify any file yet.

**Prompt 2 (per task — use Agent mode):**
> Implement task **T1.1** from `improvement_plan.md` exactly as written, following the working protocol in Section 0. Stop after its acceptance criteria are met and report using the Section 9 checklist.

---

## 1. PROJECT UNDERSTANDING (facts verified by reading the code and running the tests)

### 1.1 What the product is
A multi-tenant SaaS: users sign up, connect e-commerce stores (Shopify, WooCommerce, Amazon…), the backend **syncs** their data into a Postgres "medallion" warehouse (**Bronze** raw → **Silver** normalised → **Gold** daily aggregates), builds a **RAG index** (embeddings), and a chat UI lets the user ask analytics questions in natural language. An LLM (Groq) turns the question into **SQL**, the backend validates it with `SQLGuard`, runs it read-only, and returns an answer + KPIs + chart specs.

### 1.2 Stack
- **Frontend:** React 19 + Vite 8, plain CSS, `framer-motion`, `lucide-react`, linter `oxlint`. No router (hash based: `#workspace`, `#app`, `#signin`, `#start-flow`, `#landing`). No TypeScript, no frontend tests, no CI.
- **Backend:** Python ≥3.11 (the dev machine uses 3.13), **FastAPI**, `psycopg` 3 + `psycopg_pool`, `httpx`, `pydantic` 2, `pypdf`. Package `commerce_connector` lives in `backend/src/`.
- **External services:** Supabase (Auth, Postgres, Vault, Storage), Groq (LLM), Ollama (local embeddings, 768 dims, `pgvector`).
- **Dev environment:** Windows (`D:\Internship-Proj2`, PowerShell, `.venv\Scripts\...`). Frontend dev server is pinned to port **5173** (`strictPort`), backend on **8000**.

### 1.3 Repository map (what matters)

```
/                          React app (package.json, vite.config.js, index.html)
├─ src/
│  ├─ main.jsx             mounts <AuthProvider><App/></AuthProvider> inside React.StrictMode
│  ├─ App.jsx              hash-based view switch: landing page vs workspace (login gate)
│  ├─ lib/api.js           THE ONLY place that calls the backend (fetch wrapper, token refresh, ApiError)
│  ├─ context/AuthContext.jsx   login/signup/logout, loadMe(), auto-creates first workspace, exposes tenantId
│  ├─ components/auth/AuthPage.jsx
│  ├─ components/workspace/    WorkspaceView, WorkspaceChat (586 lines), StoreConnectorsTab,
│  │                           ConnectStoreModal, LibraryTab, FilesTab, UpgradeModal, AnalyticsChart, Sidebar/Header
│  ├─ components/sections/     landing-page sections (static marketing content)
│  └─ data/siteData.js         static landing data
├─ backend/
│  ├─ api_main.py          `from commerce_connector.api.app import app`  (uvicorn api_main:app)
│  ├─ main.py + cli/       separate CLI tool (not the web app)
│  ├─ requirements.txt / pyproject.toml   (dependency lists are DUPLICATED — keep in sync)
│  ├─ manifests/ mappings/ config/        platform manifests, silver mappings, yaml config
│  ├─ scripts/             helper scripts incl. check_supabase_schema.sql, diagnose_ai.py
│  ├─ tests/               pytest (56 tests, all passing at baseline)
│  └─ src/commerce_connector/
│     ├─ api/              FastAPI layer
│     │   app.py           create_app(): CORS, error middleware, mounts routers under /api/v1
│     │   config.py        APISettings.from_env() (loads backend/.env via python-dotenv)
│     │   deps.py          get_api_settings(), get_service() — both @lru_cache singletons
│     │   auth.py          SupabaseAuthClient, get_current_user (calls Supabase /auth/v1/user EVERY request),
│     │                    require_tenant_access(service, user_id, tenant_id)
│     │   schemas.py       pydantic request models
│     │   ai_helpers.py    enforce_ai_limit, ask_ai_or_http_error, SSE helpers, map_ai_exception
│     │   task_manager.py  in-memory BackgroundTaskManager (TASKS) for /sync/background
│     │   table_registry.py allowlist of tables exposed by the generic /database API
│     │   routers/         auth, me, tenants, connections, sync, files, conversations, tasks(legacy),
│     │                    ai, database, data, library, dashboards, prompts, subscription, usage,
│     │                    analytics, ops, models, platforms, health
│     ├─ platform/         business logic
│     │   service.py       CommercePlatformService: wires db, bronze, silver, gold, sync_engine, llm, indexer, analyst
│     │   db.py            PostgresGateway (1924 lines) — ALL SQL lives here; pool min1/max10
│     │   ai_analyst.py    AIAnalyst.ask(): RAG context → Groq plan (PLAN_SYSTEM) → SQLGuard → execute_readonly_query → Groq answer
│     │   sql_guard.py     SQLGuard (regex based)  ← security-critical
│     │   rag.py groq.py gemini.py(legacy) llm.py   embeddings / LLM clients
│     │   orchestrator.py bronze.py silver.py gold.py   sync pipeline
│     │   settings.py      PlatformSettings dataclass (built field-by-field in api/deps.py!)
│     ├─ core/ connection/ manifests/ protocols/ auth/ pagination/ response/ resilience/ transport/
│     │  security/ discovery/ bulk/ webhooks/ plugins/ runtime/    generic "universal connector" engine
│     │     transport/client.py   ResilientHttpClient (httpx, follow_redirects=True)
│     │     security/ssrf.py      assert_safe_public_url()
│     └─ ...
```

### 1.4 Key request flows

1. **Auth:** frontend → `POST /api/v1/auth/login` → backend proxies to Supabase → returns `access_token` + `refresh_token`; frontend stores them in `localStorage` key `merchlayer.session`. Every API call sends `Authorization: Bearer`. On `401` the frontend calls `/auth/refresh` once and retries.
2. **Tenant model:** a *workspace* == a *tenant* (`iam.tenants`), membership in `iam.tenant_members`. Every endpoint calls `require_tenant_access(service, user_id, tenant_id)`. Plan is `iam.tenants.metadata->>'plan_code'` (`free`/`pro`).
3. **Connect store:** `POST /connections` → `POST /connections/{id}/test` → `POST /sync/background` → poll `GET /sync/tasks/{task_id}` (state held **in memory** in `TASKS`).
4. **Ask AI:** `POST /conversations` → `POST /conversations/{id}/messages` (non-streaming; `/stream` SSE exists but the frontend does not use it). `AIAnalyst.ask` already saves BOTH user and assistant messages — callers must not save them again.
5. **Generic table API:** `/database/{schema}/{table}` is generated from `table_registry.TABLE_SPECS`; SQL there is parameterised with identifier quoting (this part is GOOD — do not weaken it).

### 1.5 Conventions to respect
- Python: `from __future__ import annotations`, type hints, FastAPI routers with `Depends(get_current_user)` and `Depends(get_service)`. Sync `def` endpoints are fine (FastAPI runs them in a threadpool).
- DB access only through `PostgresGateway` methods; routers do not write SQL.
- Errors: raise `HTTPException` with a human-readable `detail`. The app-level middleware turns unknown exceptions into JSON 500.
- Frontend: all HTTP goes through `src/lib/api.js`; components never call `fetch` directly. Errors are `ApiError(status, message)`.
- Existing comments are a mix of English and Roman Urdu. Keep them; add new comments in English.

### 1.6 Commands (use exactly these)

```powershell
# Backend (Windows/PowerShell, from repo root)
cd backend
python -m venv .venv            # only if .venv is missing/broken
.\.venv\Scripts\Activate.ps1
pip install -e . pytest pytest-asyncio
python -m pytest -q             # BASELINE: 56 passed
uvicorn api_main:app --reload --port 8000     # http://localhost:8000/docs

# Frontend (from repo root) — node_modules in the zip came from Windows; always reinstall on another OS
npm ci            # or: npm install
npm run lint      # oxlint
npm run build
npm run dev       # http://localhost:5173
```
On Linux/macOS replace the venv activation with `source .venv/bin/activate`.

### 1.7 Facts verified by experiment (so you do not need to re-prove them, but DO add regression tests)

`SQLGuard.validate()` currently **ALLOWS** all of these (each must be blocked after T1.1):

| Id | Query (tenant placeholder written as `:tenant_id`) | Why it is dangerous |
|---|---|---|
| G1 | `select * from gold.daily_sales d where d.tenant_id = :tenant_id or true` | `OR true` returns every tenant's rows |
| G2 | `... where d.tenant_id = :tenant_id or d.tenant_id <> :tenant_id` | same |
| G3 | `select m.content from gold.daily_sales d, ai.messages m where d.tenant_id = :tenant_id` | comma-join skips the blocked-table check |
| G4 | `select app.get_connection_secret(c.id,'access_token') from silver.orders c where c.tenant_id = :tenant_id` | calls a function that returns decrypted store secrets |
| G5 | `select pg_sleep(9), 1 from gold.daily_sales d where d.tenant_id = :tenant_id` | time-based DoS / probing |
| G6 | `select g from gold.daily_sales d, generate_series(1,100000000) g where d.tenant_id = :tenant_id limit 5` | resource exhaustion |
| G7 | `select * from gold.daily_sales d where true -- d.tenant_id = :tenant_id` | the comment satisfies the "has tenant filter" regex |
| G8 | `select c.name, c.base_url from gold.daily_sales d join control.connections c on true where d.tenant_id = :tenant_id` | reads other tenants' connection names/URLs (`control` schema allowed with no tenant filter) |

And it **wrongly blocks** (false positives) `select d.refresh from gold.daily_sales d where d.tenant_id = :tenant_id` and `... and d.channel = 'update'` because of a keyword regex.

**Functional bug (verified):** `SQLGuard` output keeps a literal `%` (e.g. `ILIKE '%shirt%'`). `execute_readonly_query` passes a params dict to psycopg, and psycopg then raises `ProgrammingError: positional and named placeholders cannot be mixed`. So **any generated query containing `LIKE '%…%'` fails** ("products containing X"). A version with `%%` works. Fixed in T1.1 (step 7).

### 1.8 Known-good things — DO NOT change
- `read_frontend_table` / `count_frontend_table` / `get_frontend_record` in `db.py` and `table_registry.py` (parameterised, allow-listed).
- `_owned_conversation()` ownership checks in `routers/conversations.py` and the conversation/file ownership check inside `AIAnalyst.ask`.
- Credentials are stored via Supabase Vault functions (`app.store_connection_secret`, `app.get_connection_secret`) and never returned by the API.
- `.gitignore` already ignores `.env`, `.venv`, `node_modules`, `dist`, `__pycache__`.

---

## 2. RECONNAISSANCE CHECKLIST (read-only; do this before any edit)

### 2.1 Read these files completely
Backend: `api/app.py`, `api/config.py`, `api/deps.py`, `api/auth.py`, `api/ai_helpers.py`, `api/task_manager.py`, `api/schemas.py`, `routers/{auth,me,tenants,connections,sync,files,conversations,ai,database,subscription}.py`, `platform/{service,settings,sql_guard,ai_analyst,rag}.py`, `platform/db.py` (at least: `__init__`, `connection`, `execute_readonly_query`, `list_connections`, `get_connection`, `create_workspace_for_user`, `usage_summary`, `increment_usage`), `transport/client.py`, `security/ssrf.py`, `core/connector.py`, `discovery/engine.py`, tests: `tests/test_sql_guard.py`, `tests/unit/platform/test_db_readonly.py`, `tests/test_api_contract.py`, `tests/test_required_endpoints.py`.
Frontend: `src/lib/api.js`, `src/context/AuthContext.jsx`, `src/App.jsx`, `src/main.jsx`, `components/workspace/{WorkspaceChat,StoreConnectorsTab,ConnectStoreModal,WorkspaceView,FilesTab}.jsx`.

### 2.2 Answer these questions by grepping (do not assume)
1. Where is `SQLGuard(` constructed and where do `allowed_tables` come from? (`ai_analyst.py` ~line 480–500, built from `ai.query_permissions`.)
2. Every place the strings `control.connections`, `control.platforms`, `app.get_connection_secret` appear (prompts, semantic catalog, rag docs, seed SQL, manifests).
3. Every `async def` endpoint that calls `service.db.*` directly (blocking calls inside the event loop). List them.
4. Where `URLPolicy` / `assert_safe_public_url` is invoked in `core/connector.py` — before **every** request, including pagination "next URL" requests and redirects? Report what you find.
5. Which code uses `usage_summary(...)["connections"]` (frontend `UpgradeModal`/sidebar, `connections.py`, `subscription.py`).
6. Whether any other place creates tenants/workspaces besides `me.py` and `tenants.py`.
7. Which frontend files import `rowsToCsv`/`downloadCsv` or construct CSV.
8. Whether `backend/docs/openapi.json` is generated or hand-edited (affects docs updates).

### 2.3 Post this *Understanding Summary* to the human and wait for "OK"
- 8–12 lines in plain words: what the app does, the request flow for "ask AI", where tenant isolation is enforced.
- Answers to 2.2 (short).
- Anything in this plan that you believe is outdated or risky.
- The baseline result of `python -m pytest -q` and `npm run build`/`npm run lint` (report failures honestly; do not "fix" unrelated failures).

---

## 3. PHASE 0 — Preparation & hygiene (no behaviour change)

### T0.1 Branch and baseline
1. `git switch -c improvements/phase-0`
2. Run backend tests and frontend lint/build; record results.
**Accept:** baseline recorded; working tree clean.

### T0.2 Secrets hygiene (agent part)
**Problem:** `backend/.env` (real keys) was in the shared zip; `backend/.env` sets `FREE_STORE_LIMIT` twice (1 and later 5 — the last wins silently).
**Steps**
1. **Do not open `.env`.** Edit only `backend/.env.example` and root `.env.example`: keep every variable once, add comments, and add the new variables introduced later in this plan (as empty/safe defaults): `ANALYST_DATABASE_URL=`, `MAX_WORKSPACES_PER_USER=3`, `DB_POOL_MAX=10`, `AUTH_CACHE_TTL_SECONDS=30`, `TASK_RETENTION_SECONDS=3600`.
2. Add to `.gitignore` (if missing): `*.zip`, `backend/.pytest_cache/`, `.cursor/` (only if the human does not want it committed — ask).
3. Add `backend/scripts/check_no_secrets.py` (small script: fails if a tracked file matches `gsk_[A-Za-z0-9]{20,}`, `eyJhbGciOi`, `postgres(ql)?://[^:]+:[^@]+@`). Optional: mention `gitleaks` in README.
4. Tell the human: do **H1 (rotate keys)** now, and delete the duplicate `FREE_STORE_LIMIT` line from their own `backend/.env`.
**Accept:** `git grep -nE "gsk_|service_role|eyJhbGci"` shows no real secret in tracked files; example files list each variable once.
**Rollback:** `git revert`.

---

## 4. PHASE 1 — Security-critical fixes (do these first, in this order)

### T1.1 Make AI-generated SQL safe (defence in depth: DB role + RLS + AST guard) ★ highest value

**Why (plain words):** the AI writes SQL from user text, and text can contain hidden instructions ("prompt injection"). Today the only protection is a regex. We add **three layers**: (1) a database user that is *physically unable* to see other tenants or secrets, (2) a real SQL parser instead of regex, (3) fixing the `%` bug.

#### Part A — Database layer (HUMAN runs the SQL; agent only writes it)
Create `backend/scripts/sql/001_analyst_readonly_role.sql`. Before writing it, **ask the human to run this introspection** and paste results (you must not guess):
```sql
select table_schema, table_name,
       bool_or(column_name = 'tenant_id') as has_tenant_id
from information_schema.columns
where table_schema in ('silver','gold')
group by 1,2 order by 1,2;
```
Then write the script following this template (adapt names to the introspection result; keep every statement idempotent and add a header comment *"REVIEW BEFORE RUNNING — creates a role, enables RLS on silver/gold"*):
```sql
-- 1) Role: can log in, cannot write, cannot bypass RLS, hard 10s timeout
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'analyst_ro') then
    create role analyst_ro login password '<<SET_IN_SUPABASE_NOT_IN_GIT>>' nobypassrls noinherit;
  end if;
end $$;
alter role analyst_ro set default_transaction_read_only = on;
alter role analyst_ro set statement_timeout = '10s';
alter role analyst_ro set idle_in_transaction_session_timeout = '15s';

-- 2) Take away everything, then grant only silver/gold usage
revoke all on schema public, app, vault, control, iam, ai, ops, bronze, ingestion from analyst_ro;
grant usage on schema silver, gold to analyst_ro;

-- 3) Per table that HAS tenant_id: select grant + RLS policy bound to a session setting
do $$
declare r record;
begin
  for r in
    select c.table_schema s, c.table_name t
    from information_schema.columns c
    join information_schema.tables tb
      on tb.table_schema=c.table_schema and tb.table_name=c.table_name and tb.table_type='BASE TABLE'
    where c.table_schema in ('silver','gold') and c.column_name='tenant_id'
  loop
    execute format('alter table %I.%I enable row level security', r.s, r.t);
    execute format('grant select on %I.%I to analyst_ro', r.s, r.t);
    execute format('drop policy if exists analyst_tenant_isolation on %I.%I', r.s, r.t);
    execute format($p$create policy analyst_tenant_isolation on %I.%I for select to analyst_ro
                      using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)$p$, r.s, r.t);
  end loop;
end $$;

-- 4) Safe label view so the AI never touches control.* directly (adjust columns after introspection;
--    list_connections() in db.py joins control.connections c with control.platforms p on p.id = c.platform_id)
create or replace view gold.v_connections as
select c.id, c.tenant_id, c.name, p.code as platform_code, p.name as platform_name
from control.connections c join control.platforms p on p.id = c.platform_id
where c.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid;
grant select on gold.v_connections to analyst_ro;
```
Notes for the human (put them in the file header): (a) The backend's normal connection (Supabase `postgres`/service role) is unaffected because it owns the tables / bypasses RLS. (b) If you connect through the Supabase **pooler**, the username must be `analyst_ro.<project-ref>`; URL-encode special characters in the password. (c) After running, set `ANALYST_DATABASE_URL` in `backend/.env` (H3). (d) Rollback script: `001_analyst_readonly_role.rollback.sql` (`drop view`, `drop policy`, `alter table … disable row level security`, `drop role`). **Write the rollback file too.**

#### Part B — Backend wiring (agent)
1. `api/config.py`: add `analyst_database_url: str = ""` to `APISettings` and read `ANALYST_DATABASE_URL` in `from_env()`.
2. `platform/settings.py`: add `analyst_database_url: str = ""` to `PlatformSettings`.
3. `api/deps.py`: **`get_service()` builds `PlatformSettings` field-by-field — add `analyst_database_url=cfg.analyst_database_url`** (easy to forget).
4. `platform/service.py`: `PostgresGateway(settings.database_url, analyst_database_url=settings.analyst_database_url)`.
5. `platform/db.py`: extend `PostgresGateway.__init__(self, database_url, analyst_database_url: str | None = None)`. If provided, create a **second** `ConnectionPool` (`min_size=1`, `max_size=3`, same kwargs). Add `self._analyst_pool`. In `execute_readonly_query`:
   - use the analyst pool when present, otherwise the normal pool and **log one warning** (`"ANALYST_DATABASE_URL not set — AI SQL runs with the main DB role (less safe)"`);
   - keep `set transaction read only` and the `statement_timeout` `set_config`;
   - add `cur.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_id),))` **before** running the query (this is what the RLS policy reads).
   - Keep the method signature; update `tests/unit/platform/test_db_readonly.py` (its fake cursor records `calls`) to also assert the `app.tenant_id` call.
6. `DB_POOL_MAX` env (default 10) — read in `PostgresGateway.__init__` via `os.getenv` (do not break the tests that build the gateway with `__new__`).

#### Part C — Replace the regex guard with an AST guard (agent)
1. Add dependency `sqlglot>=25,<30` to `requirements.txt` and `pyproject.toml`.
2. Rewrite `SQLGuard.validate()` in `platform/sql_guard.py`. **Keep the public API** (`SQLGuard(allowed_tables, max_rows)`, `GuardResult(ok, sql, reason)`, `DEFAULT_ALLOWED_SCHEMAS`, `BLOCKED_TABLES`) so `ai_analyst.py` needs no change.
3. Algorithm (implement exactly; check the sqlglot version's node names with a quick REPL experiment):
   1. Strip markdown fences and one trailing `;`.
   2. Reject if the text contains `--` or `/*` (comments).
   3. Replace the literal `:tenant_id` with the string literal `'__TENANT__'` **before parsing** (sqlglot may not parse `:name`). Reject if `:tenant_id` is absent.
   4. `sqlglot.parse(text, read="postgres")` → must return exactly **one** statement; any parse error → reject with a short reason.
   5. Root must be `exp.Select`/`exp.Union`-family (CTE `WITH … SELECT` is a Select). Reject if the tree contains `Insert, Update, Delete, Merge, Create, Drop, Alter, Command, Into, Lock (FOR UPDATE), Set`, or any `exp.Command`.
   6. **Tables:** collect CTE alias names; for every `exp.Table` that is not a CTE alias require an explicit schema; require `(schema, table)` ∈ allowed set (`allowed_tables` if given, else `silver.*`, `gold.*`) and ∉ `BLOCKED_TABLES`. **Reject the whole `control` schema** except nothing (labels now come from `gold.v_connections`). This also catches comma-joins and quoted names.
   7. **Functions:** reject any `exp.Anonymous` function whose lowercase name is not in an allowlist (`sum, count, avg, min, max, coalesce, nullif, round, ceil, floor, abs, greatest, least, date_trunc, extract, to_char, now, current_date, lower, upper, trim, length, substring, concat, row_number, rank, dense_rank, lag, lead, percentile_cont, string_agg, array_agg, jsonb_extract_path_text`). Typed sqlglot functions (Sum, Count, Coalesce, Cast …) are fine. **Reject set-returning/generator functions**: `exp.Unnest`, `generate_series`, `exp.Explode`, any function starting with `pg_`, `set_config`, `current_setting`, `lo_`, `dblink`, anything in schema `app`/`vault`/`pg_catalog`/`information_schema`.
   8. **Tenant predicate (the core rule):** for every `exp.Select` node, for every silver/gold/`gold.v_connections` table in its own `FROM`/`JOIN`, require a **top-level AND-conjunct** of that Select's `WHERE` (or that join's `ON`) of the form `<alias_or_table>.tenant_id = '__TENANT__'` (unqualified `tenant_id` allowed only when the Select has a single table). Flatten `exp.And`; a conjunct inside an `OR` does **not** count. (Fixes G1, G2, G7, G8.)
   9. **Limit:** if the root has no `LIMIT`, add `LIMIT max_rows`; if it exceeds `max_rows`, lower it. Do this on the AST (`root.limit(...)`), not by appending text.
   10. **Emit:** `executable = root.sql(dialect="postgres")`, then **escape `%` → `%%` first**, then replace `'__TENANT__'` with `%(tenant_id)s`. (Fixes the `LIKE '%…%'` bug.)
4. Keep human-readable `reason` strings (they are shown to users and stored in `ai.generated_queries.blocked_reason`).
5. **Tests** (`backend/tests/test_sql_guard.py` — keep all existing tests passing, add):
   - must-BLOCK: G1–G8 from section 1.7; `select 1; select 2`; `insert …`; `select … for update`; `select * into x from silver.orders …`; `with a as (select * from ai.messages) select * from gold.daily_sales d where d.tenant_id=:tenant_id`; query without `:tenant_id`; query referencing `pg_catalog.pg_tables`.
   - must-ALLOW: the normal KPI query; join of two silver tables each with its own alias filter; CTE query; a `UNION ALL` where both branches are filtered; `d.refresh` column; `'update'` string literal; `LIKE '%shirt%'` and assert the emitted SQL contains `%%shirt%%`; a query already containing `LIMIT 10`; `date_trunc('day', d.metric_date)`.
   - emitted SQL must be accepted by psycopg's query converter: `PostgresQuery(adapt.Transformer()).convert(sql, {"tenant_id": "x"})` must not raise.
**Accept:** all new + existing tests green; manual: ask the chat "show products containing shirt" works; G1–G8 rejected.
**Verify (human, H5):** with two accounts A and B, A asks "show all sales of every tenant" / pastes a prompt-injection sentence in an uploaded file; A must never see B's numbers. Then (after Part A SQL is applied) temporarily run `select count(*) from gold.daily_sales` as `analyst_ro` with `app.tenant_id` unset → **0 rows**.
**Rollback:** code: `git revert`. DB: run the rollback `.sql`. If `ANALYST_DATABASE_URL` is empty the code falls back to the old pool, so the app keeps working before the SQL is applied.
**Update** the `PLAN_SYSTEM` prompt in `ai_analyst.py`: remove "control.connections/platforms may be joined" and say labels come from `gold.v_connections`; also grep rag/semantic-catalog documents for `control.connections` and update them (then the human re-runs *Rebuild RAG*).

### T1.2 SSRF: validate every redirect hop and never leak tokens cross-host
**Problem (plain words):** the URL check happens once; then `httpx` follows redirects automatically. An attacker site can redirect to `http://169.254.169.254` (cloud-internal) or to another host, and custom auth headers such as `X-Shopify-Access-Token` are **not** removed by httpx on cross-host redirects (only `Authorization` is).
**Files:** `transport/client.py`, `discovery/engine.py`, `security/ssrf.py`, `core/connector.py` (read first).
**Steps**
1. Verify (2.2 #4) that `URLPolicy.validate(url)` runs before each outgoing request incl. pagination URLs. If a path skips it, add it.
2. In both httpx clients set `follow_redirects=False`. Implement a small helper `send_with_safe_redirects(client, request_kwargs, policy, max_hops=5)`: on `301/302/303/307/308` read `Location`, resolve relative URL, run `policy.validate(new_url)`, **refuse if the host differs from the original host** (log a warning) unless the request carried no credentials, then re-send (method rules: 303 → GET). Allow same-host `http→https` upgrades.
3. In `ssrf.py` also treat IPv4-mapped IPv6, `0.0.0.0/8`, carrier-grade NAT `100.64.0.0/10` as blocked (use `ipaddress` flags + explicit networks), and **fail closed** when DNS resolution fails (currently `except socket.gaierror: return` lets it through).
4. Tests in `tests/unit/security/test_ssrf.py`: redirect to `http://127.0.0.1` rejected; cross-host redirect with auth header rejected; same-host https upgrade followed; DNS failure rejected; use `httpx.MockTransport` (no real network).
**Accept:** tests green; connecting a normal Shopify/Woo store still works (human check).
**Rollback:** `git revert`. **Risk:** some stores legitimately redirect to a canonical domain — if the human reports failures, add an explicit per-manifest `allowed_redirect_hosts` list instead of disabling the check.

### T1.3 Add tenant check to background-task status + clean up memory
**Problem:** `GET /sync/tasks/{task_id}` only requires login; any user with a task id can read it. `TASKS` also never deletes finished tasks (memory leak) and forgets everything on restart.
**Files:** `api/task_manager.py`, `routers/sync.py`.
**Steps**
1. `TaskState`: add `tenant_id: str | None = None`, `user_id: str | None = None`.
2. `BackgroundTaskManager.submit(factory, *, tenant_id=None, user_id=None)`; store them. Add `prune()` removing finished states older than `TASK_RETENTION_SECONDS` (default 3600); call it at the start of `submit`. Also drop the finished `asyncio.Task` handle from `self._tasks`.
3. `sync.py → run_sync_background`: pass `tenant_id` and `current_user.id`.
4. `sync.py → get_task`: inject `service=Depends(get_service)`; if `state.tenant_id` is missing or the caller is not a member → **404** (not 403, to avoid confirming the id exists).
5. Do **not** change the JSON field names the frontend polls (`status`, `result`, `error`).
**Tests:** new `tests/test_sync_tasks_authz.py` using FastAPI `TestClient` with dependency overrides: member sees the task, non-member gets 404, unknown id 404.
**Accept:** tests green; frontend sync polling still works.
**Rollback:** `git revert`.

### T1.4 Stop leaking internal errors; stream uploads with a hard size cap
**Problem:** some endpoints return `str(exc)` (database/internal details) to the browser; `files.upload` reads the whole file into RAM **before** checking the size (a 2 GB upload can crash the server).
**Files:** `routers/{me,tenants,files,database}.py`, `api/app.py`.
**Steps**
1. `me.py` and `tenants.py` workspace creation: catch `psycopg.errors.UniqueViolation` → `409 "Workspace slug already taken"`; catch `ValueError` → `400` with its message (these are our own messages); everything else → log with `logger.exception` and raise `HTTPException(500, "Could not create workspace")`.
2. `files.py → upload_file`: replace `data = await upload.read()` with chunked reading (1 MiB chunks) that raises `413` as soon as the running size exceeds `service.settings.max_user_file_bytes`. Also reject early if `Content-Length` header (when present) is larger. Replace the generic `except Exception → detail=str(exc)` by logging + `"File upload failed"`.
3. `database.py → _translate_error`: keep `KeyError → 404`; `ValueError → 400` (our messages); any other exception → log + `500 "Query failed"` (not `400 str(exc)`).
4. Keep message wording for already user-friendly errors.
**Tests:** upload slightly above the limit → 413 and memory not read fully (use a small `MAX_USER_FILE_BYTES` via settings override); duplicate slug → 409.
**Accept:** tests green.

### T1.5 CSV formula-injection protection (frontend)
**Problem:** a customer named `=HYPERLINK("http://evil","x")` runs as a formula when the exported CSV is opened in Excel.
**Files:** `src/components/workspace/WorkspaceChat.jsx` (`rowsToCsv`, `downloadCsv`).
**Steps**
1. Move CSV helpers to `src/lib/csv.js` (`rowsToCsv`, `downloadCsv`) and import them in `WorkspaceChat.jsx`.
2. In the cell escaper: if the string starts with `=`, `+`, `-`, `@`, tab or carriage-return, prefix it with `'`. Keep the existing `""` quote-doubling. Keep numbers as numbers (do not prefix negative numeric values; only prefix when the **original value is a string**).
3. Add a UTF-8 BOM only if the human asks (Excel/Urdu text) — otherwise leave behaviour unchanged.
4. (Phase 5 adds a unit test for this.)
**Accept:** export of rows with a `=1+1` cell shows the text `'=1+1`; normal numbers unchanged.

---

## 5. PHASE 2 — Business-logic fixes (plan limits, deletion)

### T2.1 Limit how many workspaces a user can create (free-plan bypass)
**Problem:** `POST /me/workspaces` and `POST /tenants` have no limit; every new workspace is a new "free" plan with its own free store/AI limits.
**Needs decision H4-1** (Section 8). Default implemented here: **cap = `MAX_WORKSPACES_PER_USER` (default 3)** counted as tenants where `created_by = user` (or `role='owner'` memberships — confirm with the human which column is authoritative).
**Steps**
1. `config.py`: `max_workspaces_per_user` from env (default 3).
2. `db.py`: `count_owned_workspaces(user_id) -> int` (`select count(*) from iam.tenant_members where user_id=%s and role::text='owner' and status::text='active'`).
3. `me.py` and `tenants.py`: before creating, if count ≥ limit → `HTTPException(402, "Workspace limit reached for this account")`.
4. **Must not break the auto-created first workspace** in `AuthContext.loadMe()` — the first workspace is count 0, always allowed.
5. Frontend: `AuthContext` already surfaces errors; no UI change needed, but make sure a `402` during bootstrap shows a message rather than a blank screen (see T4.2).
**Tests:** creating workspace #limit+1 → 402; first workspace OK.
**Out of scope (note in PR):** moving the plan to the *account* level instead of per workspace — larger product change.

### T2.2 Allow deleting a connection and count only live connections
**Problem:** there is no delete endpoint; a failed/typo connection permanently uses the single free slot (`usage_summary()["connections"]` counts every row in `control.connections`).
**Before coding, ask the human to run and paste:**
```sql
select column_name, data_type, udt_name from information_schema.columns
where table_schema='control' and table_name='connections' order by ordinal_position;
select conname, confrelid::regclass, confdeltype from pg_constraint where confrelid='control.connections'::regclass;
select enumlabel from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname like '%connection%status%';
```
**Steps (choose based on the result):**
1. If a soft-delete column exists (`deleted_at`/`archived_at`) → prefer soft delete. Else, if `status` enum has a suitable value (`disabled`/`archived`) → use it. Else hard delete only if the FKs are `ON DELETE CASCADE`/safe — otherwise stop and ask.
2. `db.py`: `delete_connection(connection_id)` (soft or hard per step 1) and also remove its Vault secrets via the existing `app.*` function if one exists (grep `scripts/` and `docs/`; if none, ask).
3. `routers/connections.py`: `DELETE /connections/{connection_id}` → `_guard_connection(...)`, call `delete_connection`, return `204`. Reject if a sync job for it is currently running (check `ingestion.sync_jobs` status via an existing `db` method; otherwise skip and note it).
4. `db.usage_summary`: make `connections` count only non-deleted rows. **Keep the key name `connections`.**
5. Frontend: `api.js` add `deleteConnection: (id) => request(`/connections/${id}`, { method: 'DELETE' })`; `StoreConnectorsTab.jsx` add a "Remove" button with a `window.confirm` and refresh the list.
**Tests:** delete as member → 204 and count drops; delete as non-member → 403; deleting another tenant's connection → 403.
**Accept:** after deleting a broken connection a free user can connect a new store.

---

## 6. PHASE 3 — Reliability & performance

### T3.1 Cache the Supabase user lookup (and optionally verify JWT locally)
**Problem:** `get_current_user` calls Supabase `/auth/v1/user` for **every** API request (a page load = 6–8 extra network calls; rate-limit risk).
**Files:** `api/auth.py`, `api/config.py`.
**Steps (T3.1a — do this):**
1. Add a tiny in-process TTL cache: `dict[sha256(token)] -> (expires_at, raw_user_dict)`, TTL = `AUTH_CACHE_TTL_SECONDS` (default 30, hard max 60), max 1000 entries, guarded by a `threading.Lock`; evict expired entries opportunistically.
2. Cache only **successful** lookups. Never cache failures.
3. On `POST /auth/logout`, delete that token's cache entry.
4. Never log tokens; key by hash only.
**Steps (T3.1b — optional, only if the human agrees):** local JWT verification with `PyJWT` using Supabase's JWKS (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, cache the keys 1 h) or the legacy HS256 secret if the project still uses it; verify `exp`, `aud=authenticated`, `iss`. Keep T3.1a as the fallback. Ask the human which signing mode the Supabase project uses.
**Tests:** monkeypatch `SupabaseAuthClient.user` with a counter: 5 calls with same token within TTL → 1 upstream call; after TTL → 2; after logout → upstream again.
**Accept:** network tab shows no per-request Supabase round trip in backend logs.

### T3.2 Stop blocking the event loop; make the DB pool configurable
**Problem:** `async def` endpoints (`sync.run`, `sync.background` pre-checks, `connections.test_connection`, `files.upload/delete`) call **blocking** `service.db.*` functions. While one runs, *all* other requests wait. Also the pool max is hard-coded to 10 while FastAPI can run 40 sync endpoints concurrently → "pool timeout" under load.
**Steps**
1. Use the list from reconnaissance (2.2 #3). For each listed endpoint, either (a) change `async def` → `def` when it does **not** `await` anything, or (b) keep `async def` and wrap each blocking call: `await asyncio.to_thread(service.db.get_connection, connection_id)`.
2. `connections.test_connection` is `async` because `service.test_connection` is awaited; wrap the `_guard_connection(...)` call with `to_thread`. Inside `service.test_connection` and `orchestrator.py`, wrap blocking `self.db.*` calls similarly **only where profiling shows they are on the hot path**; do not refactor the orchestrator wholesale.
3. `PostgresGateway`: `DB_POOL_MAX` env (already added in T1.1 step 6); also pass `timeout=10` to `ConnectionPool` so waiting fails fast with a clear 503 instead of hanging 30 s.
**Tests / verification:** write `tests/test_event_loop_not_blocked.py` that starts a fake slow DB call (time.sleep 1 s) through the patched endpoint while hitting `/health` concurrently with `httpx.AsyncClient` + `ASGITransport`; `/health` must answer in < 300 ms.
**Accept:** while a store sync runs, `/api/v1/health` and chat requests from another user stay responsive (human check).

---

## 7. PHASE 4 — Frontend correctness

### T4.1 Prevent two workspaces being created for a brand-new user
**Problem:** `main.jsx` uses `React.StrictMode`; in development effects run twice, so `loadMe()` runs twice concurrently, both see "no workspace" and both create one. Two browser tabs can do the same.
**Files:** `src/context/AuthContext.jsx`, backend `routers/me.py`, `platform/db.py`.
**Steps**
1. Frontend: keep a module-level `let loadMePromise = null;` and make `loadMe` return the in-flight promise if one exists (clear it in `finally`).
2. Backend (recommended): add `POST /me/bootstrap` that returns the user's first workspace or creates one **atomically**: inside one transaction run `select pg_advisory_xact_lock(hashtext(%s))` with the user id, re-check `list_user_workspaces`, then create if still empty. Return `{workspace}`. Frontend `loadMe` calls this instead of `createWorkspace` when `me.workspaces` is empty. Respect T2.1 (the first workspace is always allowed).
**Tests:** backend: call bootstrap twice concurrently (threads) → exactly one workspace.
**Accept:** new signup in dev (StrictMode) creates exactly one workspace.

### T4.2 Don't log the user out on temporary errors; add an error boundary
**Problem:** `loadMe().catch(() => sessionStore.clear())` logs the user out on *any* failure (backend restarting, Wi-Fi blip). A crash in any component produces a blank white screen.
**Steps**
1. `AuthContext`: in the `.catch`, clear the session **only if** `err instanceof ApiError && err.status === 401`. Otherwise keep the session, set `bootError` (new context value) and render a small "Server not reachable — Retry" screen in `App.jsx` (retry calls `loadMe()` again).
2. Create `src/components/ui/ErrorBoundary.jsx` (class component with `componentDidCatch`, friendly message + "Reload" button). Wrap `<App/>` in `main.jsx` and wrap `WorkspaceView` separately in `App.jsx`.
3. `React.lazy` + `Suspense`: lazy-load `WorkspaceView` and `AuthPage` (`const WorkspaceView = lazy(() => import(...))`) so the landing page bundle shrinks. Provide a simple loading fallback (existing `.auth-loading` class).
**Accept:** stopping the backend while logged in shows the retry screen, not the login page; restarting + Retry restores the session. `npm run build` shows a separate chunk for the workspace.

### T4.3 Remove fake/dead UI and make quick prompts truthful
**Problem:** store chips (Amazon/eBay/…) are decoration (never sent to the backend); "Reasoning" steps are a fake timer; the `+` and image buttons do nothing; `QUICK_PROMPTS` suggest things the backend cannot do (buy-box win rate, abandoned checkout, CRM sync…).
**Steps**
1. `api.js`: add `prompts: (tenant_id, category) => request('/prompts', { query: { tenant_id, category } })` (backend route exists: `routers/prompts.py`).
2. `WorkspaceChat.jsx`: replace the hard-coded `QUICK_PROMPTS` with prompts from `api.prompts(tenantId)` (fallback to a short static list of 4 prompts that the backend demonstrably supports: total revenue, sales by day, top products by revenue, compare last 30 days vs previous 30). Remove `STORES`/`MORE_STORES` chips **or** replace them with the platforms from `api.connections(tenantId)` (read-only badges "Connected: Shopify"). Do not send a store filter the backend ignores.
3. Replace the fake step ticker texts with one honest status: "Analysing your data…" (or implement streaming in T4.4).
4. `+` and image buttons: either remove them or implement attach-file (upload via existing `api.uploadFile`, keep returned ids in state, include `file_ids` in `api.sendMessage` body — the backend already accepts `file_ids`, max 20). Default: **remove the image button, implement `+` as file attach** if time allows; otherwise remove both.
5. Keep CSS class names unless the element is deleted; remove dead CSS only if clearly unused.
**Accept:** every visible control does something real; quick prompts all return answers on a store with synced data (human check).

### T4.4 (Optional) Real streaming status via SSE
Backend already has `POST /conversations/{id}/stream` emitting `started → status → result → done|error`. Implement `api.streamMessage(id, body, onEvent)` with `fetch` + `ReadableStream` (not `EventSource`, because it cannot send POST/Authorization), reuse the 401-refresh logic, parse `event:`/`data:` lines, and use `status.stage` for the progress label. Keep `sendMessage` as fallback if streaming fails. Do this only after T4.1–T4.3 are done.

---

## 8. PHASE 5 — Quality, docs, CI & decisions

### T5.1 Tests & CI
1. Frontend: add `vitest` (devDependency) and `src/lib/csv.test.js` covering: plain cell, comma/quote cell, `=1+1` string → prefixed, numeric `-5` unchanged, `null` → empty/`—` per existing behaviour. Add `"test": "vitest run"` script.
2. Add `.github/workflows/ci.yml`: job **backend** (Python 3.12, `pip install -e . pytest pytest-asyncio`, `pytest -q` in `backend/`), job **frontend** (Node 22, `npm ci`, `npm run lint`, `npm test`, `npm run build`), job **secrets** (`python backend/scripts/check_no_secrets.py`).
3. Do not make CI depend on real secrets or network.

### T5.2 Docs & naming
1. `README.md`: add a **Backend** section (setup, env vars table from `.env.example`, `uvicorn api_main:app`, tests, architecture diagram in text), and a **Security notes** section describing the analyst role/RLS (T1.1).
2. `DEBUG_FIX_REPORT.md` still talks about Gemini although code uses Groq: add a banner line "Historical — LLM provider is now Groq" and move it to `backend/docs/history/`.
3. `INTEGRATION_GUIDE.md`: update the "still pending" list as tasks complete (streaming, delete connection, file attach).
4. **Naming is inconsistent** (README "NexusCommerce", guide "MerchLayer", package `nexus-commerce`). **Do not pick** — see decision H4-3.
5. Regenerate/refresh `backend/docs/openapi.json` only if reconnaissance 2.2 #8 shows it is generated (e.g. `python -c "import json; from commerce_connector.api.app import app; print(json.dumps(app.openapi()))"`).

### Decisions needed from the human (agent: ask, do not guess)
| Id | Question | Default if human says "your call" |
|---|---|---|
| H4-1 | Free-plan rule: per workspace (today) or per account? Max workspaces per user? | Keep per workspace; cap 3 workspaces |
| H4-2 | Delete connection: soft or hard delete? | Soft delete if the column exists |
| H4-3 | Product name: NexusCommerce or MerchLayer? | Do nothing until answered |
| H4-4 | Local JWT verification (T3.1b) or cache only? | Cache only |
| H4-5 | Implement file-attach and streaming (T4.3-4, T4.4) now or later? | Later |
| H4-6 | Should viewers/members have fewer rights than owners (roles)? | Not in this plan |

### Explicitly OUT of scope (mention in final report as "next steps")
Role-based permissions (owner/admin/viewer), moving auth tokens from `localStorage` to httpOnly cookies, persistent job queue (Redis/RQ/Celery instead of in-memory `TASKS`), account-level billing, TypeScript migration, full line-by-line audit of the connector engine modules (`discovery/`, `pagination/`, `protocols/`, `silver.py`).

---

## 9. PER-TASK REPORT CHECKLIST (agent pastes this after every task)

```
Task: T_._  — <title>
[ ] Branch/commit: <name / sha>
[ ] Files changed: <list>
[ ] New/updated tests: <list>
[ ] Backend:  python -m pytest -q  → <N passed / failures>
[ ] Frontend: npm run lint → <ok/err>   npm run build → <ok/err>   (if frontend touched)
[ ] No secrets printed or committed
[ ] No existing API field renamed/removed (or: docs/frontend updated)
[ ] Manual verification steps I could NOT do (for the human): <list>
[ ] Risks / things I was unsure about: <list>
[ ] Rollback: <how>
```

## 10. FINAL DEFINITION OF DONE (whole plan)

- [ ] Keys rotated (H1) and no secrets in tracked files; `.env.example` complete.
- [ ] G1–G8 blocked, `LIKE '%…%'` works, analyst role + RLS in place (or fallback warning logged), tests added.
- [ ] Redirect/SSRF protections tested; `/sync/tasks` tenant-checked; uploads capped; no `str(exc)` leaks.
- [ ] Workspace cap and connection deletion work; free-plan users can recover from a bad connection.
- [ ] Auth lookup cached; event loop not blocked; pool configurable.
- [ ] Single workspace per new user; temporary errors do not log users out; error boundary + lazy loading in place.
- [ ] No fake UI controls; CSV export safe.
- [ ] CI (backend tests, frontend lint/test/build, secret scan) green; README/docs updated.
- [ ] Two-account manual isolation test (H5) passed.