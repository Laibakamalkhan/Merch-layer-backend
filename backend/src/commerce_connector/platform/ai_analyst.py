from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

logger = logging.getLogger("commerce_connector.platform.ai_analyst")

from commerce_connector.platform.analytics.metric_resolver import (
    MetricResolution,
    compact_semantic_context,
    enforce_verified_metric_sql,
    resolve_metrics,
)
from commerce_connector.platform.analytics.dashboard_builder import (
    build_verified_dashboard,
    compact_verified_payload,
)
from commerce_connector.platform.analytics.visualization import (
    recommend_visualizations,
)
from commerce_connector.platform.analytics.result_validator import (
    validate_query_result,
)
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

When a verified metric definition is supplied, you MUST use its sql_expression
exactly (or the equivalent pre-aggregated Gold column from that definition).
Never invent a replacement aggregate, scaled expression, or guessed column for
a verified metric. If a metric is listed as unsupported, do not generate SQL
for it.

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
        "aggregation": "value"
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
- Choose chart types only from the allowed visualization candidates supplied in the user prompt.
- Never use pie, donut, scatter, map, or other types the frontend cannot render.
- Backend visualization rules are authoritative if they conflict with a preferred chart type.
- Dashboard numeric values are filled by the backend from the executed query. Do not put numbers on KPIs or charts.
- For a one-row aggregate result, KPI aggregation MUST be "value" because PostgreSQL has already performed the aggregation.
- If the database result is empty, explain that no matching data was returned. Do not invent zeros.
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

MAX_SUBQUERIES = 4
MAX_SUBQUERY_RETRIES = 2
CATEGORY_UNAVAILABLE_MESSAGE = "The category breakdown is not available yet."


class _SubqueryValidationError(Exception):
    """A planner-generated sub-query failed a required validation stage."""


_RELATIVE_PERIOD_PATTERN = re.compile(
    r"\b(?:last|past|previous)\s+(?:\d+\s+)?(?:day|days|week|weeks|month|months|quarter|quarters|year|years|hour|hours)\b",
    re.IGNORECASE,
)


def _enforce_relative_date_filter(question: str, sql: str) -> None:
    """Validate that questions asking for a relative period contain a metric_date filter."""
    if _RELATIVE_PERIOD_PATTERN.search(question):
        if not re.search(r"\bmetric_date\b", sql, re.IGNORECASE):
            raise _SubqueryValidationError(
                "SQL must filter metric_date for the requested period"
            )


