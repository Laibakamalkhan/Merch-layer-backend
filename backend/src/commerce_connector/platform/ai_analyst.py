from __future__ import annotations

import json
import time
from typing import Any

from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from commerce_connector.platform.rag import RagRetriever
from commerce_connector.platform.sql_guard import SQLGuard


PLAN_SYSTEM = """You are the query planner for a multi-tenant ecommerce analytics platform.

Your job is to convert the user's analytics question into exactly ONE safe PostgreSQL query plan.

IMPORTANT OUTPUT RULES:
- Return exactly one JSON object.
- Never return an empty response.
- Never return markdown.
- Never wrap the JSON in ``` fences.
- Do not add commentary before or after the JSON.
- The JSON object MUST contain exactly these top-level keys:
  route, intent, sql, title.

The required JSON structure is:

{
  "route": "string",
  "intent": {
    "metric": "string",
    "dimensions": ["string"],
    "date_range": "string",
    "comparison": "string",
    "filters": ["string"]
  },
  "sql": "string",
  "title": "string"
}

Use only the supplied semantic context. Never invent columns or tables.

Prefer Gold for standard KPIs and Silver for detailed/ad-hoc analysis.

SQL rules:
- read-only SELECT or WITH only
- use fully qualified gold.* / silver.* tables
- control.connections/platforms may be joined only for names/platform labels
- tenant isolation is mandatory
- EVERY tenant-scoped table referenced in FROM or JOIN must have its own tenant filter
- each tenant-scoped table must use its own alias-qualified condition, for example:
  alias.tenant_id = :tenant_id
- do NOT rely on another table's tenant_id filter to secure a joined table
- if silver.products is referenced as alias p, the SQL MUST contain:
  p.tenant_id = :tenant_id
- apply this rule to EVERY silver.* and gold.* table referenced by the query
- never access credentials, Vault, Bronze raw payloads, IAM, AI chat tables, or Ops internals
- use PostgreSQL syntax
- no trailing semicolon
- generate exactly one SQL query
- do not invent values
- do not put hard-coded analytics results into the SQL
- date calculations must be performed by PostgreSQL
"""


FINAL_SYSTEM = """You are an ecommerce analytics assistant.

Your job is to explain the result of a database query accurately.

IMPORTANT OUTPUT RULES:
- Return exactly one JSON object.
- Never return an empty response.
- Never return markdown.
- Never wrap the JSON in ``` fences.
- Do not add commentary before or after the JSON.
- The JSON object MUST contain exactly these top-level keys:
  answer, dashboard.

The required JSON structure is:

{
  "answer": "string",
  "dashboard": {
    "title": "string",
    "kpis": [
      {
        "label": "string",
        "column": "string",
        "aggregation": "sum|avg|max|min|value"
      }
    ],
    "charts": [
      {
        "type": "line|bar|area|table",
        "title": "string",
        "x": "string or null",
        "y": "string or null",
        "series": "string or null"
      }
    ],
    "filters": [
      {
        "field": "string",
        "type": "date_range|select"
      }
    ]
  }
}

The database result is authoritative.

Rules:
- Do not invent values.
- Do not estimate values.
- Do not round values.
- Do not recalculate numeric values.
- Do not describe any number that is absent from the database result.
- Only reference columns actually present in the database result.
- For a one-row aggregate result, KPI aggregation MUST be "value" because PostgreSQL has already performed the aggregation.
- For multi-row results, use an aggregation only when it intentionally summarizes those rows.
- If the database result is empty, explain that no matching data was returned.
"""


PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "route",
        "intent",
        "sql",
        "title",
    ],
    "properties": {
        "route": {
            "type": "string",
        },
        "intent": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "metric",
                "dimensions",
                "date_range",
                "comparison",
                "filters",
            ],
            "properties": {
                "metric": {
                    "type": "string",
                },
                "dimensions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "date_range": {
                    "type": "string",
                },
                "comparison": {
                    "type": "string",
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
        },
        "sql": {
            "type": "string",
        },
        "title": {
            "type": "string",
        },
    },
}


