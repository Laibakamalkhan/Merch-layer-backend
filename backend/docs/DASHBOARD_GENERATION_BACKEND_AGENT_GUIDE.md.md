# Dashboard Generation Backend Improvement Guide

## Purpose

This document is the implementation contract for an AI coding agent working on the backend of the current web app.

The goal is to improve the **AI-generated analytical dashboard backend** so that:

- the LLM helps understand intent and choose an analytical plan;
- **all numerical values shown to the user come from verified database query results**;
- the LLM is never the source of numerical truth;
- dashboard KPIs/charts are selected from verified metrics and data characteristics;
- dashboard specifications cannot reference columns/data that were not returned by the executed query;
- tenant isolation, SQL safety, RAG, Supabase/PostgreSQL, and existing ingestion behavior remain intact;
- the backend exposes a clean, frontend-friendly dashboard contract;
- internal SQL/debug traces remain available for engineering/operations but are not part of the normal end-user dashboard response.

This is a **backend-only implementation task**. Do not modify frontend code during the implementation phase except when a frontend contract/test fixture is needed to document compatibility. A separate frontend handoff must be produced after backend completion.

---

# 1. Core product principle

## Golden rule

> **The LLM is an analytical planner, not the source of numerical truth. PostgreSQL/Supabase is the source of truth for all displayed analytical values.**

The normal user flow must be:

```text
User question
    -> AI interprets intent
    -> AI selects verified metrics/dimensions
    -> AI generates one read-only SQL query
    -> SQL guard validates it
    -> PostgreSQL/Supabase executes it
    -> backend validates returned data
    -> backend generates verified dashboard data/spec
    -> frontend only renders backend output
```

Never use this pattern:

```text
User question
    -> LLM invents/calculates number
    -> frontend displays LLM number
```

The system may still use an LLM after the database query to generate human-readable wording or choose among allowed visualization candidates, but **the LLM must not create or recalculate dashboard numbers**.

Do not show users an AI-vs-database disagreement. The user should see only the final verified result.

---

# 2. Current backend state to preserve

The current repository already contains several useful components. Do not replace them with a new architecture unless code inspection proves they are insufficient.

## Existing dataset ingestion

Relevant files:

- `backend/src/commerce_connector/api/routers/datasets.py`
- `backend/src/commerce_connector/platform/datasets/parsers.py`
- `backend/src/commerce_connector/platform/datasets/profiler.py`
- `backend/src/commerce_connector/platform/datasets/ingestor.py`
- `backend/src/commerce_connector/platform/datasets/validator.py`

Current capabilities include:

- CSV parsing
- XLSX parsing through `openpyxl`
- JSON parsing
- upload security validation
- dataset profiling
- suggested mappings
- natural-key/duplicate detection
- Bronze -> Silver -> Gold ingestion flow

The dataset upload API is:

```text
POST /api/v1/datasets/upload
```

Ingestion is:

```text
POST /api/v1/datasets/{dataset_id}/ingest
```

## Existing AI analytics flow

Relevant files:

- `backend/src/commerce_connector/platform/ai_analyst.py`
- `backend/src/commerce_connector/platform/rag.py`
- `backend/src/commerce_connector/platform/sql_guard.py`
- `backend/src/commerce_connector/platform/db.py`
- `backend/src/commerce_connector/api/routers/ai.py`
- `backend/src/commerce_connector/api/routers/dashboards.py`

Current high-level flow is already:

```text
question
 -> RAG retrieval
 -> planner LLM
 -> SQLGuard
 -> readonly DB query
 -> final LLM
 -> dashboard normalisation
 -> save dashboard spec
```

That is a useful base. Improve it rather than creating a second AI analytics pipeline.

## Existing semantic catalog

`PostgresGateway.semantic_catalog_snapshot()` already exposes:

- Silver/Gold columns
- `ai.metric_definitions`
- tenant connections
- `ai.query_permissions`

This should become the main semantic source for the AI planner.

Do not create an unrelated parallel semantic system if the existing one can be extended safely.

## Existing dashboard persistence

Current persistence uses:

- `ai.query_runs`
- `ai.generated_queries`
- `ai.dashboard_specs`

Keep these tables/use cases intact unless a migration is required.

## Existing safety tests

There are already tests for:

- SQL guard and tenant isolation
- dataset parsers
- dataset profiler
- dataset ingestion
- AI contract/dashboard normalisation
- embeddings

Examples:

```text
backend/tests/test_sql_guard.py
backend/tests/unit/test_ai_contract.py
backend/tests/unit/test_dataset_parsers.py
backend/tests/unit/test_dataset_profiler.py
backend/tests/unit/test_dataset_ingestion.py
backend/tests/unit/platform/test_ai_contract.py
backend/tests/unit/platform/test_db_readonly.py
```

All existing tests must continue to pass.

---

# 3. Important current problem

The current `AIAnalyst.ask()` still returns internal analytics data in the normal response, including:

- `sql`
- raw `rows`
- `reasoning`

The current frontend currently consumes those fields for rendering/debugging. This is an existing contract and must be handled deliberately.

For the improved backend:

### User-facing response

Return only the information required to render the verified dashboard and answer the user.

Recommended shape:

```json
{
  "conversation_id": "...",
  "query_run_id": "...",
  "answer": "...",
  "dashboard_id": "...",
  "dashboard": {
    "title": "Sales Overview",
    "kpis": [],
    "charts": [],
    "filters": []
  }
}
```

### Internal/debug information

SQL, execution metadata, raw query rows, validation decisions, RAG context IDs and model information should remain in:

- database audit tables;
- backend logs;
- internal/admin-only endpoints if needed.

Do not expose raw SQL/query rows in the normal user-facing response unless the product explicitly adds a secure developer/admin feature later.

### Compatibility rule

Do not simply delete `sql`/`rows` and break the frontend without documenting the contract change.

Instead:

1. implement the backend's new canonical dashboard response;
2. update API schemas/tests;
3. document the breaking/changed response clearly;
4. add a versioned endpoint or compatibility mode if needed;
5. produce the frontend handoff document.

Do not modify the frontend during this backend task.

---

# 4. Target backend architecture

The target flow should be:

```text
                         USER QUESTION
                               |
                               v
                     +--------------------+
                     | Intent Understanding|
                     |      (LLM)          |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | Semantic Catalog    |
                     | metrics/dimensions  |
                     | entity/relationships|
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | Metric Resolver     |
                     | verified definitions|
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | SQL Planner (LLM)   |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | SQL Guard           |
                     | readonly + tenant   |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | PostgreSQL/Supabase |
                     | source of truth     |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | Result Validator    |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | Visualization Rules |
                     | + Dashboard Planner |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | Dashboard Validator |
                     +---------+----------+
                               |
                               v
                     +--------------------+
                     | Canonical Dashboard |
                     | Response            |
                     +--------------------+
```

The key architectural difference from the current approach is that dashboard numbers are produced by the database query and carried forward as verified results. The LLM can choose structure, wording and visualization candidates, but cannot manufacture numerical values.

---

# 5. Implementation requirements

## 5.1 Build a strong semantic model for uploaded data

The backend already has a dataset profiler. Extend the existing semantic approach so the system knows:

### Dataset-level

- detected business entity
- row count
- data quality status
- dataset/source ID
- available date fields
- likely primary/natural key

### Column-level

- raw column name
- canonical field name
- data type
- semantic type
- null percentage
- cardinality/unique count when practical
- sample values (bounded)
- confidence score
- whether the field is safe for aggregation
- whether the field can be used as a dimension
- whether the field can be used as a filter

### Metric-level

Each metric must have a trusted definition, for example:

```json
{
  "code": "revenue",
  "name": "Revenue",
  "description": "Total sales value",
  "sql_expression": "SUM(order_total)",
  "aggregation": "sum",
  "data_type": "currency",
  "default_time_column": "order_date",
  "allowed_dimensions": ["date", "product", "category", "city"]
}
```

Do not allow the LLM to invent a metric expression when a verified metric definition already exists.

If a requested metric is not supported by the dataset, the backend must refuse to calculate it or explain that the required source data is unavailable.

---

# 6. Metric truth rules

These rules are mandatory.

## Rule A: database numbers only

All KPI/chart numeric values shown to the user must originate from an executed database query.

## Rule B: no LLM arithmetic

Do not ask the final LLM to calculate:

- totals
- averages
- growth rates
- percentages
- counts
- ratios
- AOV
- margins
- rankings
- time-series values

The database must calculate these.

## Rule C: no unsupported KPI

If the source data cannot support a KPI, do not show it.

Example:

```text
Dataset has revenue but no cost

Allowed:
- Revenue
- Orders
- AOV

Not allowed:
- Profit
- Profit Margin
```

## Rule D: one-row aggregate handling

If SQL returns:

```text
[{"total_revenue": 6230.83}]
```

that value is already aggregated by PostgreSQL.

The frontend/backend must not sum it again.