def _build_subquery_tasks(
    question: str,
    resolution: Any,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Group requested metrics by Gold/Silver source and cap the query count."""

    groups: dict[tuple[str, str], list[Any]] = {}
    for metric in resolution.matched:
        key = (
            str(metric.preferred_source_schema or "").lower(),
            str(metric.preferred_source_table or "").lower(),
        )
        groups.setdefault(key, []).append(metric)

    if not groups:
        groups[("", "")] = []

    tasks = [
        {
            "source": ".".join(part for part in source if part) or "catalog-authorized tables",
            "metrics": metrics,
        }
        for source, metrics in groups.items()
    ]
    capped = len(tasks) > MAX_SUBQUERIES
    tasks = tasks[:MAX_SUBQUERIES]

    top_n = re.search(r"\b(top(?:\s+\d+)?|top[- ]selling|best[- ]selling)\b", question, re.I)
    dimension_match = re.search(
        r"\b(?:broken\s+down\s+by|by|per)\s+(category|categories|product|products)\b",
        question,
        re.I,
    )
    unavailable_dimension = None
    if top_n and dimension_match:
        dimension = dimension_match.group(1).lower()
        canonical = "category" if dimension.startswith("categor") else "product"
        permitted_dimensions = {
            item.lower()
            for metric in resolution.matched
            for item in metric.allowed_dimensions
        }
        if canonical not in permitted_dimensions:
            unavailable_dimension = canonical

    notice = (
        CATEGORY_UNAVAILABLE_MESSAGE
        if unavailable_dimension == "category"
        else (
            f"The {unavailable_dimension} breakdown is not available yet."
            if unavailable_dimension
            else None
        )
    )
    return tasks, capped, notice


def _merge_dashboards(dashboards: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge verified per-query dashboard sections without changing the contract."""

    if not dashboards:
        return {
            "title": "AI Analytics",
            "kpis": [],
            "charts": [],
            "filters": [],
            "no_data": True,
        }

    merged: dict[str, Any] = {
        "title": next(
            (item["title"] for item in dashboards if item.get("title")),
            "AI Analytics",
        ),
        "kpis": [],
        "charts": [],
        "filters": [],
        "no_data": all(bool(item.get("no_data")) for item in dashboards),
    }
    seen_kpis: set[str] = set()
    seen_filters: set[tuple[str, str]] = set()
    for dashboard in dashboards:
        for kpi in dashboard.get("kpis") or []:
            key = str(kpi.get("id") or kpi.get("column") or kpi.get("label"))
            if key not in seen_kpis:
                seen_kpis.add(key)
                merged["kpis"].append(kpi)
        merged["charts"].extend(dashboard.get("charts") or [])
        for filter_item in dashboard.get("filters") or []:
            key = (str(filter_item.get("field")), str(filter_item.get("type")))
            if key not in seen_filters:
                seen_filters.add(key)
                merged["filters"].append(filter_item)
    return merged


def _execute_subquery(
    *,
    llm: LLMClient,
    db: PostgresGateway,
    tenant_id: str,
    query_run_id: str,
    question: str,
    task: dict[str, Any],
    snapshot: dict[str, Any],
    resolution: Any,
    context_text: str,
    history_text: str,
    files_text: str,
    reasoning: bool,
) -> dict[str, Any]:
    permissions = snapshot.get("permissions") or []
    allowed = (
        {
            (p["schema_name"], p["table_name"])
            for p in permissions
        }
        if permissions
        else None
    )
    max_rows = min(
        max((int(p.get("max_rows") or 5000) for p in permissions), default=5000),
        5000,
    )
    scoped_resolution = MetricResolution(
        ok=resolution.ok,
        metrics=resolution.metrics,
        matched=list(task["metrics"]),
    )
    catalog_text = compact_semantic_context(snapshot, scoped_resolution)
    subquery_goal = (
        f"Create a query for the requested metric(s) "
        f"{', '.join(metric.code for metric in task['metrics'])} "
        f"from {task['source']}."
        if task["metrics"]
        else "Create one safe query that answers the supported part of the request."
    )
    planner_prompt = (
        "Create one analytics query plan for this sub-query.\n\n"
        f"Sub-query goal: {subquery_goal}\n"
        f"User question:\n{question}\n\n"
        f"{catalog_text}\n\n"
        "Retrieved semantic context (supporting terminology only; not a source "
        "of numerical values or metric SQL):\n"
        f"{context_text}{history_text}{files_text}\n\n"
        "Return exactly one JSON object matching the supplied schema. "
        "Return exactly one safe read-only query, and do not return markdown. "
        "Only answer this sub-query's verified metric goal. Do not attempt any "
        "product or category breakdown unless the supplied metric definitions "
        "and allowed dimensions explicitly support it."
    )
    if reasoning:
        planner_prompt += (
            "\nReasoning mode is enabled; consider multiple relevant metrics "
            "and dimensions for this sub-query."
        )

    feedback = ""
    failed_sql = ""
    for attempt in range(MAX_SUBQUERY_RETRIES + 1):
        prompt = planner_prompt
        if feedback:
            prompt += (
                "\n\nValidation feedback for the previous attempt:\n"
                f"Failed SQL:\n{failed_sql}\n"
                f"Validation error:\n{feedback}\n"
                "Correct the SQL for this sub-query. Do not remove required "
                "tenant filters or bypass any validation."
            )
        plan: dict[str, Any] = {}
        sql = ""
        intent: dict[str, Any] | None = None
        try:
            try:
                plan = llm.generate_json(
                    prompt,
                    system=PLAN_SYSTEM,
                    temperature=0.0,
                    schema_name="analytics_query_plan",
                    schema=PLAN_JSON_SCHEMA,
                    reasoning_effort="high" if reasoning else "low",
                )
            except Exception as exc:
                logger.warning(
                    "LLM query plan generation failed for query_run_id=%s attempt=%s: %s",
                    query_run_id,
                    attempt,
                    exc,
                )
                raise _SubqueryValidationError(
                    "The generated query plan was not valid JSON or could not be generated."
                ) from exc

            if not isinstance(plan, dict):
                raise _SubqueryValidationError(
                    "Query planner returned an invalid response structure."
                )

            sql = str(plan.get("sql") or "").strip()
            intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else None

            if not sql:
                raise _SubqueryValidationError("Generated SQL query was empty.")

            try:
                enforce_verified_metric_sql(
                    sql,
                    snapshot=snapshot,
                    resolution=scoped_resolution,
                    intent=intent,
                )
            except RuntimeError as exc:
                raise _SubqueryValidationError(str(exc)) from exc

            _enforce_relative_date_filter(question, sql)

            if intent:
                post_resolution = resolve_metrics(
                    question,
                    snapshot,
                    intent=intent,
                )
                if not post_resolution.ok:
                    raise _SubqueryValidationError(
                        post_resolution.message
                        or "Required metric is not available in the semantic catalog."
                    )

            guard = SQLGuard(allowed_tables=allowed, max_rows=max_rows).validate(sql)
            if not guard.ok:
                try:
                    db.save_generated_query(
                        tenant_id=tenant_id,
                        query_run_id=query_run_id,
                        sql_text=sql,
                        validation_status="blocked",
                        blocked_reason=guard.reason,
                    )
                except Exception:
                    pass
                raise _SubqueryValidationError(
                    guard.reason or "Generated SQL did not pass SQL validation."
                )

            started = time.perf_counter()
            try:
                raw_rows = db.execute_readonly_query(guard.sql, tenant_id)
            except Exception as exc:
                logger.warning(
                    "Database readonly query execution failed for query_run_id=%s attempt=%s: %s",
                    query_run_id,
                    attempt,
                    exc,
                )
                try:
                    db.save_generated_query(
                        tenant_id=tenant_id,
                        query_run_id=query_run_id,
                        sql_text=sql,
                        validation_status="failed",
                        blocked_reason=str(exc)[:500],
                    )
                except Exception:
                    pass
                raise _SubqueryValidationError(
                    "Database query execution failed. Please verify table names, column names, join conditions, and SQL syntax."
                ) from exc

            execution_ms = int((time.perf_counter() - started) * 1000)
            expected_dimensions = [
                str(item)
                for item in (intent.get("dimensions") or [])
                if str(item).strip()
            ] if intent else []
            verified = validate_query_result(
                raw_rows,
                expected_metrics=list(task["metrics"]),
                expected_dimensions=expected_dimensions,
                max_rows=max_rows,
            )
            if not verified.ok:
                raise _SubqueryValidationError(
                    verified.message
                    or "Query result failed verification."
                )
            rows = verified.as_dicts()
            try:
                db.save_generated_query(
                    tenant_id=tenant_id,
                    query_run_id=query_run_id,
                    sql_text=sql,
                    validation_status="approved",
                    execution_ms=execution_ms,
                    row_count=verified.row_count,
                    result_preview=rows[:50],
                )
            except Exception:
                pass
            return {
                "plan": plan,
                "sql": sql,
                "intent": intent,
                "verified": verified,
                "rows": rows,
                "execution_ms": execution_ms,
                "validation_attempts": attempt + 1,
                "resolution": scoped_resolution,
            }
        except _SubqueryValidationError as exc:
            feedback = str(exc)
            failed_sql = sql
            if attempt >= MAX_SUBQUERY_RETRIES:
                return {
                    "plan": plan,
                    "sql": "",
                    "intent": intent,
                    "failure": True,
                    "resolution": scoped_resolution,
                }

    raise AssertionError("Sub-query retry loop exited without a result")


def _complete_subquery_request(
    *,
    db: PostgresGateway,
    llm: LLMClient,
    tenant_id: str,
    query_run_id: str,
    question: str,
    tasks: list[dict[str, Any]],
    capped: bool,
    breakdown_notice: str | None,
    snapshot: dict[str, Any],
    resolution: Any,
    context: list[dict[str, Any]],
    semantic: str,
    history_text: str,
    files_text: str,
    file_ids: list[str] | None,
    reasoning: bool,
    conversation_id: str | None,
    include_debug: bool,
) -> dict[str, Any]:
    outcomes = [
        _execute_subquery(
            llm=llm,
            db=db,
            tenant_id=tenant_id,
            query_run_id=query_run_id,
            question=question,
            task=task,
            snapshot=snapshot,
            resolution=resolution,
            context_text=semantic,
            history_text=history_text,
            files_text=files_text,
            reasoning=reasoning,
        )
        for task in tasks
    ]
    successful = [item for item in outcomes if not item.get("failure")]
    failed = [item for item in outcomes if item.get("failure")]
    dashboards: list[dict[str, Any]] = []
    answers: list[str] = []

    for item in successful:
        verified = item["verified"]
        viz = recommend_visualizations(verified, intent=item["intent"])
        shape_note = (
            f"Verified result shape: {verified.shape}. "
            f"already_aggregated={verified.already_aggregated}. "
            "PostgreSQL already calculated these values; do not recalculate."
        )
        if verified.shape == "empty":
            shape_note = (
                "Verified result shape: empty. No matching rows were returned. "
                "Do not invent or substitute numbers."
            )
        final_prompt = (
            "Generate a grounded response for this executed analytics sub-query.\n\n"
            f"User question:\n{question}\n\n"
            f"Sub-query goal: {item['plan'].get('title') or 'verified analytics'}\n\n"
            f"Executed SQL:\n{item['sql']}\n\n{shape_note}\n\n"
            "Verified database result (authoritative; do not recalculate):\n"
            f"{json.dumps(compact_verified_payload(verified), allow_nan=False)}"
            f"{files_text}\n\n"
            "Do not invent or calculate any number. Only reference columns "
            "present in the database result. Dashboard numbers are copied "
            "by the backend. For one-row aggregates use KPI aggregation "
            '"value". Do not claim to have produced an unsupported breakdown.\n'
            f"- {viz.prompt_text()}\n"
            "Return exactly one JSON object matching the supplied schema."
        )
        final = llm.generate_json(
            final_prompt,
            system=FINAL_SYSTEM,
            temperature=0.0,
            schema_name="analytics_final_response",
            schema=FINAL_JSON_SCHEMA,
            reasoning_effort="high" if reasoning else "low",
        )
        dashboards.append(
            _normalise_dashboard(
                final.get("dashboard"),
                item["rows"],
                intent=item["intent"],
                verified=verified,
                metrics=item["resolution"].matched,
                title=str(item["plan"].get("title") or "AI Analytics"),
            )
        )
        answer_text = str(final.get("answer") or "").strip()
        if answer_text:
            answers.append(answer_text)

    dashboard = _merge_dashboards(dashboards)
    notices: list[str] = []
    if breakdown_notice:
        notices.append(breakdown_notice)
    if failed:
        notices.append("I couldn't produce one requested section after checking its query.")
    if capped:
        notices.append(
            "Some requested analyses were omitted because this request is limited to four queries."
        )
    answer = " ".join([*answers, *notices]).strip()
    if not answer:
        answer = "I couldn't produce the requested analytics from the available verified data."

    rows = [row for item in successful for row in item["rows"]]
    sql = "\n\n".join(item["sql"] for item in successful)
    execution_ms = sum(item["execution_ms"] for item in successful)
    first_outcome = successful[0] if successful else (outcomes[0] if outcomes else {})
    first_plan = first_outcome.get("plan") or {}
    first_intent = first_outcome.get("intent")
    verified_results = [item["verified"] for item in successful]
    title = str(dashboard.get("title") or "AI Analytics")
    saved_dashboard = db.save_dashboard_spec(
        tenant_id,
        query_run_id,
        title,
        answer,
        dashboard,
    )
    db.update_query_run(
        query_run_id,
        status="completed",
        route=first_plan.get("route"),
        intent=first_intent or {},
        selected_context={
            "chunks": [str(c["chunk_id"]) for c in context],
            "file_ids": file_ids or [],
            "reasoning": reasoning,
            "metric_codes": resolution.matched_codes(),
            "result_shapes": [result.shape for result in verified_results],
            "partial": bool(failed or breakdown_notice or capped),
        },
    )
    if conversation_id:
        db.add_message(
            tenant_id,
            conversation_id,
            "assistant",
            answer,
            {
                "query_run_id": str(query_run_id),
                "dashboard_id": str(saved_dashboard["id"]),
                "route": first_plan.get("route"),
            },
        )

    response: dict[str, Any] = {
        "conversation_id": conversation_id,
        "query_run_id": str(query_run_id),
        "answer": answer,
        "dashboard_id": str(saved_dashboard["id"]),
        "dashboard": dashboard,
        "rows": rows,
        "sql": sql,
        "reasoning": reasoning,
        "route": first_plan.get("route"),
    }
    if include_debug:
        response["debug"] = {
            "sql": sql,
            "execution_ms": execution_ms,
            "row_count": len(rows),
            "route": first_plan.get("route"),
            "intent": first_intent,
            "result_shape": (
                verified_results[0].shape
                if len(verified_results) == 1
                else ("empty" if not verified_results else "grouped")
            ),
            "already_aggregated": all(
                result.already_aggregated for result in verified_results
            ) if verified_results else False,
            "retrieved_context_ids": [str(c["chunk_id"]) for c in context],
            "metric_codes": resolution.matched_codes(),
        }
    return response


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
        include_debug: bool = False,
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

            snapshot = self.db.semantic_catalog_snapshot(tenant_id)
            resolution = resolve_metrics(question, snapshot)
            if not resolution.ok:
                raise RuntimeError(
                    resolution.message
                    or "Required metric is not available in the semantic catalog."
                )

            catalog_text = compact_semantic_context(snapshot, resolution)
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

            tasks, capped, breakdown_notice = _build_subquery_tasks(
                question,
                resolution,
            )
            return _complete_subquery_request(
                db=self.db,
                llm=self.llm,
                tenant_id=tenant_id,
                query_run_id=str(query_run_id),
                question=question,
                tasks=tasks,
                capped=capped,
                breakdown_notice=breakdown_notice,
                snapshot=snapshot,
                resolution=resolution,
                context=context,
                semantic=semantic,
                history_text=history_text,
                files_text=files_text,
                file_ids=file_ids,
                reasoning=reasoning,
                conversation_id=conversation_id,
                include_debug=include_debug,
            )

        except Exception as exc:
            try:
                if not blocked:
                    self.db.update_query_run(
                        query_run_id,
                        status="failed",
                        error_message=str(exc)[:500],
                    )

                if conversation_id:
                    self.db.add_message(
                        tenant_id,
                        conversation_id,
                        "assistant",
                        "I couldn't complete that analysis.",
                        {
                            "error": "I couldn't complete that analysis.",
                            "query_run_id": str(query_run_id),
                        },
                    )

            except Exception:
                pass

            raise


def _normalise_dashboard(
    dashboard: Any,
    rows: list[dict[str, Any]],
    *,
    intent: dict[str, Any] | None = None,
    verified: Any | None = None,
    metrics: list[Any] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Materialise a canonical dashboard from executed query rows.

    The LLM may supply labels and layout. Numeric KPI/chart values are copied
    from PostgreSQL results and are never recalculated here.
    """

    return build_verified_dashboard(
        verified if verified is not None else rows,
        title=title,
        llm_dashboard=dashboard if isinstance(dashboard, dict) else {},
        intent=intent,
        metrics=metrics,
    )