FINAL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer",
        "dashboard",
    ],
    "properties": {
        "answer": {
            "type": "string",
        },
        "dashboard": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "title",
                "kpis",
                "charts",
                "filters",
            ],
            "properties": {
                "title": {
                    "type": "string",
                },
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "label",
                            "column",
                            "aggregation",
                        ],
                        "properties": {
                            "label": {
                                "type": "string",
                            },
                            "column": {
                                "type": "string",
                            },
                            "aggregation": {
                                "type": "string",
                                "enum": [
                                    "sum",
                                    "avg",
                                    "max",
                                    "min",
                                    "value",
                                ],
                            },
                        },
                    },
                },
                "charts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "type",
                            "title",
                            "x",
                            "y",
                            "series",
                        ],
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "line",
                                    "bar",
                                    "area",
                                    "table",
                                ],
                            },
                            "title": {
                                "type": "string",
                            },
                            "x": {
                                "type": [
                                    "string",
                                    "null",
                                ],
                            },
                            "y": {
                                "type": [
                                    "string",
                                    "null",
                                ],
                            },
                            "series": {
                                "type": [
                                    "string",
                                    "null",
                                ],
                            },
                        },
                    },
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "field",
                            "type",
                        ],
                        "properties": {
                            "field": {
                                "type": "string",
                            },
                            "type": {
                                "type": "string",
                                "enum": [
                                    "date_range",
                                    "select",
                                ],
                            },
                        },
                    },
                },
            },
        },
    },
}