## Rule E: multi-row metrics

For time series/grouped output, the database query should explicitly return the metric at the required grain.

Example:

```sql
SELECT
    DATE_TRUNC('month', order_date) AS month,
    SUM(order_total) AS revenue
FROM gold.orders
WHERE tenant_id = :tenant_id
GROUP BY 1
ORDER BY 1
```

The dashboard renderer should display these rows directly.

---

# 7. Visualization recommendation engine

Do not let the LLM freely choose arbitrary chart types.

Create a deterministic backend recommendation layer that uses:

- analytical intent
- metric type
- dimension type
- date/time presence
- cardinality
- number of series
- number of rows
- comparison vs trend vs composition
- whether the result is one value, a sequence, category comparison, relationship, or detailed table

The LLM may choose among allowed candidates, but it must not bypass these rules.

## Initial rules

| Analytical shape | Preferred visual | Fallback |
|---|---|---|
| One aggregated value | KPI | table |
| Time + metric | line | area |
| Category + metric | bar | table |
| Top-N categorical comparison | horizontal bar | table |
| Few-category part-to-whole | donut/pie only if supported by frontend | bar |
| Multiple numeric variables | scatter if frontend supports it | table |
| Detailed records | table | none |
| Target vs actual | bullet/bar if supported | table |
| Geographic dimension | map only if supported | bar/table |

Do not add new chart types unless the backend contract and frontend renderer support them.

---

# 8. Dashboard composition rules

The system should optimize for usefulness, not maximum number of widgets.

For a typical ecommerce dataset, a dashboard might contain:

1. 3-5 highly relevant KPI cards;
2. one main trend chart;
3. one categorical comparison chart;
4. one top-N chart/table;
5. optional secondary analysis only when supported by the data;
6. only useful filters.

Avoid:

- duplicate charts answering the same question;
- charts with too many categories;
- KPI cards without business meaning;
- empty widgets;
- visualizations using raw IDs as measures;
- metrics not present in the dataset;
- charts that cannot be interpreted without hidden context.

The dashboard should answer the user's question first. Extra widgets should add meaningful context.

---

# 9. Query strategy

The AI planner should receive a compact, trusted semantic context rather than a huge dump of raw schema.

The context should prioritize:

1. relevant metric definitions;
2. allowed dimensions;
3. relevant table/column metadata;
4. relationships needed for the requested question;
5. relevant RAG context;
6. query permission constraints.

The planner should produce exactly one read-only analytical query unless the existing product contract is intentionally changed.

The SQL must continue to satisfy all current requirements:

- SELECT/WITH only;
- fully qualified analytics tables;
- tenant isolation on every tenant-scoped table used in FROM/JOIN;
- no secrets/credential/internal operational tables;
- no mutation statements;
- bounded result size;
- PostgreSQL-compatible syntax;
- query timeout/read-only transaction;
- approved tables/columns only.

Do not weaken `SQLGuard` to make an LLM query pass.

If SQLGuard rejects the query, repair the planner/query path; do not weaken the security policy.

---

# 10. Result validation layer

After SQL execution, validate the result before dashboard generation.

At minimum validate:

- rows are within allowed maximum;
- expected metric columns exist;
- requested dimensions exist;
- data types are serializable;
- no unexpected null structure for required fields;
- date/dimension values are usable by the visualization engine;
- numeric outputs are finite where appropriate;
- one-row aggregate semantics are recognized;
- empty results are handled explicitly.

The backend must not silently fabricate replacement values when a result is missing.

---

# 11. Canonical dashboard response

Create a backend response contract that represents **verified display data**, not instructions for the frontend to recalculate metrics.

Recommended conceptual model:

```json
{
  "title": "Sales Overview",
  "kpis": [
    {
      "id": "revenue",
      "label": "Revenue",
      "value": 247850.0,
      "format": "currency",
      "source_column": "revenue"
    },
    {
      "id": "orders",
      "label": "Orders",
      "value": 1240,
      "format": "integer",
      "source_column": "orders"
    }
  ],
  "charts": [
    {
      "id": "revenue_trend",
      "type": "line",
      "title": "Revenue Over Time",
      "x_field": "month",
      "y_field": "revenue",
      "data": [
        {"month": "2026-01", "revenue": 20000},
        {"month": "2026-02", "revenue": 25000}
      ]
    }
  ],
  "filters": [
    {
      "field": "month",
      "type": "date_range"
    }
  ]
}
```

The exact schema can differ, but these principles are mandatory:

