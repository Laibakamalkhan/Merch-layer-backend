from __future__ import annotations

from copy import deepcopy
import psycopg.errors
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import test_metric_resolver

from commerce_connector.api.app import create_app
from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    _enforce_relative_date_filter,
    _SubqueryValidationError,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from commerce_connector.platform.rag import RagRetriever


def _make_test_analyst(monkeypatch, planner, final, *, execute_fn=None):
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    analyst = AIAnalyst(fake_db, fake_llm)
    snapshot = deepcopy(test_metric_resolver.REAL_REGISTRY_SNAPSHOT)
    fake_db.executed_sql = []
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
    monkeypatch.setattr(fake_db, "create_query_run", lambda *a, **k: {"id": "run-test"})
    monkeypatch.setattr(fake_db, "save_generated_query", lambda *a, **k: {"id": "gen-1"})
    monkeypatch.setattr(fake_db, "save_dashboard_spec", lambda *a, **k: {"id": "dash-test"})
    monkeypatch.setattr(fake_db, "update_query_run", lambda *a, **k: None)

    def default_execute(sql, tenant_id):
        fake_db.executed_sql.append(sql)
        if execute_fn:
            return execute_fn(sql, tenant_id)
        return [{"net_sales": 500, "orders": 10, "average_order_value": 50}]

    monkeypatch.setattr(fake_db, "execute_readonly_query", default_execute)

    def generate_json(prompt, **kwargs):
        if kwargs.get("schema_name") == "analytics_query_plan":
            return planner(prompt)
        return final(prompt)

    monkeypatch.setattr(fake_llm, "generate_json", generate_json)
    return analyst


def _kpi_plan(sql, metric="average_order_value", title="Sales KPIs"):
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


def _kpi_final(prompt):
    return {
        "answer": "The verified KPI results are ready.",
        "dashboard": {
            "title": "Sales Overview",
            "kpis": [
                {"label": "Net sales", "column": "net_sales", "aggregation": "value"},
                {"label": "Average order value", "column": "average_order_value", "aggregation": "value"},
            ],
            "charts": [],
            "filters": [],
        },
    }


_VALID_SQL = (
    "select sum(ds.net_sales) as net_sales, "
    "case when sum(ds.orders_count)=0 then null else sum(ds.net_sales)/sum(ds.orders_count) end "
    "as average_order_value from gold.daily_sales ds where ds.tenant_id = :tenant_id "
    "and ds.metric_date >= current_date - interval '30 day'"
)


def test_question_without_breakdown_retries_invalid_sql_then_succeeds(monkeypatch):
    """Question without breakdown uses retry: first SQL invalid, second valid -> success."""
    invalid_sql = _VALID_SQL.replace("ds.tenant_id = :tenant_id and ", "")
    answers = iter([
        _kpi_plan(invalid_sql),
        _kpi_plan(_VALID_SQL),
    ])
    analyst = _make_test_analyst(
        monkeypatch,
        lambda prompt: next(answers),
        _kpi_final,
    )

    response = analyst.ask("tenant-1", "show revenue and average order value for last 30 days")

    assert response["sql"] == _VALID_SQL
    assert response["dashboard"]["kpis"][0]["value"] == 500
    assert "verified KPI results" in response["answer"]


def test_db_execution_error_attempt_1_retried_and_succeeds(monkeypatch):
    """DB execution error on attempt 1, valid SQL attempt 2 -> success."""
    prompts = []
    attempt_count = 0

    def planner(prompt):
        prompts.append(prompt)
        return _kpi_plan(_VALID_SQL)

    def execute_query(sql, tenant_id):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
        return [{"net_sales": 500, "average_order_value": 50}]

    analyst = _make_test_analyst(
        monkeypatch,
        planner,
        _kpi_final,
        execute_fn=execute_query,
    )

    response = analyst.ask("tenant-1", "show revenue and average order value for last 30 days")

    assert len(prompts) == 2
    assert "Validation error:" in prompts[1]
    assert "Database query execution failed" in prompts[1]
    assert response["dashboard"]["kpis"][0]["value"] == 500
    assert "verified KPI results" in response["answer"]


