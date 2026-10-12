from __future__ import annotations

from copy import deepcopy
import logging
import pytest

from commerce_connector.platform import ai_analyst
from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    _log_subquery_failure,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from tests.unit.platform import test_metric_resolver

_LOGGER_NAME = ai_analyst.logger.name

_VALID_SQL = (
    "select sum(ds.net_sales) as net_sales, "
    "case when sum(ds.orders_count)=0 then null else sum(ds.net_sales)/sum(ds.orders_count) end "
    "as average_order_value from gold.daily_sales ds where ds.tenant_id = :tenant_id "
    "and ds.metric_date >= current_date - interval '30 day'"
)
_VALID_SQL_WITH_CURRENCY = _VALID_SQL + " group by ds.currency_code"


def _kpi_plan(sql: str) -> dict:
    return {
        "route": "metric",
        "intent": {
            "metric": "average_order_value",
            "dimensions": [],
            "date_range": "last_30_days",
            "comparison": "none",
            "filters": [],
        },
        "sql": sql,
        "title": "Sales KPIs",
    }


def _kpi_final(prompt: str) -> dict:
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


def _make_test_analyst(monkeypatch, planner, final, *, execute_fn=None, profile_fn=None):
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    analyst = AIAnalyst(fake_db, fake_llm)
    snapshot = deepcopy(test_metric_resolver.REAL_REGISTRY_SNAPSHOT)
    fake_db.executed_sql = []
    snapshot["permissions"] = [
        {"schema_name": "gold", "table_name": "daily_sales", "max_rows": 500},
        {"schema_name": "gold", "table_name": "product_daily", "max_rows": 500},
        {"schema_name": "silver", "table_name": "orders", "max_rows": 500},
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

    if profile_fn:
        monkeypatch.setattr(fake_db, "get_data_profile_raw", profile_fn)

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
    return analyst, fake_db


def test_a_all_attempts_fail_validation_logs_and_returns_failure_keys(monkeypatch, caplog):
    """(a) all attempts fail with validation error -> caplog has 3 WARNING lines (1/3, 2/3, 3/3),
    each containing 'multiple currencies' and SQL snippet; final result dict has failure_reason and failed_sql."""
    profile_4 = {
        "daily_sales": {
            "currencies": [
                {"currency_code": "USD"},
                {"currency_code": "CAD"},
                {"currency_code": "EUR"},
                {"currency_code": "GBP"},
            ]
        }
    }

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        lambda prompt: _kpi_plan(_VALID_SQL),
        _kpi_final,
        profile_fn=lambda t: profile_4,
    )

    captured_outcomes = []
    orig_execute = ai_analyst._execute_subquery

    def spy_execute(*args, **kwargs):
        res = orig_execute(*args, **kwargs)
        captured_outcomes.append(res)
        return res

    monkeypatch.setattr(ai_analyst, "_execute_subquery", spy_execute)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    subquery_records = [
        r for r in caplog.records
        if "subquery attempt failed" in r.getMessage() and r.levelno == logging.WARNING
    ]
    assert len(subquery_records) == 3

    for idx, (attempt_str, record) in enumerate(zip(["1/3", "2/3", "3/3"], subquery_records), start=1):
        msg = record.getMessage()
        assert f"attempt={attempt_str}" in msg
        assert "multiple currencies" in msg
        assert "gold.daily_sales" in msg
        assert "kind=_SubqueryValidationError" in msg

    assert len(captured_outcomes) == 1
    final_dict = captured_outcomes[0]
    assert final_dict.get("failure") is True
    assert "failure_reason" in final_dict
    assert "failed_sql" in final_dict
    assert "multiple currencies" in final_dict["failure_reason"]
    assert "gold.daily_sales" in final_dict["failed_sql"]
    assert response["dashboard"]["no_data"] is True


