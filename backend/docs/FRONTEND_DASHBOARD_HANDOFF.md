# Frontend Dashboard Handoff Guide

## Overview

This document specifies the updated backend dashboard contract delivered under **Slices A through F** of `backend/docs/DASHBOARD_GENERATION_BACKEND_AGENT_GUIDE.md`.

The core product principle is:
> **PostgreSQL/Supabase is the sole source of numerical truth.**
> The LLM plans queries, chooses structure, and formulates natural-language explanations, but **never manufactures or recalculates dashboard numbers**.

---

## 1. What Changed in the Backend

### 1.1 Canonical Dashboard Response

The response returned by `POST /api/v1/ai/ask`, `POST /api/v1/conversations/{id}/messages`, and the SSE `result` event from streaming endpoints now provides a verified, structured dashboard specification.

#### Canonical Response Schema:

```json
{
  "conversation_id": "97e5559c-6a12-4c22-b918-68e1da415be2",
  "query_run_id": "4020a104-e34d-44a6-b51d-d249f70d10ec",
  "answer": "Total revenue is $50,000 across 320 orders.",
  "dashboard_id": "76e3381a-7b35-430b-a010-867df3c9428c",
  "dashboard": {
    "title": "Revenue Overview",
    "kpis": [
      {
        "id": "revenue",
        "label": "Revenue",
        "value": 50000.0,
        "format": "currency",
        "source_column": "revenue",
        "column": "revenue",
        "aggregation": "value"
      }
    ],
    "charts": [
      {
        "id": "revenue_trend_0",
        "type": "line",
        "title": "Revenue Over Time",
        "x_field": "metric_date",
        "y_field": "revenue",
        "x": "metric_date",
        "y": "revenue",
        "series": null,
        "data": [
          {"metric_date": "2026-09-01", "revenue": 12000.0},
          {"metric_date": "2026-09-02", "revenue": 15000.0}
        ]
      }
    ],
    "filters": [
      {
        "field": "metric_date",
        "type": "date_range"
      }
    ],
    "no_data": false
  },
  "rows": [ ... ],
  "sql": "SELECT ...",
  "reasoning": true,
  "route": "metric"
}
```

### 1.2 Separation of Internal / Debug Data

1. **Standard Mode (`include_debug=false`, default):**
   - The user-facing response provides `answer`, `dashboard`, `dashboard_id`, `query_run_id`, and `conversation_id`.
   - Backward-compatibility fields (`rows`, `sql`, `reasoning`) remain present so current components (e.g., `WorkspaceChat.jsx`) continue operating without immediate breaking changes.
2. **Debug Mode (`include_debug=true`):**
   - When requested by clients, an explicit top-level `"debug"` object is attached containing execution telemetry:
     ```json
     {
       "debug": {
         "sql": "SELECT SUM(net_sales) AS revenue ...",
         "execution_ms": 14,
         "row_count": 1,
         "route": "metric",
         "intent": { "metric": "revenue", ... },
         "result_shape": "one_row_aggregate",
         "already_aggregated": true,
         "retrieved_context_ids": ["..."],
         "metric_codes": ["revenue"]
       }
     }
     ```
   - All internal query runs and SQL details are also persistently auditable via `GET /api/v1/ai/queries` and table registry endpoints for authorized users.

---

## 2. What the Frontend Must Stop Doing

The frontend (`WorkspaceChat.jsx`) must **stop**:
1. **Recalculating KPI values in JavaScript**:
   - Do NOT run client-side reducers (`computeKpis`) over raw rows.
   - Do NOT sum or average values across returned rows.
2. **Executing or formatting ad-hoc SQL**:
   - The backend runs read-only verified SQL bounded to the tenant.
3. **Assuming unsupported chart types**:
   - The frontend should only render standard, verified chart types: `line`, `bar`, `area`, and `table`. The backend automatically coerces unsupported types (such as pie/donut/radar) to safe fallbacks.

---

## 3. What the Frontend Should Do

The frontend becomes a pure renderer:
1. **Render `dashboard.kpis` directly**:
   - Display `kpi.label` and format `kpi.value` using `kpi.format` (`currency`, `integer`, `number`, `percent`).
2. **Render `dashboard.charts` directly**:
   - Use `chart.data` embedded inside each chart spec, or fall back to verified row data.
   - Render `chart.type`, `chart.title`, `chart.x_field`, and `chart.y_field`.
3. **Handle Empty / No-Data State**:
   - Check `dashboard.no_data === true` or empty widgets, and display an explicit "No matching records found" card rather than placeholder zeros.

---

## 4. UI Acceptance Criteria

- **Successful Dashboard**:
  - Displays KPI cards with exact values provided by `dashboard.kpis`.
  - Trend charts render lines/bars using `chart.data`.
- **Empty Query Result**:
  - `dashboard.no_data` is `true`.
  - Assistant answer indicates no data was found; no synthetic zeros or cards are invented.
- **SQL / Security Blocks**:
  - Unsafe queries are stopped with a user-friendly error; internal SQL details are safely logged.
