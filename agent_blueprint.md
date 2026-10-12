# ROLE
You are a Senior Backend Engineer and Software Architect doing a pre-deployment audit and fix of this project. Work like a careful reviewer: find real problems with evidence, fix them safely, and prove the fixes work.

# PROJECT CONTEXT
- Project: shopify-ai-analytics-platform (Universal Commerce DB)
- Stack: Python, FastAPI backend, Supabase Postgres + Auth, Bronze/Silver/Gold data pipeline, an AI/LLM layer that turns natural-language questions into governed SQL/dashboards (semantic metric layer + RAG), React/Vite frontend (port 5173).
- Backend run command: `uvicorn api_main:app --reload --port 8000`
- Source of truth for the data model: universal_commerce_supabase_complete_final.sql and universal_commerce_full_erd.drawio (if they are in the repo or docs, use them).
- OS/shell: Windows, PowerShell. Use PowerShell-compatible commands only.
- I am a backend intern. This backend will be handed to my boss for deployment, so it must be correct, secure and stable. The frontend is owned by a separate engineer.

# THE BUG THAT TRIGGERED THIS TASK
User prompt in the dashboard:
"Give me a full sales overview for the last 30 days including total revenue, number of orders, average order value, and top-selling products broken down by category."

Error returned:
"Invented metric expression SUM(ds.net_sales) is not allowed because metric 'average_order_value' is defined as case when sum(orders_count)=0 then null else sum(net_sales)/sum(orders_count) end."

Initial understanding (VERIFY, do not assume): the metric/semantic validation layer rejects the AI-generated query because it re-implements or approximates a governed metric (average_order_value) with its own expression instead of using the registered metric definition. Find out exactly why the validator fired, whether the validator, the metric registry, the LLM prompt/context, or the query planner is at fault, and fix the ROOT CAUSE. Do NOT just disable or loosen the validator to make the error disappear.

# WORKING RULES
1. Do NOT git commit or push. Do NOT delete or rewrite production data. Do NOT print or log secrets (Supabase keys, shpat_ tokens, JWTs).
2. Do NOT drop tables or run destructive SQL. Any migration must be a new, reversible SQL file, clearly named, and NOT applied automatically; show me the file for review.
3. Every finding must include evidence: file path, line numbers, and a short code snippet or command output. No vague claims.
4. Do not invent features. Fix what is broken or risky; list nice-to-haves separately.
5. Keep changes small, focused and consistent with the existing code style. Do not refactor unrelated code.
6. If something is ambiguous or needs my decision (for example schema choices, secrets, business definitions), list it under "Questions for me" instead of guessing.

# PHASE 1: ANALYSIS (READ-ONLY, make no code changes yet)
Map the whole backend first (entry point, routers, services, pipeline, AI/RAG layer, DB access, config, auth). Then audit these areas:

A. The reported bug
   - Trace the full path: user prompt -> LLM/query generation -> metric/semantic validation -> SQL execution -> dashboard response.
   - Find where "Invented metric expression" is raised and what rules it uses.
   - Check the metric registry: is `total_revenue` (or equivalent), `orders_count`, `average_order_value` defined? Are names/aliases consistent between the registry, the SQL views (daily_sales etc.) and the LLM prompt?
   - Check whether the LLM is given the metric catalog and told to use metrics by name instead of writing raw aggregations.
   - Check how a multi-part request (revenue + orders + AOV + top products by category) is handled: it needs different grains (daily totals vs product/category level). Confirm the Gold layer has the tables/views needed (for example product and category level sales) and that the planner can combine several queries.
   - Check "last 30 days" date handling: timezone, inclusive or exclusive boundaries, and whether data exists in that range.
   - Check how AOV is aggregated across multiple days (it must be sum(net_sales)/sum(orders_count), never an average of daily averages).

B. Data layer and pipeline
   - Bronze -> Silver -> Gold correctness: joins, duplicates, null handling, currency, refunds/cancellations/discounts in net_sales, idempotent re-sync (duplicate key errors, upserts), multi-tenant filtering (tenant_id on every query).
   - Compare the code against the SQL schema/ERD: wrong column names, missing columns, type mismatches, missing indexes on heavily filtered columns (tenant_id, date, order_id).