- dashboard numeric values are backend-produced;
- dashboard chart data is backend-produced;
- frontend does not re-aggregate KPI values;
- frontend does not execute SQL;
- frontend does not use the LLM to calculate values;
- every field referenced by a widget is validated against the query result;
- format metadata is separated from numerical value.

Do not let the frontend infer business metrics from raw rows when the backend can provide the final verified metric value.

---

# 12. User-facing answer generation

The final LLM may create the natural-language answer, but it must only describe values that are present in the verified database result.

Good:

```text
Revenue was $247,850 across 1,240 orders.
```

Only if those exact values came from the executed query result.

Bad:

```text
Sales appear to have grown because customers prefer premium products.
```

unless the database contains supporting evidence for that statement.

Avoid unsupported causal language such as:

- because
- caused by
- customers prefer
- demand increased because
- product popularity caused

unless the dataset/query actually establishes the relationship.

For derived insights, prefer evidence-based wording such as:

- "Revenue increased 18% from January to February."
- "Category A generated the highest revenue in the returned data."
- "Product X had the largest revenue share among the returned products."

Again, the values must come from the query result.

---

# 13. RAG responsibilities

Keep RAG in the system, but use it for context rather than numerical truth.

RAG is appropriate for:

- metric definitions
- semantic field meaning
- business terminology
- dataset descriptions
- schema documentation
- user/business context

RAG is not the source of truth for:

- current revenue
- order count
- AOV
- time-series numeric values
- percentages
- rankings

Numeric questions must reach the database.

---

# 14. Agentic coding workflow

The AI coding agent must follow this process strictly.

## Phase 0 — Read before editing

Before making any change, inspect:

1. `backend/src/commerce_connector/platform/ai_analyst.py`
2. `backend/src/commerce_connector/platform/db.py`
3. `backend/src/commerce_connector/platform/sql_guard.py`
4. `backend/src/commerce_connector/platform/rag.py`
5. `backend/src/commerce_connector/platform/datasets/profiler.py`
6. `backend/src/commerce_connector/platform/datasets/ingestor.py`
7. `backend/src/commerce_connector/api/routers/ai.py`
8. `backend/src/commerce_connector/api/routers/dashboards.py`
9. relevant schemas
10. all existing AI/dataset/SQL tests

Do not start coding until the current flow is understood.

## Phase 1 — Write a mini implementation plan

Before editing, produce a short internal plan containing:

- files to modify;
- files to add;
- DB changes, if any;
- API contract changes;
- tests to add/change;
- risks and compatibility concerns.

Do not make unrelated refactors.

## Phase 2 — Implement one vertical slice at a time

Recommended order:

### Slice A — semantic/metric foundation

Implement or extend trusted metric/semantic metadata.

Add tests.

### Slice B — verified result model

Make query results the only numerical source.

Add tests.

### Slice C — visualization recommendation

Implement deterministic rules and candidate validation.

Add tests.

### Slice D — canonical dashboard response

Return backend-generated KPI/chart values.

Add contract tests.

### Slice E — user-facing/internal response separation

Remove raw SQL/rows/reasoning from the normal public contract or move them behind explicit internal/debug access.

Add API tests.

### Slice F — end-to-end regression

Run focused tests first, then the complete backend suite.

---

# 15. Safe coding-agent rules

The coding agent MUST follow these rules:

## Do not

- rewrite the entire AI stack;
- replace Supabase/PostgreSQL with another DB;
- remove SQLGuard;
- weaken tenant isolation;
- hardcode dashboard values;
- calculate business metrics in Python when PostgreSQL should calculate them;
- calculate KPI values in the frontend;
- silently change existing endpoint semantics;
- delete existing tests to make the suite green;
- disable failing tests;
- ignore type/schema validation errors;
- introduce a second competing RAG system;
- create parallel metric definitions if existing `ai.metric_definitions` can be extended;
- expose service-role credentials;
- send secrets to the LLM;
- use arbitrary SQL generated by the model without validation;
- claim the system is correct without running tests.

## Do

- preserve tenant isolation everywhere;
- reuse existing abstractions;
- add small, testable functions/classes;
- add regression tests before risky changes when practical;
- validate all LLM structured outputs against a schema;
- keep deterministic logic outside the LLM whenever possible;
- keep database-derived numerical values authoritative;
- log internal execution metadata safely;
- document API contract changes;
- run `py_compile`/lint/type checks where configured;
- run targeted tests after each slice;
- run the full backend test suite before completion.

---

# 16. Testing requirements