def test_db_execution_error_all_attempts_returns_friendly_partial_result(monkeypatch):
    """DB error on all attempts -> partial friendly result, no exception text in answer/dashboard/response."""
    def planner(prompt):
        return _kpi_plan(_VALID_SQL)

    def execute_query(sql, tenant_id):
        raise psycopg.errors.UndefinedColumn("relation gold.daily_sales column ds.non_existent does not exist")

    analyst = _make_test_analyst(
        monkeypatch,
        planner,
        _kpi_final,
        execute_fn=execute_query,
    )

    response = analyst.ask("tenant-1", "show revenue and average order value for last 30 days")

    assert response["dashboard"]["no_data"] is True
    assert "couldn't produce" in response["answer"].lower()
    # Ensure no exception class name, stack trace, or raw DB error leaked
    assert "undefinedcolumn" not in response["answer"].lower()
    assert "non_existent" not in response["answer"].lower()
    assert "traceback" not in response["answer"].lower()
    assert "exception" not in response["answer"].lower()


def test_relative_period_asked_without_metric_date_filter_is_retried(monkeypatch):
    """Relative period asked but SQL lacks metric_date filter -> retried with feedback; SQL with filter accepted."""
    sql_without_date = (
        "select sum(ds.net_sales) as net_sales, "
        "case when sum(ds.orders_count)=0 then null else sum(ds.net_sales)/sum(ds.orders_count) end "
        "as average_order_value from gold.daily_sales ds where ds.tenant_id = :tenant_id"
    )
    prompts = []
    answers = iter([
        _kpi_plan(sql_without_date),
        _kpi_plan(_VALID_SQL),
    ])

    def planner(prompt):
        prompts.append(prompt)
        return next(answers)

    analyst = _make_test_analyst(
        monkeypatch,
        planner,
        _kpi_final,
    )

    response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    assert len(prompts) == 2
    assert "SQL must filter metric_date for the requested period" in prompts[1]
    assert response["sql"] == _VALID_SQL
    assert response["dashboard"]["kpis"][0]["value"] == 500


def test_no_relative_period_asked_does_not_require_metric_date_filter(monkeypatch):
    """No period asked -> no date check enforcement."""
    sql_without_date = (
        "select sum(ds.net_sales) as net_sales, "
        "case when sum(ds.orders_count)=0 then null else sum(ds.net_sales)/sum(ds.orders_count) end "
        "as average_order_value from gold.daily_sales ds where ds.tenant_id = :tenant_id"
    )
    analyst = _make_test_analyst(
        monkeypatch,
        lambda prompt: _kpi_plan(sql_without_date),
        _kpi_final,
    )

    # Question without relative period
    response = analyst.ask("tenant-1", "What is the net sales and average order value?")
    assert response["sql"] == sql_without_date
    assert response["dashboard"]["kpis"][0]["value"] == 500


def test_500_response_body_has_no_class_name_and_has_request_id():
    """500 response body has no class name and has request_id."""
    app = create_app()

    @app.get("/test-internal-error")
    def faulty_endpoint():
        raise ZeroDivisionError("division by zero in test")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-internal-error")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Something went wrong. Please try again."
    assert "request_id" in body
    assert isinstance(body["request_id"], str)
    assert len(body["request_id"]) == 8
    assert "ZeroDivisionError" not in response.text
    assert "division by zero" not in response.text


def test_rag_default_min_similarity_is_0_20(monkeypatch):
    """RAG default min_similarity is 0.20."""
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)

    monkeypatch.setattr(fake_llm, "embed", lambda text, task="query": [0.1] * 1536)

    captured_kwargs = {}

    def fake_match_chunks(tenant_id, embedding, count=8, min_similarity=None):
        captured_kwargs["tenant_id"] = tenant_id
        captured_kwargs["count"] = count
        captured_kwargs["min_similarity"] = min_similarity
        return [{"chunk_id": "c1", "title": "Doc", "similarity": 0.85, "content": "Content"}]

    monkeypatch.setattr(fake_db, "match_chunks", fake_match_chunks)

    retriever = RagRetriever(fake_db, fake_llm)
    results = retriever.retrieve("tenant-1", "sales question", count=10)

    assert len(results) == 1
    assert captured_kwargs["min_similarity"] == 0.20
    assert captured_kwargs["count"] == 10