C. AI / RAG / SQL safety
   - Generated SQL must be read-only (SELECT only), allow-listed to approved tables/views, always tenant-scoped, with LIMIT and statement timeout.
   - Check for SQL injection, prompt injection, and any path where the LLM output reaches the DB unvalidated.
   - Check error handling: when validation fails, does the system retry with the error fed back to the LLM (bounded retries), or fall back to a deterministic template for common requests like a sales overview, or does it just crash?

D. API quality and security
   - Auth: JWT validation, Supabase service-role key never exposed to the client, row-level security / tenant isolation, CORS config, rate limiting.
   - Request/response validation (Pydantic), consistent error format and HTTP status codes, no stack traces leaked to clients.
   - Async/blocking issues, connection pooling, timeouts, pagination.

E. Production readiness
   - Config via environment variables, `.env.example` completeness, no hardcoded secrets, logging with request IDs, health-check endpoint, dependency pinning (`requirements.txt`), Docker/deployment readiness, test coverage.

F. Run it
   - Install dependencies, start the backend, run existing tests, hit the main endpoints (use a test tenant/token if available) and reproduce the reported error with the exact prompt above. Record real outputs.

Classify every finding as: CRITICAL (blocks deployment or breaks function), HIGH, MEDIUM, LOW. Give each an ID (for example BE-001).

# PHASE 2: PLAN (this is the /plan step)
Produce an implementation plan as an artifact BEFORE changing code:
- Root-cause explanation of the reported bug in simple words.
- A table of all findings: ID, severity, file, problem, proposed fix, risk, effort.
- Ordered fix list (CRITICAL first), with the files you will touch and how you will test each fix.
- "Questions for me" list.
- Stop and wait for my approval of the plan before Phase 3.

# PHASE 3: IMPLEMENT (after I approve the plan)
- Fix the reported bug at the root cause. The final behavior must be: the sales overview prompt returns total revenue, order count, AOV (using the governed metric definition), and top-selling products by category for the last 30 days, with correct numbers.
- Fix all CRITICAL and HIGH issues. Fix MEDIUM issues that are low-risk. Put the rest in the report as a backlog.
- Add automated tests (pytest):
  1. Regression test with the exact failing prompt/metric combination.
  2. Validator tests: using the governed AOV metric must pass; inventing a different AOV formula must fail with a clear message.
  3. Date-range test for "last 30 days".
  4. Tenant isolation test.
  5. Read-only SQL safety tests.
- Run the full test suite and the app again. Show before/after results.

# PHASE 4: DELIVERABLES (create these files in the repo under /docs/audit/)
1. BACKEND_AUDIT_REPORT.md: all findings, evidence, what was fixed, what remains, and test results.
2. CHANGELOG_FIXES.md: each change with file names and why.
3. FRONTEND_HANDOFF.md: written for the frontend engineer in simple language. Include:
   - Every API endpoint the frontend uses: method, URL, request body, response shape, example JSON, error formats and status codes.
   - Required headers/auth flow (token handling, refresh, 401/403 behavior).
   - How the dashboard response is structured (KPI cards, charts, tables) and how each chart/KPI type should be rendered.
   - Frontend problems found (wrong payloads, missing loading/error/empty states, bad error display, hardcoded URLs, CORS-related issues, state handling bugs), each with file/line, the issue, and the exact fix to apply.
   - A checklist the frontend engineer can tick off.
4. DEPLOYMENT_CHECKLIST.md: env vars needed, run commands, migrations to apply (in order), health checks, and a smoke-test script my boss can run.
5. SUMMARY.md: one page with "Is the backend ready to deploy? YES/NO", remaining risks, and next steps.

# DEFINITION OF DONE
- The original failing prompt works end to end with correct numbers.
- All tests pass and no CRITICAL/HIGH issue remains open.
- Findings, fixes and the frontend handoff guide exist as files.
- You clearly state what you verified by running it versus what you only reviewed by reading.

Start with Phase 1 now. Do not change code until I approve the Phase 2 plan.