The implementation is not complete until the following classes of tests exist.

## Metric truth tests

Test that:

- unsupported metrics are rejected;
- LLM cannot inject arbitrary metric expressions when verified definitions exist;
- KPI values equal the database-returned values;
- no frontend-style re-aggregation happens in the backend response.

## Dashboard contract tests

Test that:

- every KPI has a verified value;
- every chart references existing result fields;
- unsupported chart types are rejected/fallbacked;
- empty query results produce a safe empty/no-data dashboard state;
- one-row aggregate results remain exact values;
- multi-row results preserve row-level values for charts.

## SQL safety tests

Keep existing SQLGuard tests and add cases for:

- multiple tenant-scoped joins;
- unsupported schemas;
- mutation attempts;
- subquery tenant isolation;
- oversized results;
- forbidden internal tables.

## Dataset tests

Keep existing tests and add end-to-end coverage for:

```text
CSV -> profile -> ingest -> Gold -> semantic model -> AI query -> dashboard
XLSX -> profile -> ingest -> Gold -> semantic model -> AI query -> dashboard
JSON -> profile -> ingest -> Gold -> semantic model -> AI query -> dashboard
```

At least one fixture should contain:

- date field;
- categorical field;
- numeric measure;
- repeated records;
- missing values;
- a potential natural key.

## Regression tests for current behavior

Run all existing backend tests before and after implementation.

Do not accept "only my new tests pass" as completion.

---

# 17. Database migration rules

If DB changes are required:

1. inspect the existing Supabase schema first;
2. reuse existing tables when possible;
3. add an explicit SQL migration/script under the backend scripts/migration convention;
4. make changes idempotent where practical;
5. include indexes and tenant-scoped constraints for new tables;
6. document rollback considerations;
7. add tests or schema checks where practical.

Never modify the production database manually without recording the schema change in source control.

Potential schema extensions may include dataset-scoped semantic metadata, but do not create new tables until the existing `ai.metric_definitions`, `ingestion.uploaded_datasets`, and semantic catalog capabilities have been fully evaluated.

---

# 18. Performance requirements

The backend should not turn every user question into many expensive LLM/database calls.

Target:

```text
1 semantic retrieval step
1 planner LLM call
1 validated database query
1 visualization/dashboard planning step
1 optional final wording LLM call
```

Prefer deterministic backend logic over an additional LLM call when the decision can be made reliably in code.

Keep query results bounded and avoid returning large raw datasets to the final LLM. Use aggregated/grouped results whenever the question only needs analytical summaries.

---

# 19. Failure handling

The backend must fail safely.

### Unsupported question

Return a useful message that required data is unavailable.

### SQL rejected

Do not execute it. Log the rejection internally and return a safe user-facing error.

### Query returns zero rows

Return a valid no-data state; do not invent a zero unless zero is actually returned/calculated by the query.

### LLM produces invalid dashboard JSON

Do not pass it to the frontend. Validate and repair using deterministic defaults or return a safe error.

### AI provider unavailable

Do not show fabricated/cached numeric results unless an explicit trusted cache policy exists.

### Database unavailable

Do not answer with an LLM guess.

---

# 20. Observability and auditability

Every completed analytics request should be traceable internally through the existing query-run/dashboard records.

Recommended internal audit chain:

```text
query_run_id
    -> retrieved context IDs
    -> planner output
    -> validated SQL
    -> execution metadata
    -> result metadata
    -> dashboard validation
    -> dashboard_id
```

Store enough metadata to debug failures without storing secrets.

Do not expose this internal chain in the normal dashboard UI.

---

# 21. Definition of Done

The backend work is complete only when ALL of the following are true:

### Data

- [ ] CSV/XLSX/JSON dataset ingestion works through the canonical dataset pipeline.
- [ ] Dataset profiling produces useful semantic metadata.
- [ ] Unsupported/invalid metrics are not generated.

### AI

- [ ] LLM receives trusted semantic context.
- [ ] LLM does not act as numerical source of truth.
- [ ] Structured model outputs are schema-validated.

### SQL

- [ ] SQL is read-only.
- [ ] SQLGuard remains enforced.
- [ ] Every tenant-scoped table has its own tenant filter.
- [ ] Query results remain bounded.
- [ ] Database execution remains read-only and safe.

### Dashboard

- [ ] KPI values come only from executed DB results.
- [ ] Chart data comes only from executed DB results.
- [ ] KPI aggregation is not accidentally performed twice.
- [ ] Unsupported charts are rejected/fallbacked.
- [ ] Chart selection follows deterministic analytical rules.
- [ ] Dashboard contains useful, non-duplicative widgets.
- [ ] Dashboard spec references only verified result fields.