def test_b_log_single_line_and_no_question_text(monkeypatch, caplog):
    """(b) the log does NOT contain the question text and is single-line (no newline characters)."""
    profile_4 = {
        "daily_sales": {
            "currencies": [
                {"currency_code": "USD"},
                {"currency_code": "CAD"},
                {"currency_code": "EUR"},
                {"currency_code": "GBP"},
            ]
        }
    }
    question = "Show revenue and average order value for the last 30 days"

    analyst, _ = _make_test_analyst(
        monkeypatch,
        lambda prompt: _kpi_plan(_VALID_SQL),
        _kpi_final,
        profile_fn=lambda t: profile_4,
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        analyst.ask("tenant-1", question)

    subquery_records = [
        r for r in caplog.records
        if "subquery attempt failed" in r.getMessage() and r.levelno == logging.WARNING
    ]
    assert len(subquery_records) == 3
    for record in subquery_records:
        msg = record.getMessage()
        assert "\n" not in msg
        assert "\r" not in msg
        assert question not in msg


def test_c_long_reason_and_sql_truncated(caplog):
    """(c) a long reason/SQL is truncated to 300/400 chars, whitespace collapsed, truncate after sanitise."""
    long_reason = "Error: " + ("reason_tail " * 40)  # > 400 chars with newlines/tabs
    long_reason_with_ws = f"multi\nline\r\terror\t   {long_reason}"
    long_sql = "SELECT " + ("column_long_name, " * 40) + " FROM gold.daily_sales"  # > 600 chars

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        reason, sql = _log_subquery_failure(
            "tenant-xyz",
            0,
            "CustomError",
            long_reason_with_ws,
            long_sql,
        )

    assert len(reason) <= 300
    assert len(sql) <= 400
    assert "\n" not in reason
    assert "\r" not in reason
    assert "\t" not in reason
    assert "   " not in reason
    assert "\n" not in sql

    rec = [r for r in caplog.records if "subquery attempt failed" in r.getMessage()][-1]
    msg = rec.getMessage()
    assert "\n" not in msg
    assert f"kind=CustomError" in msg
    assert f"reason={reason}" in msg
    assert f"sql={sql}" in msg


def test_d_successful_first_attempt_produces_no_subquery_failed_log(monkeypatch, caplog):
    """(d) a successful first attempt produces no 'subquery attempt failed' log."""
    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        lambda prompt: _kpi_plan(_VALID_SQL),
        _kpi_final,
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    subquery_records = [
        r for r in caplog.records
        if "subquery attempt failed" in r.getMessage()
    ]
    assert subquery_records == []
    assert response["sql"] == _VALID_SQL


class FakeDBExecutionError(Exception):
    pass


def test_e_db_execution_error_produces_3_log_lines_with_exception_class(monkeypatch, caplog):
    """(e) a DB-execution error on every attempt also produces 3 log lines with kind equal to the exception class name."""
    def fail_execute(sql, tenant_id):
        raise FakeDBExecutionError("relation 'daily_sales' does not exist")

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        lambda prompt: _kpi_plan(_VALID_SQL),
        _kpi_final,
        execute_fn=fail_execute,
    )

    captured_outcomes = []
    orig_execute = ai_analyst._execute_subquery

    def spy_execute(*args, **kwargs):
        res = orig_execute(*args, **kwargs)
        captured_outcomes.append(res)
        return res

    monkeypatch.setattr(ai_analyst, "_execute_subquery", spy_execute)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    subquery_records = [
        r for r in caplog.records
        if "subquery attempt failed" in r.getMessage() and r.levelno == logging.WARNING
    ]
    assert len(subquery_records) == 3

    for attempt_str, record in zip(["1/3", "2/3", "3/3"], subquery_records):
        msg = record.getMessage()
        assert f"attempt={attempt_str}" in msg
        assert "kind=FakeDBExecutionError" in msg
        assert "relation 'daily_sales' does not exist" in msg

    assert len(captured_outcomes) == 1
    final_dict = captured_outcomes[0]
    assert final_dict.get("failure") is True
    assert final_dict.get("failure_reason") == "relation 'daily_sales' does not exist"
    assert "gold.daily_sales" in final_dict.get("failed_sql", "")


def test_f_unexpected_value_error_propagates_and_logs(monkeypatch, caplog):
    """The LLM-returned SQL path raises an unexpected ValueError from a mocked dependency inside the loop
    -> propagates out of _execute_subquery (pytest.raises(ValueError)), and one warning with kind=ValueError logged."""
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    snapshot = deepcopy(test_metric_resolver.REAL_REGISTRY_SNAPSHOT)
    snapshot["permissions"] = [
        {"schema_name": "gold", "table_name": "daily_sales", "max_rows": 500},
    ]

    def mock_filter(question, sql):
        raise ValueError("unexpected dependency failure")

    monkeypatch.setattr(ai_analyst, "_enforce_relative_date_filter", mock_filter)
    monkeypatch.setattr(
        fake_llm,
        "generate_json",
        lambda *a, **kw: _kpi_plan(_VALID_SQL),
    )

    task = {"metrics": [], "source": "gold.daily_sales"}
    resolution = type("Res", (), {"ok": True, "metrics": [], "matched": []})()

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        with pytest.raises(ValueError, match="unexpected dependency failure"):
            ai_analyst._execute_subquery(
                llm=fake_llm,
                db=fake_db,
                tenant_id="tenant-1",
                query_run_id="run-1",
                question="Show revenue",
                task=task,
                snapshot=snapshot,
                resolution=resolution,
                context_text="",
                history_text="",
                files_text="",
                reasoning=False,
            )

    subquery_records = [
        r for r in caplog.records
        if "subquery attempt failed" in r.getMessage() and r.levelno == logging.WARNING
    ]
    assert len(subquery_records) == 1
    msg = subquery_records[0].getMessage()
    assert "kind=ValueError" in msg
    assert "unexpected dependency failure" in msg
    assert "attempt=1/3" in msg

