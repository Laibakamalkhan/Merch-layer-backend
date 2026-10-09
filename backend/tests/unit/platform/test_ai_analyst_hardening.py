from __future__ import annotations

from copy import deepcopy
import psycopg.errors
import pytest

import test_metric_resolver

from commerce_connector.api.ai_helpers import map_ai_exception
from commerce_connector.platform.ai_analyst import AIAnalyst
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.groq import GroqAPIError
from commerce_connector.platform.llm import LLMClient


def _make_hardening_analyst(monkeypatch, planner, final, *, execute_fn=None):
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    analyst = AIAnalyst(fake_db, fake_llm)
    snapshot = deepcopy(test_metric_resolver.REAL_REGISTRY_SNAPSHOT)
    fake_db.executed_sql = []
    fake_db.update_query_run_calls = []
    snapshot["permissions"] = [
        {"schema_name": "gold", "table_name": "daily_sales", "max_rows": 500},
        {"schema_name": "gold", "table_name": "refund_daily", "max_rows": 500},
    ]

    monkeypatch.setattr(
        analyst.retriever,
        "retrieve",
        lambda *a, **k: [
            {"chunk_id": "ctx-1", "title": "Sales", "similarity": 0.9, "content": "Sales context"}
        ],
    )
    monkeypatch.setattr(fake_db, "semantic_catalog_snapshot", lambda *a: snapshot)
    monkeypatch.setattr(fake_db, "create_query_run", lambda *a, **k: {"id": "run-harden"})
    monkeypatch.setattr(fake_db, "save_generated_query", lambda *a, **k: {"id": "gen-harden"})
    monkeypatch.setattr(fake_db, "save_dashboard_spec", lambda *a, **k: {"id": "dash-harden"})

    def update_query_run(run_id, **kwargs):
        fake_db.update_query_run_calls.append({"run_id": run_id, **kwargs})

    monkeypatch.setattr(fake_db, "update_query_run", update_query_run)

    def default_execute(sql, tenant_id):
        fake_db.executed_sql.append(sql)
        if execute_fn:
            return execute_fn(sql, tenant_id)
        if "refund_daily" in sql:
            return [{"refund_rate": 0.05}]
        return [{"net_sales": 800, "average_order_value": 80}]

    monkeypatch.setattr(fake_db, "execute_readonly_query", default_execute)

    def generate_json(prompt, **kwargs):
        if kwargs.get("schema_name") == "analytics_query_plan":
            return planner(prompt)
        return final(prompt)

    monkeypatch.setattr(fake_llm, "generate_json", generate_json)
    return analyst, fake_db, fake_llm


def _plan(sql, metric="average_order_value", title="Sales KPIs"):
    return {
        "route": "metric",
        "intent": {
            "metric": metric,
            "dimensions": [],
            "date_range": "last_30_days",
            "comparison": "none",
            "filters": [],
        },
        "sql": sql,
        "title": title,
    }


def _final(prompt):
    return {
        "answer": "The verified KPI results are ready.",
        "dashboard": {
            "title": "Sales Overview",
            "kpis": [
                {"label": "Net sales", "column": "net_sales", "aggregation": "value"},
            ],
            "charts": [],
            "filters": [],
        },
    }


def test_all_attempts_fail_marks_status_failed_and_caps_retries_at_3(monkeypatch):
    """All attempts fail -> response friendly, update_query_run has status 'failed', planner called 3 times."""
    planner_calls = []
    invalid_sql = "select sum(net_sales) from gold.daily_sales where metric_date >= current_date - interval '30 day'"

    def planner(prompt):
        planner_calls.append(prompt)
        return _plan(invalid_sql)

    analyst, fake_db, _ = _make_hardening_analyst(monkeypatch, planner, _final)

    response = analyst.ask("tenant-1", "show revenue for last 30 days")

    assert len(planner_calls) == 3
    assert len(fake_db.update_query_run_calls) == 1
    last_update = fake_db.update_query_run_calls[0]
    assert last_update["status"] == "failed"
    assert "failed validation or execution" in last_update["error_message"]
    assert last_update["selected_context"]["partial"] is True
    assert response["dashboard"]["no_data"] is True
    assert "couldn't produce" in response["answer"].lower()


def test_one_of_two_subqueries_fails_marks_status_completed_and_partial_true(monkeypatch):
    """One of two sub-queries fails -> status 'completed' and selected_context partial True."""
    valid_sales_sql = (
        "select sum(ds.net_sales) as net_sales from gold.daily_sales ds "
        "where ds.tenant_id = :tenant_id"
    )
    invalid_refund_sql = (
        "select rd.refund_rate as refund_rate from gold.refund_daily rd "
        "where true"  # Missing tenant filter
    )

    def planner(prompt):
        if "from gold.refund_daily" in prompt:
            return _plan(invalid_refund_sql, metric="refund_rate", title="Refund Rate")
        return _plan(valid_sales_sql, metric="revenue", title="Revenue")

    def execute_query(sql, tenant_id):
        return [{"revenue": 400, "net_sales": 400}]

    analyst, fake_db, _ = _make_hardening_analyst(
        monkeypatch,
        planner,
        lambda p: {
            "answer": "Net sales verified.",
            "dashboard": {
                "title": "Sales",
                "kpis": [{"label": "Net sales", "column": "net_sales", "aggregation": "value"}],
                "charts": [],
                "filters": [],
            },
        },
        execute_fn=execute_query,
    )

    response = analyst.ask("tenant-1", "Show revenue and refund percentage")

    assert len(fake_db.update_query_run_calls) == 1
    last_update = fake_db.update_query_run_calls[0]
    assert last_update["status"] == "completed"
    assert last_update["selected_context"]["partial"] is True
    assert len(response["dashboard"]["kpis"]) == 1
    assert response["dashboard"]["kpis"][0]["value"] == 400
    assert "couldn't produce one requested section" in response["answer"]


