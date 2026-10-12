from __future__ import annotations

from copy import deepcopy
import pytest

from commerce_connector.platform import ai_analyst
from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    _collect_sql_policy_violations,
    _enforce_allowed_bind_params,
    _enforce_single_currency,
    _question_mentions_period,
    _SubqueryValidationError,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from tests.unit.platform import test_metric_resolver


_SQL_CURRENT_DATE_NO_CURR = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id "
    "and pd.metric_date >= (CURRENT_DATE - INTERVAL '30 days') "
    "group by 1 order by 2 desc limit 5"
)

_SQL_CLEAN = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id "
    "group by pd.product_title, pd.currency_code order by 2 desc limit 5"
)

_SQL_CLEAN_SINGLE_CURR = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id "
    "group by pd.product_title order by 2 desc limit 5"
)


def _product_plan(sql: str) -> dict:
    return {
        "route": "metric",
        "intent": {
            "metric": "net_sales",
            "dimensions": ["product_title"],
            "date_range": "all_time",
            "comparison": "none",
            "filters": [],
        },
        "sql": sql,
        "title": "Top 5 Products by Revenue",
    }


def _product_final(prompt: str) -> dict:
    return {
        "answer": "The top products by revenue are ready.",
        "dashboard": {
            "title": "Top Products",
            "kpis": [],
            "charts": [
                {
                    "title": "Top 5 Products by Revenue",
                    "type": "bar",
                    "x": "product_title",
                    "y": ["net_sales"],
                }
            ],
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
            {"chunk_id": "ctx-1", "title": "Products", "similarity": 0.9, "content": "Products context"}
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
        return [{"product_title": "Shirt", "net_sales": 1000}]

    monkeypatch.setattr(fake_db, "execute_readonly_query", default_execute)

    def generate_json(prompt, **kwargs):
        if kwargs.get("schema_name") == "analytics_query_plan":
            return planner(prompt)
        return final(prompt)

    monkeypatch.setattr(fake_llm, "generate_json", generate_json)
    return analyst, fake_db


# a) collect: question "top 5 products by revenue", 4 currencies, SQL with CURRENT_DATE window and no currency_code
# -> ONE raised error in the flow containing BOTH "multiple currencies" and "do not filter by today's date" with "(1)" and "(2)".
def test_a_collect_multiple_violations_flow(monkeypatch):
    currencies_4 = ["USD", "CAD", "EUR", "GBP"]
    profile_4 = {
        "daily_sales": {
            "currencies": [{"currency_code": c} for c in currencies_4]
        }
    }

    answers = iter([
        _product_plan(_SQL_CURRENT_DATE_NO_CURR),
        _product_plan(_SQL_CLEAN),
    ])
    prompts = []

    def planner(p):
        prompts.append(p)
        return next(answers)

    analyst, _ = _make_test_analyst(monkeypatch, planner, _product_final, profile_fn=lambda t: profile_4)
    analyst.ask("tenant-1", "top 5 products by revenue")

    assert len(prompts) == 2
    retry_prompt = prompts[1]
    assert "(1) This workspace has multiple currencies" in retry_prompt
    assert "(2) The question does not ask for a specific period, so do not filter by today's date" in retry_prompt


# b) collect: exactly one violation -> list has 1 item and its text is identical to the single helper's message.
def test_b_collect_single_violation_identical_message():
    currencies_4 = ["USD", "CAD", "EUR", "GBP"]
    # Question has period, so date-window won't fire. SQL has money but no currency_code.
    question = "top 5 products in the last 30 days"
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id = :tenant_id AND metric_date >= current_date - interval '30 day'"
    violations = _collect_sql_policy_violations(question, sql, currencies_4)
    assert len(violations) == 1

    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_single_currency(sql, currencies_4)
    assert violations[0] == str(exc_info.value)


# c) collect: clean SQL -> empty list.
def test_c_collect_clean_sql_empty():
    question = "top 5 products by revenue"
    currencies_4 = ["USD", "CAD", "EUR", "GBP"]
    violations = _collect_sql_policy_violations(question, _SQL_CLEAN, currencies_4)
    assert violations == []


# d) bind check: ":connection_id" is flagged; "::date", "::text", "'12:30'", ":tenant_id", "arr[1:2]", "x[a:b]", "CAST(x AS date)", "'a :foo b'", "'it''s :foo'" are not.
def test_d_bind_check():
    # Flagged
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_allowed_bind_params("SELECT * FROM orders WHERE connection_id = :connection_id")
    assert str(exc_info.value) == "Only the :tenant_id bind parameter is allowed; remove :connection_id."

    with pytest.raises(_SubqueryValidationError) as exc_info2:
        _enforce_allowed_bind_params("WHERE tenant_id = :tenant_id AND y = :other")
    assert str(exc_info2.value) == "Only the :tenant_id bind parameter is allowed; remove :other."

    # Max 3, sorted, deduped
    with pytest.raises(_SubqueryValidationError) as exc_info3:
        _enforce_allowed_bind_params("SELECT :d, :b, :c, :a, :b")
    assert str(exc_info3.value) == "Only the :tenant_id bind parameter is allowed; remove :a, :b, :c."

    # Not flagged
    _enforce_allowed_bind_params("SELECT arr[1:2], x[a:b]")
    _enforce_allowed_bind_params("SELECT CAST(x AS date), x::date, x::text")
    _enforce_allowed_bind_params("SELECT '12:30', 'a :foo b', 'it''s :foo'")
    _enforce_allowed_bind_params("SELECT * FROM gold.daily_sales WHERE tenant_id = :tenant_id")
    _enforce_allowed_bind_params("/* :bad_param */ SELECT :tenant_id -- :also_bad")


# e) flow: LLM first returns SQL with both problems, second returns SQL fixing both -> success on attempt 2, execute_readonly_query called once with the second SQL.
def test_e_flow_two_attempts_success(monkeypatch):
    currencies_4 = ["USD", "CAD", "EUR", "GBP"]
    profile_4 = {
        "daily_sales": {
            "currencies": [{"currency_code": c} for c in currencies_4]
        }
    }

    answers = iter([
        _product_plan(_SQL_CURRENT_DATE_NO_CURR),
        _product_plan(_SQL_CLEAN),
    ])
    prompts = []

    def planner(p):
        prompts.append(p)
        return next(answers)

    analyst, fake_db = _make_test_analyst(monkeypatch, planner, _product_final, profile_fn=lambda t: profile_4)
    res = analyst.ask("tenant-1", "top 5 products by revenue")

    assert res["sql"] == _SQL_CLEAN
    assert res["answer"] == "The top products by revenue are ready."
    assert len(prompts) == 2
    assert len(fake_db.executed_sql) == 1
    assert "currency_code" in fake_db.executed_sql[0]
    assert "CURRENT_DATE" not in fake_db.executed_sql[0]


# f) flow: three attempts; verify the THIRD prompt contains the error texts from attempt 1 and attempt 2 ("Earlier errors that must STILL be avoided").
def test_f_flow_three_attempts_earlier_errors(monkeypatch):
    currencies_4 = ["USD", "CAD", "EUR", "GBP"]
    profile_4 = {
        "daily_sales": {
            "currencies": [{"currency_code": c} for c in currencies_4]
        }
    }

    # Attempt 1: bad currency & bad date (composite violation A)
    # Attempt 2: bad bind param (violation B)
    # Attempt 3: clean SQL
    sql_bad_bind = "select pd.product_title, sum(pd.net_sales) as net_sales from gold.product_daily pd where pd.tenant_id = :tenant_id and pd.conn = :connection_id group by pd.product_title, pd.currency_code"

    answers = iter([
        _product_plan(_SQL_CURRENT_DATE_NO_CURR),
        _product_plan(sql_bad_bind),
        _product_plan(_SQL_CLEAN),
    ])
    prompts = []

    def planner(p):
        prompts.append(p)
        return next(answers)

    analyst, fake_db = _make_test_analyst(monkeypatch, planner, _product_final, profile_fn=lambda t: profile_4)
    res = analyst.ask("tenant-1", "top 5 products by revenue")

    assert res["sql"] == _SQL_CLEAN
    assert len(prompts) == 3

    # Attempt 1 prompt: no validation feedback
    assert "Validation feedback for the previous attempt:" not in prompts[0]

    # Attempt 2 prompt: feedback from attempt 1 only, no "Earlier errors" block
    assert "Validation feedback for the previous attempt:" in prompts[1]
    assert "(1) This workspace has multiple currencies" in prompts[1]
    assert "Earlier errors that must STILL be avoided in the new SQL:" not in prompts[1]

    # Attempt 3 prompt: feedback for attempt 2 + Earlier errors block with attempt 1
    prompt_3 = prompts[2]
    assert "Validation feedback for the previous attempt:" in prompt_3
    assert "Only the :tenant_id bind parameter is allowed; remove :connection_id." in prompt_3
    assert "Earlier errors that must STILL be avoided in the new SQL:" in prompt_3
    assert "- (1) This workspace has multiple currencies" in prompt_3


# g) flow: the FIRST prompt contains the currency hint and the "no period" hint when 4 currencies and question "top 5 products by revenue";
# and contains neither when 1 currency and question "top 5 products in the last 30 days".
def test_g_flow_hints_in_first_prompt(monkeypatch):
    # Part 1: 4 currencies + no period
    currencies_4 = ["USD", "CAD", "EUR", "GBP"]
    profile_4 = {
        "daily_sales": {
            "currencies": [{"currency_code": c} for c in currencies_4]
        }
    }
    prompts_1 = []

    def planner_1(p):
        prompts_1.append(p)
        return _product_plan(_SQL_CLEAN)

    analyst_1, _ = _make_test_analyst(monkeypatch, planner_1, _product_final, profile_fn=lambda t: profile_4)
    analyst_1.ask("tenant-1", "top 5 products by revenue")

    first_prompt_1 = prompts_1[0]
    assert "This workspace has multiple currencies (CAD, EUR, GBP, USD). Every money total must GROUP BY currency_code or filter one currency_code; never add amounts across currencies." in first_prompt_1
    assert "The question names no period: do not filter metric_date by CURRENT_DATE or NOW(); use all available data." in first_prompt_1
    assert "The only allowed bind parameter is :tenant_id." in first_prompt_1

    # Part 2: 1 currency + question mentions period ("top 5 products in the last 30 days")
    profile_1 = {
        "daily_sales": {
            "currencies": [{"currency_code": "USD"}]
        }
    }
    prompts_2 = []

    def planner_2(p):
        prompts_2.append(p)
        return _product_plan(_SQL_CLEAN_SINGLE_CURR)

    analyst_2, _ = _make_test_analyst(monkeypatch, planner_2, _product_final, profile_fn=lambda t: profile_1)
    analyst_2.ask("tenant-1", "top 5 products in the last 30 days")

    first_prompt_2 = prompts_2[0]
    assert "This workspace has multiple currencies" not in first_prompt_2
    assert "The question names no period:" not in first_prompt_2
    assert "The only allowed bind parameter is :tenant_id." in first_prompt_2


# h) _question_mentions_period: "revenue this month" True, "total revenue" False.
def test_h_question_mentions_period():
    assert _question_mentions_period("revenue this month") is True
    assert _question_mentions_period("total revenue") is False


# Extra tests per Nuance:
# 1. A monkeypatched _enforce_single_currency that raises ValueError still propagates out of _execute_subquery.
def test_extra_enforce_single_currency_unexpected_error_propagates(monkeypatch):
    fake_db = PostgresGateway.__new__(PostgresGateway)
    fake_llm = LLMClient.__new__(LLMClient)
    fake_llm.model = "test-model"
    snapshot = deepcopy(test_metric_resolver.REAL_REGISTRY_SNAPSHOT)
    snapshot["permissions"] = [
        {"schema_name": "gold", "table_name": "daily_sales", "max_rows": 500},
    ]

    def mock_currency(sql, currencies):
        raise ValueError("currency check dependency failure")

    monkeypatch.setattr(ai_analyst, "_enforce_single_currency", mock_currency)
    monkeypatch.setattr(
        fake_llm,
        "generate_json",
        lambda *a, **kw: _product_plan(_SQL_CLEAN),
    )

    task = {"metrics": [], "source": "gold.daily_sales"}
    resolution = type("Res", (), {"ok": True, "metrics": [], "matched": []})()

    with pytest.raises(ValueError, match="currency check dependency failure"):
        ai_analyst._execute_subquery(
            llm=fake_llm,
            db=fake_db,
            tenant_id="tenant-1",
            query_run_id="run-1",
            question="top 5 products by revenue",
            task=task,
            snapshot=snapshot,
            resolution=resolution,
            context_text="",
            history_text="",
            files_text="",
            reasoning=False,
            currencies=["USD", "CAD"],
        )


# 2. Bind check swallows an internal error (monkeypatch regex helper to raise) and still returns the other violations.
def test_extra_bind_check_swallows_internal_error_and_returns_other_violations(monkeypatch):
    def broken_sanitize(sql):
        raise RuntimeError("regex sanitizer crashed")

    monkeypatch.setattr(ai_analyst, "_sanitize_sql_for_bind_params", broken_sanitize)

    # question has no period, SQL uses CURRENT_DATE -> date-window violation should still be collected
    violations = _collect_sql_policy_violations(
        "top 5 products by revenue",
        _SQL_CURRENT_DATE_NO_CURR,
        ["USD"],
    )
    assert len(violations) == 1
    assert "do not filter by today's date" in violations[0]
