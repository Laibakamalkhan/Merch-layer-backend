from __future__ import annotations

import json
import time
from typing import Any

from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.gemini import GeminiClient
from commerce_connector.platform.rag import RagRetriever
from commerce_connector.platform.sql_guard import SQLGuard


PLAN_SYSTEM = """You are the query planner for a multi-tenant ecommerce analytics platform.
Use only the supplied semantic context. Never invent columns or tables.
Prefer Gold for standard KPIs and Silver for detailed/ad-hoc analysis.
Return JSON only with keys: route, intent, sql, title.
SQL rules:
- read-only SELECT or WITH only
- use fully qualified gold.* / silver.* tables; control.connections/platforms may be joined only for names/platform labels
- every query MUST explicitly filter tenant_id = :tenant_id (or alias.tenant_id = :tenant_id)
- never access credentials, Vault, Bronze raw payloads, IAM, AI chat tables, or Ops internals
- use PostgreSQL syntax
- no trailing semicolon
"""


FINAL_SYSTEM = """You are an ecommerce analytics assistant. Explain database-calculated results accurately.
Do not recalculate or invent values. Return JSON only with keys:
answer (string), dashboard (object).
Dashboard object format:
{
  "title": string,
  "kpis": [{"label": string, "column": string, "aggregation": "sum|avg|max|min|value"}],
  "charts": [{"type":"line|bar|area|table", "title":string, "x":string|null, "y":string|null, "series":string|null}],
  "filters": [{"field":string,"type":"date_range|select"}]
}
Only reference columns actually present in the result set.
"""


class AIAnalyst:
    def __init__(self, db: PostgresGateway, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini
        self.retriever = RagRetriever(db, gemini)

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
            conversation = self.db.create_conversation(tenant_id, user_id)
            conversation_id = str(conversation["id"])
        elif conversation_id and user_id:
            if not self.db.get_conversation(conversation_id, tenant_id, user_id):
                raise RuntimeError("Conversation does not belong to this user/workspace")

        if conversation_id:
            self.db.add_message(
                tenant_id,
                conversation_id,
                "user",
                question,
                {"reasoning": reasoning, "file_ids": file_ids or []},
            )
            self.db.maybe_title_conversation(conversation_id, question)

        run = self.db.create_query_run(
            tenant_id,
            question,
            self.gemini.model,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        query_run_id = run["id"]
        blocked = False
        try:
            retrieval_count = 15 if reasoning else 10
            context = self.retriever.retrieve(tenant_id, question, count=retrieval_count)
            if not context:
                raise RuntimeError("RAG index is empty. Build/rebuild the semantic index first.")
            semantic = "\n\n".join(
                f"[{item['title']}] similarity={item['similarity']:.3f}\n{item['content']}"
                for item in context
            )

            history_text = ""
            if conversation_id:
                history = self.db.list_messages(conversation_id, tenant_id, limit=12)
                prior = history[:-1] if history and history[-1].get("role") == "user" else history
                if prior:
                    history_text = "\n\nRecent conversation:\n" + "\n".join(
                        f"{m.get('role')}: {str(m.get('content') or '')[:1500]}" for m in prior[-10:]
                    )

            files_text = ""
            if user_id and file_ids:
                files = self.db.get_file_context(tenant_id, user_id, file_ids)
                if files:
                    files_text = "\n\nAttached file context:\n" + "\n\n".join(
                        f"FILE: {f['title']}\n{f['content']}" for f in files
                    )

            planner_hint = (
                "\nReasoning mode is enabled: examine multiple relevant metrics/dimensions before choosing the SQL, "
                "but still return one safe read-only query." if reasoning else ""
            )
            plan = self.gemini.generate_json(
                f"User question:\n{question}\n\nRetrieved semantic context:\n{semantic}{history_text}{files_text}{planner_hint}",
                system=PLAN_SYSTEM,
                temperature=0.0,
            )
            sql = str(plan.get("sql") or "")
            permissions = self.db.semantic_catalog_snapshot(tenant_id)["permissions"]
            allowed = None
            max_rows = 5000
            if permissions:
                allowed = {(p["schema_name"], p["table_name"]) for p in permissions}
                max_rows = min(max(int(p.get("max_rows") or 5000) for p in permissions), 5000)
            guard = SQLGuard(allowed_tables=allowed, max_rows=max_rows).validate(sql)
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
                    intent=plan.get("intent") if isinstance(plan.get("intent"), dict) else {"intent": plan.get("intent")},
                    selected_context={"chunks": [str(c["chunk_id"]) for c in context], "file_ids": file_ids or [], "reasoning": reasoning},
                    error_message=guard.reason,
                )
                raise RuntimeError(f"Generated SQL blocked: {guard.reason}")

            started = time.perf_counter()
            rows = self.db.execute_readonly_query(guard.sql, tenant_id)
            execution_ms = int((time.perf_counter() - started) * 1000)
            self.db.save_generated_query(
                tenant_id=tenant_id,
                query_run_id=query_run_id,
                sql_text=sql,
                validation_status="approved",
                execution_ms=execution_ms,
                row_count=len(rows),
                result_preview=rows[:50],
            )

            final = self.gemini.generate_json(
                "User question:\n"
                + question
                + "\n\nExecuted SQL:\n"
                + sql
                + "\n\nDatabase result JSON:\n"
                + json.dumps(rows[:200], default=str)
                + files_text,
                system=FINAL_SYSTEM,
                temperature=0.1,
            )
            dashboard = final.get("dashboard") if isinstance(final.get("dashboard"), dict) else {}
            title = str(dashboard.get("title") or plan.get("title") or "AI Analytics")
            saved_dashboard = self.db.save_dashboard_spec(
                tenant_id,
                query_run_id,
                title,
                str(final.get("answer") or ""),
                dashboard,
            )
            self.db.update_query_run(
                query_run_id,
                status="completed",
                route=plan.get("route"),
                intent=plan.get("intent") if isinstance(plan.get("intent"), dict) else {"intent": plan.get("intent")},
                selected_context={"chunks": [str(c["chunk_id"]) for c in context], "file_ids": file_ids or [], "reasoning": reasoning},
            )
            answer = str(final.get("answer") or "")
            if conversation_id:
                self.db.add_message(
                    tenant_id,
                    conversation_id,
                    "assistant",
                    answer,
                    {
                        "query_run_id": str(query_run_id),
                        "dashboard_id": str(saved_dashboard["id"]),
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
                "dashboard_id": str(saved_dashboard["id"]),
                "route": plan.get("route"),
                "reasoning": reasoning,
            }
        except Exception as exc:
            try:
                if not blocked:
                    self.db.update_query_run(query_run_id, status="failed", error_message=str(exc))
                if conversation_id:
                    self.db.add_message(
                        tenant_id,
                        conversation_id,
                        "assistant",
                        "I couldn't complete that analysis.",
                        {"error": str(exc)[:500], "query_run_id": str(query_run_id)},
                    )
            except Exception:
                pass
            raise