def test_strengthened_date_filter_predicate_enforcement(monkeypatch):
    """Date filter: SELECT/GROUP BY bare metric_date retried; >= and BETWEEN predicates accepted; no period -> no check."""
    bare_metric_date_sql = (
        "select ds.metric_date, sum(ds.net_sales) as net_sales from gold.daily_sales ds "
        "where ds.tenant_id = :tenant_id group by ds.metric_date"
    )
    between_sql = (
        "select sum(ds.net_sales) as net_sales from gold.daily_sales ds "
        "where ds.tenant_id = :tenant_id and ds.metric_date between current_date - interval '30 day' and current_date"
    )
    gte_sql = (
        "select sum(ds.net_sales) as net_sales from gold.daily_sales ds "
        "where ds.tenant_id = :tenant_id and ds.metric_date >= current_date - interval '30 day'"
    )

    # 1. Bare metric_date in SELECT / GROUP BY must fail date check and be retried
    prompts = []
    answers = iter([
        _plan(bare_metric_date_sql),
        _plan(gte_sql),
    ])
    analyst, _, _ = _make_hardening_analyst(
        monkeypatch,
        lambda p: (prompts.append(p), next(answers))[1],
        _final,
    )
    res1 = analyst.ask("tenant-1", "Show revenue for the last 30 days")
    assert len(prompts) == 2
    assert "SQL must filter metric_date for the requested period" in prompts[1]
    assert res1["sql"] == gte_sql

    # 2. BETWEEN predicate is accepted on first attempt
    analyst2, _, _ = _make_hardening_analyst(
        monkeypatch,
        lambda p: _plan(between_sql),
        _final,
    )
    res2 = analyst2.ask("tenant-1", "Show revenue for the past 30 days")
    assert res2["sql"] == between_sql

    # 3. No relative period asked -> no date filter check enforced
    analyst3, _, _ = _make_hardening_analyst(
        monkeypatch,
        lambda p: _plan("select sum(ds.net_sales) as net_sales from gold.daily_sales ds where ds.tenant_id = :tenant_id"),
        _final,
    )
    res3 = analyst3.ask("tenant-1", "What is the overall total revenue?")
    assert "metric_date" not in res3["sql"]
    assert res3["dashboard"]["kpis"][0]["value"] == 800


def test_final_answer_llm_failure_uses_fallback_answer_and_preserves_dashboard(monkeypatch):
    """Final-answer LLM raises -> response still has dashboard with KPIs and fixed fallback answer, no exception text."""
    valid_sql = (
        "select sum(ds.net_sales) as net_sales from gold.daily_sales ds "
        "where ds.tenant_id = :tenant_id"
    )

    def planner(prompt):
        return _plan(valid_sql)

    def faulty_final(prompt):
        raise RuntimeError("LLM service unavailable SECRET_INTERNAL_DETAIL")

    analyst, _, _ = _make_hardening_analyst(
        monkeypatch,
        planner,
        faulty_final,
    )

    response = analyst.ask("tenant-1", "What is the total revenue?")

    assert response["dashboard"]["kpis"][0]["value"] == 800
    assert response["answer"] == "Here are the verified results for your request."
    assert "SECRET_INTERNAL_DETAIL" not in response["answer"]
    assert "RuntimeError" not in response["answer"]


def test_map_ai_exception_sanitizes_class_names_and_provider_bodies():
    """map_ai_exception: details contain neither class names nor bodies; status codes unchanged."""
    # 1. ZeroDivisionError (unexpected generic exception)
    exc1 = ZeroDivisionError("division by zero SECRET_MSG")
    http_exc1 = map_ai_exception(exc1)
    assert http_exc1.status_code == 500
    assert http_exc1.detail == "Something went wrong. Please try again."
    assert "ZeroDivisionError" not in http_exc1.detail
    assert "SECRET_MSG" not in http_exc1.detail

    # 2. psycopg.Error subclass
    exc2 = psycopg.errors.UndefinedTable("relation gold.secret_table does not exist")
    http_exc2 = map_ai_exception(exc2)
    assert http_exc2.status_code == 500
    assert http_exc2.detail == "A database error occurred. Please try again."
    assert "UndefinedTable" not in http_exc2.detail
    assert "secret_table" not in http_exc2.detail

    # 3. GroqAPIError with secret body
    exc3 = GroqAPIError(429, "Rate limit exceeded SECRETBODY")
    http_exc3 = map_ai_exception(exc3)
    assert http_exc3.status_code == 429
    assert http_exc3.detail == "The AI provider returned an error. Please try again."
    assert "SECRETBODY" not in http_exc3.detail
    assert "GroqAPIError" not in http_exc3.detail