### API

- [ ] Public response is clean and frontend-friendly.
- [ ] Raw SQL/raw rows are not required for normal dashboard rendering.
- [ ] Internal/debug information remains available through safe internal mechanisms if needed.
- [ ] Existing endpoints/contracts are either preserved or explicitly versioned/documented.

### Tests

- [ ] Existing backend tests pass.
- [ ] New metric truth tests pass.
- [ ] New dashboard contract tests pass.
- [ ] New visualization rule tests pass.
- [ ] Upload/ingestion regression tests pass.
- [ ] SQL security tests pass.
- [ ] End-to-end backend dashboard flow passes.

### Documentation

- [ ] Backend API contract updated.
- [ ] New environment variables documented, if any.
- [ ] DB migration documented, if any.
- [ ] Frontend handoff document produced.
- [ ] Known limitations documented.

---

# 22. Frontend handoff required after backend completion

Do NOT implement frontend changes as part of this backend task.

Instead, after backend completion create a separate handoff document, for example:

```text
backend/docs/FRONTEND_DASHBOARD_HANDOFF.md
```

The handoff must explain:

## A. What changed in backend

- new dashboard response schema;
- new KPI structure;
- new chart structure;
- filters;
- any endpoint/version changes;
- any removed/hidden fields such as raw SQL/rows/reasoning.

## B. What frontend must stop doing

The frontend must NOT:

- calculate KPI values from raw rows;
- aggregate revenue/orders/AOV itself;
- execute SQL;
- call the LLM directly for dashboard calculations;
- trust model-generated numeric values.

## C. What frontend should do

The frontend should:

```text
API response
   -> render KPI.value
   -> render chart.data
   -> render chart metadata
   -> render filter controls
```

The frontend becomes a renderer, not an analytics engine.

## D. Current frontend compatibility concerns

The current frontend (`WorkspaceChat.jsx`) consumes:

- `dashboard`
- `rows`
- `sql`
- `reasoning`

and currently computes KPI display values in JavaScript.

The frontend handoff must explicitly explain how this is replaced by the canonical backend dashboard response.

## E. Example API response

Provide at least one complete realistic example response for the frontend engineer.

## F. UI acceptance criteria

Define exactly what the user should see for:

- successful dashboard;
- no-data result;
- unsupported metric;
- query failure;
- dashboard validation failure;
- loading state;
- filters.

---

# 23. Recommended implementation order for the coding agent

Follow this order unless code inspection proves a different order is necessary:

```text
1. Understand current AI + dataset + SQL flow
2. Add/strengthen semantic metric model
3. Make DB results the only numerical truth
4. Add deterministic visualization recommendation engine
5. Build verified dashboard data contract
6. Validate dashboard against executed results
7. Separate public response from internal/debug data
8. Add/upgrade tests
9. Run full backend regression suite
10. Update backend API docs
11. Produce frontend handoff document
12. Report exact files changed + tests executed + known limitations
```

At every step:

```text
inspect -> change minimally -> test -> review -> continue
```

Do not perform a large blind refactor.

---

# 24. Final engineering standard

The finished backend should behave like a small, trustworthy analytical system:

```text
LLM = intent + planning + language

Semantic model = business meaning

SQLGuard = security policy

PostgreSQL/Supabase = numerical source of truth

Visualization engine = analytical representation rules

Dashboard validator = correctness gate

Frontend = renderer
```

The user should experience:

```text
"I asked a question and got a useful dashboard."
```

They should NOT need to know:

```text
what SQL was generated
what the LLM initially thought
how RAG retrieved context
how the metric was computed internally
how many repair steps happened
```

Those are engineering concerns, not normal user concerns.

---

# 25. Agent completion report format

When the coding agent finishes, it must report:

```text
## Implemented
- ...

## Files changed
- ...

## Database changes
- ...

## API contract changes
- ...

## Tests run
- command
- result

## End-to-end verification
- dataset upload: PASS/FAIL
- ingestion: PASS/FAIL
- semantic model: PASS/FAIL
- SQL generation: PASS/FAIL
- SQL validation: PASS/FAIL
- DB execution: PASS/FAIL
- dashboard generation: PASS/FAIL
- dashboard validation: PASS/FAIL

## Frontend handoff
- path to handoff document

## Known limitations
- ...
```

The agent must not claim success unless the tests and end-to-end verification support the claim.