class AIAnalyst:
    def __init__(self, db: PostgresGateway, llm: LLMClient):
        self.db = db
        self.llm = llm
        self.retriever = RagRetriever(db, llm)

    def ask(
        self,
        tenant_id: str,
        question: str,
        *,
        user_id: str | None = None,
        conversation_id: str | None = None,
        reasoning: bool = False,
        file_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if conversation_id is None and user_id:
            conversation = self.db.create_conversation(
                tenant_id,
                user_id,
            )
            conversation_id = str(conversation["id"])

        elif conversation_id and user_id:
            if not self.db.get_conversation(
                conversation_id,
                tenant_id,
                user_id,
            ):
                raise RuntimeError(
                    "Conversation does not belong to this user/workspace"
                )

        if conversation_id:
            self.db.add_message(
                tenant_id,
                conversation_id,
                "user",
                question,
                {
                    "reasoning": reasoning,
                    "file_ids": file_ids or [],
                },
            )
            self.db.maybe_title_conversation(
                conversation_id,
                question,
            )

        run = self.db.create_query_run(
            tenant_id,
            question,
            self.llm.model,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        query_run_id = run["id"]
        blocked = False

        try:
            retrieval_count = 15 if reasoning else 10

            context = self.retriever.retrieve(
                tenant_id,
                question,
                count=retrieval_count,
            )

            if not context:
                raise RuntimeError(
                    "RAG index is empty. Build/rebuild the semantic index first."
                )

            semantic = "\n\n".join(
                f"[{item['title']}] "
                f"similarity={item['similarity']:.3f}\n"
                f"{item['content']}"
                for item in context
            )

            history_text = ""

            if conversation_id:
                history = self.db.list_messages(
                    conversation_id,
                    tenant_id,
                    limit=12,
                )

                prior = (
                    history[:-1]
                    if history
                    and history[-1].get("role") == "user"
                    else history
                )

                if prior:
                    history_text = (
                        "\n\nRecent conversation:\n"
                        + "\n".join(
                            f"{m.get('role')}: "
                            f"{str(m.get('content') or '')[:1500]}"
                            for m in prior[-10:]
                        )
                    )

            files_text = ""

            if user_id and file_ids:
                files = self.db.get_file_context(
                    tenant_id,
                    user_id,
                    file_ids,
                )

                if files:
                    files_text = (
                        "\n\nAttached file context:\n"
                        + "\n\n".join(
                            f"FILE: {f['title']}\n{f['content']}"
                            for f in files
                        )
                    )

            planner_hint = ""

            if reasoning:
                planner_hint = (
                    "\n\nReasoning mode is enabled. "
                    "Examine multiple relevant metrics and dimensions "
                    "before choosing the SQL, but still return exactly "
                    "one safe read-only query."
                )

            planner_prompt = (
                "Create the analytics query plan for the user question below.\n\n"
                "User question:\n"
                f"{question}\n\n"
                "Retrieved semantic context:\n"
                f"{semantic}"
                f"{history_text}"
                f"{files_text}"
                f"{planner_hint}\n\n"
                "Return exactly one JSON object matching the supplied schema. "
                "Do not return an empty response. "
                "Do not return markdown."
            )

            plan = self.llm.generate_json(
                planner_prompt,
                system=PLAN_SYSTEM,
                temperature=0.0,
                schema_name="analytics_query_plan",
                schema=PLAN_JSON_SCHEMA,
                reasoning_effort="high" if reasoning else "low",
            )

            sql = str(plan.get("sql") or "")

            permissions = self.db.semantic_catalog_snapshot(
                tenant_id
            )["permissions"]

            allowed = None
            max_rows = 5000

            if permissions:
                allowed = {
                    (
                        p["schema_name"],
                        p["table_name"],
                    )
                    for p in permissions
                }

                max_rows = min(
                    max(
                        int(p.get("max_rows") or 5000)
                        for p in permissions
                    ),
                    5000,
                )

            guard = SQLGuard(
                allowed_tables=allowed,
                max_rows=max_rows,
            ).validate(sql)

            if not guard.ok:
                self.db.save_generated_query(
                    tenant_id=tenant_id,
                    query_run_id=query_run_id,
                    sql_text=sql,
                    validation_status="blocked",
                    blocked_reason=guard.reason,
                )

                blocked = True

                self.db.update_query_run(
                    query_run_id,
                    status="blocked",
                    route=plan.get("route"),
                    intent=(
                        plan.get("intent")
                        if isinstance(plan.get("intent"), dict)
                        else {
                            "intent": plan.get("intent"),
                        }
                    ),
                    selected_context={
                        "chunks": [
                            str(c["chunk_id"])
                            for c in context
                        ],
                        "file_ids": file_ids or [],
                        "reasoning": reasoning,
                    },
                    error_message=guard.reason,
                )

                raise RuntimeError(
                    f"Generated SQL blocked: {guard.reason}"
                )

            started = time.perf_counter()

            rows = self.db.execute_readonly_query(
                guard.sql,
                tenant_id,
            )

            execution_ms = int(
                (time.perf_counter() - started) * 1000
            )

            self.db.save_generated_query(
                tenant_id=tenant_id,
                query_run_id=query_run_id,
                sql_text=sql,
                validation_status="approved",
                execution_ms=execution_ms,
                row_count=len(rows),
                result_preview=rows[:50],
            )

            final_prompt = (
                "Generate the final grounded analytics response.\n\n"
                "User question:\n"
                f"{question}\n\n"
                "Executed SQL:\n"
                f"{sql}\n\n"
                "Database result JSON:\n"
                f"{json.dumps(rows[:200], default=str)}"
                f"{files_text}\n\n"
                "IMPORTANT:\n"
                "- The database result is authoritative.\n"
                "- Do not invent or calculate any number.\n"
                "- Only reference columns present in the database result.\n"
                "- If this is a one-row aggregate result, use KPI aggregation "
                '"value".\n'
                "- Return exactly one JSON object matching the supplied schema.\n"
                "- Do not return an empty response.\n"
                "- Do not return markdown."
            )

            final = self.llm.generate_json(
                final_prompt,
                system=FINAL_SYSTEM,
                temperature=0.0,
                schema_name="analytics_final_response",
                schema=FINAL_JSON_SCHEMA,
                reasoning_effort="high" if reasoning else "low",
            )

            dashboard = _normalise_dashboard(
                final.get("dashboard"),
                rows,
            )

            title = str(
                dashboard.get("title")
                or plan.get("title")
                or "AI Analytics"
            )

            answer = str(
                final.get("answer")
                or ""
            )

            saved_dashboard = self.db.save_dashboard_spec(
                tenant_id,
                query_run_id,
                title,
                answer,
                dashboard,
            )

            self.db.update_query_run(
                query_run_id,
                status="completed",
                route=plan.get("route"),
                intent=(
                    plan.get("intent")
                    if isinstance(plan.get("intent"), dict)
                    else {
                        "intent": plan.get("intent"),
                    }
                ),
                selected_context={
                    "chunks": [
                        str(c["chunk_id"])
                        for c in context
                    ],
                    "file_ids": file_ids or [],
                    "reasoning": reasoning,
                },
            )

            if conversation_id:
                self.db.add_message(
                    tenant_id,
                    conversation_id,
                    "assistant",
                    answer,
                    {
                        "query_run_id": str(query_run_id),
                        "dashboard_id": str(
                            saved_dashboard["id"]
                        ),
                        "route": plan.get("route"),
                    },
                )

            return {
                "conversation_id": conversation_id,
                "query_run_id": str(query_run_id),
                "answer": answer,
                "sql": sql,
                "rows": rows,
                "dashboard": dashboard,
                "dashboard_id": str(
                    saved_dashboard["id"]
                ),
                "route": plan.get("route"),
                "reasoning": reasoning,
            }

        except Exception as exc:
            try:
                if not blocked:
                    self.db.update_query_run(
                        query_run_id,
                        status="failed",
                        error_message=str(exc),
                    )

                if conversation_id:
                    self.db.add_message(
                        tenant_id,
                        conversation_id,
                        "assistant",
                        "I couldn't complete that analysis.",
                        {
                            "error": str(exc)[:500],
                            "query_run_id": str(query_run_id),
                        },
                    )

            except Exception:
                pass

            raise


def _normalise_dashboard(
    dashboard: Any,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep the LLM dashboard spec strictly aligned with returned SQL columns.

    SQL is the source of truth. A dashboard field that points at a column that
    was not returned by the query is removed/neutralised instead of allowing
    the frontend to manufacture a value.

    PostgreSQL has already performed aggregation for one-row aggregate queries,
    so a one-row KPI must be displayed as its value rather than summed again.
    """

    raw = (
        dashboard
        if isinstance(dashboard, dict)
        else {}
    )

    available = (
        set(rows[0].keys())
        if rows
        else set()
    )

    title = str(
        raw.get("title")
        or "AI Analytics"
    )

    kpis: list[dict[str, Any]] = []

    for item in raw.get("kpis") or []:
        if not isinstance(item, dict):
            continue

        column = item.get("column")

        if (
            not isinstance(column, str)
            or column not in available
        ):
            continue

        aggregation = str(
            item.get("aggregation")
            or "value"
        ).lower()

        if aggregation not in {
            "sum",
            "avg",
            "max",
            "min",
            "value",
        }:
            aggregation = "value"

        if len(rows) == 1:
            aggregation = "value"

        kpis.append(
            {
                "label": str(
                    item.get("label")
                    or column
                ),
                "column": column,
                "aggregation": aggregation,
            }
        )

    charts: list[dict[str, Any]] = []

    for item in raw.get("charts") or []:
        if not isinstance(item, dict):
            continue

        chart_type = str(
            item.get("type")
            or "table"
        ).lower()

        if chart_type not in {
            "line",
            "bar",
            "area",
            "table",
        }:
            chart_type = "table"

        x = item.get("x")
        y = item.get("y")
        series = item.get("series")

        charts.append(
            {
                "type": chart_type,
                "title": str(
                    item.get("title")
                    or "Chart"
                ),
                "x": (
                    x
                    if isinstance(x, str)
                    and x in available
                    else None
                ),
                "y": (
                    y
                    if isinstance(y, str)
                    and y in available
                    else None
                ),
                "series": (
                    series
                    if isinstance(series, str)
                    and series in available
                    else None
                ),
            }
        )

    filters: list[dict[str, Any]] = []

    for item in raw.get("filters") or []:
        if not isinstance(item, dict):
            continue

        field = item.get("field")
        filter_type = item.get("type")

        if (
            isinstance(field, str)
            and field in available
            and filter_type in {
                "date_range",
                "select",
            }
        ):
            filters.append(
                {
                    "field": field,
                    "type": filter_type,
                }
            )

    return {
        "title": title,
        "kpis": kpis,
        "charts": charts,
        "filters": filters,
    }