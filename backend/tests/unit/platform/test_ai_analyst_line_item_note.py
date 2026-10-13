from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock
import pytest

from commerce_connector.platform import ai_analyst
from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    _extract_tenant_currencies,
    _line_item_note,
    _references_product_tables,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from tests.unit.platform import test_metric_resolver


def _product_plan(sql: str) -> dict[str, Any]:
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


def _product_final(prompt: str) -> dict[str, Any]:
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


def _sales_plan(sql: str) -> dict[str, Any]:
    return {
        "route": "metric",
        "intent": {
            "metric": "net_sales",
            "dimensions": [],
            "date_range": "all_time",
            "comparison": "none",
            "filters": [],
        },
        "sql": sql,
        "title": "Total Net Sales",
    }


def _sales_final(prompt: str) -> dict[str, Any]:
    return {
        "answer": "Here are the sales totals.",
        "dashboard": {
            "title": "Sales Overview",
            "kpis": [{"label": "Net sales", "column": "net_sales", "aggregation": "value"}],
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
        {"schema_name": "silver", "table_name": "order_items", "max_rows": 500},
    ]

    monkeypatch.setattr(
        analyst.retriever,
        "retrieve",
        lambda *a, **k: [
            {"chunk_id": "ctx-1", "title": "Context", "similarity": 0.9, "content": "Context info"}
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


# a) _line_item_note: raw with 201 orders and 1 order with items ->
#    returns text containing "0.5%" and "should not be used for rankings".
def test_a_line_item_note_low_coverage():
    raw = {"silver_orders": 201, "orders_with_items": 1}
    note = _line_item_note(raw)
    assert note is not None
    assert "0.5%" in note
    assert "should not be used for rankings" in note
    expected = (
        "Note: product-level figures are based on only 0.5% of your orders "
        "(the rest have no product line items), so they are incomplete and "
        "should not be used for rankings or totals."
    )
    assert note == expected

    note_499 = _line_item_note({"silver_orders": 1000, "orders_with_items": 499})
    assert note_499 == (
        "Note: product-level figures are based on only 49.9% of your orders "
        "(the rest have no product line items), so they are incomplete and "
        "should not be used for rankings or totals."
    )


# b) _line_item_note: coverage >= 0.5 -> None; None/garbage raw -> None; raw with 0 orders -> None.
def test_b_line_item_note_guards():
    # coverage exactly 0.5 -> None; coverage > 0.5 -> None
    assert _line_item_note({"silver_orders": 200, "orders_with_items": 100}) is None
    assert _line_item_note({"silver_orders": 2, "orders_with_items": 1}) is None
    assert _line_item_note({"silver_orders": 10, "orders_with_items": 9}) is None

    # raw with 0 orders
    assert _line_item_note({"silver_orders": 0, "orders_with_items": 0}) is None
    assert _line_item_note({"silver_orders": "0", "orders_with_items": "0"}) is None

    # None / garbage / empty raw
    assert _line_item_note(None) is None
    assert _line_item_note("garbage") is None
    assert _line_item_note(123) is None
    assert _line_item_note({}) is None
    assert _line_item_note({"silver_orders": None, "orders_with_items": None}) is None


# c) _extract_tenant_currencies(db, tid, raw=<dict>) returns the codes from raw and does NOT call db.
def test_c_extract_tenant_currencies_cached_raw():
    class ThrowingDB:
        def get_data_profile_raw(self, t):
            raise AssertionError("get_data_profile_raw must not be called when raw is given")

    raw = {
        "daily_sales": {
            "currencies": [
                {"currency_code": " usd "},
                {"currency_code": "EUR"},
                {"currency_code": "CAD"},
            ]
        }
    }
    codes = _extract_tenant_currencies(ThrowingDB(), "tenant-1", raw=raw)
    assert codes == ["CAD", "EUR", "USD"]

    # Verify that without raw, db is still called
    called = []

    class MockDB:
        def get_data_profile_raw(self, t):
            called.append(t)
            return raw

    codes_without_raw = _extract_tenant_currencies(MockDB(), "tenant-2")
    assert codes_without_raw == ["CAD", "EUR", "USD"]
    assert called == ["tenant-2"]


# Whole-word boundaries for product tables
def test_references_product_tables_word_boundaries():
    assert _references_product_tables("SELECT * FROM gold.product_daily pd") is True
    assert _references_product_tables("SELECT * FROM GOLD.PRODUCT_DAILY pd") is True
    assert _references_product_tables("SELECT * FROM silver.order_items oi") is True
    assert _references_product_tables(
        "select o.id from silver.orders o join silver.order_items oi on oi.order_id = o.id"
    ) is True
    assert _references_product_tables("SELECT product_daily_id FROM gold.product_daily_x") is False
    assert _references_product_tables("SELECT order_items_count FROM foo") is False
    assert _references_product_tables("SELECT * FROM gold.daily_sales") is False
    assert _references_product_tables("") is False


# d) ask flow test (mocking db/generator):
#    query mentioning top products with raw profile coverage < 0.5 appends the note;
#    query without product tables does not append the note.
def test_d_ask_flow_line_item_note(monkeypatch):
    profile_low_coverage = {
        "silver_orders": 201,
        "orders_with_items": 1,
        "daily_sales": {
            "currencies": [{"currency_code": "USD"}]
        },
    }

    product_sql = (
        "select pd.product_title, sum(pd.net_sales) as net_sales "
        "from gold.product_daily pd where pd.tenant_id = :tenant_id "
        "group by pd.product_title order by 2 desc limit 5"
    )

    db_profile_calls = []

    def profile_fn(t):
        db_profile_calls.append(t)
        return profile_low_coverage

    def product_planner(p):
        return _product_plan(product_sql)

    analyst_product, _ = _make_test_analyst(
        monkeypatch,
        product_planner,
        _product_final,
        profile_fn=profile_fn,
    )

    res_product = analyst_product.ask("tenant-1", "top 5 products by revenue")

    # Called exactly once per analytical request
    assert db_profile_calls == ["tenant-1"]

    expected_note = (
        "Note: product-level figures are based on only 0.5% of your orders "
        "(the rest have no product line items), so they are incomplete and "
        "should not be used for rankings or totals."
    )
    assert res_product["answer"].endswith(expected_note)
    assert res_product["answer"] == f"The top products by revenue are ready. {expected_note}"

    # Query without product tables does not append the note
    sales_sql = (
        "select sum(ds.net_sales) as net_sales "
        "from gold.daily_sales ds where ds.tenant_id = :tenant_id"
    )

    db_profile_calls.clear()

    def sales_planner(p):
        return _sales_plan(sales_sql)

    analyst_sales, _ = _make_test_analyst(
        monkeypatch,
        sales_planner,
        _sales_final,
        profile_fn=profile_fn,
    )

    res_sales = analyst_sales.ask("tenant-1", "what is my total net sales?")

    assert db_profile_calls == ["tenant-1"]
    assert res_sales["answer"] == "Here are the sales totals."
    assert "Note: product-level figures" not in res_sales["answer"]


_LOW_COVERAGE_RAW = {
    "silver_orders": 201,
    "orders_with_items": 1,
    "daily_sales": {"currencies": [{"currency_code": "USD"}]},
}
_GOOD_COVERAGE_RAW = {
    "silver_orders": 200,
    "orders_with_items": 100,
    "daily_sales": {"currencies": [{"currency_code": "USD"}]},
}
_LINE_ITEM_NOTE_05 = (
    "Note: product-level figures are based on only 0.5% of your orders "
    "(the rest have no product line items), so they are incomplete and "
    "should not be used for rankings or totals."
)
_PRODUCT_SQL = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id "
    "group by pd.product_title order by 2 desc limit 5"
)
_SALES_SQL = (
    "select sum(ds.net_sales) as net_sales "
    "from gold.daily_sales ds where ds.tenant_id = :tenant_id"
)
_PRODUCT_AGG_SQL = (
    "select sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id"
)
_UPPER_PRODUCT_SQL = (
    "SELECT PD.PRODUCT_TITLE, SUM(PD.NET_SALES) AS NET_SALES "
    "FROM GOLD.PRODUCT_DAILY PD WHERE PD.TENANT_ID = :tenant_id "
    "GROUP BY PD.PRODUCT_TITLE ORDER BY 2 DESC LIMIT 5"
)
_JOIN_ORDER_ITEMS_SQL = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd "
    "join silver.order_items oi on oi.tenant_id = pd.tenant_id "
    "where pd.tenant_id = :tenant_id and oi.tenant_id = :tenant_id "
    "group by pd.product_title"
)
_INVALID_PRODUCT_SQL = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd group by pd.product_title"
)
_BASELINE_PRODUCT_ANSWER = "The top products by revenue are ready."
_EMPTY_ANSWER = "No data has been synced or uploaded for this workspace yet."


def _agg_product_plan(sql: str) -> dict[str, Any]:
    return {
        "route": "metric",
        "intent": {
            "metric": "net_sales",
            "dimensions": [],
            "date_range": "all_time",
            "comparison": "none",
            "filters": [],
        },
        "sql": sql,
        "title": "Product Net Sales",
    }


def _force_two_tasks(monkeypatch, sources: tuple[str, str]) -> None:
    orig = ai_analyst._build_subquery_tasks

    def _split(question, resolution):
        tasks, _capped, _notice = orig(question, resolution)
        metrics = tasks[0]["metrics"] if tasks else []
        return (
            [
                {"source": sources[0], "metrics": metrics},
                {"source": sources[1], "metrics": metrics},
            ],
            False,
            None,
        )

    monkeypatch.setattr(ai_analyst, "_build_subquery_tasks", _split)


# d) two sub-queries: note exactly once, last sentence.
def test_d_two_subqueries_line_item_note_once(monkeypatch):
    def profile_fn(t):
        return _LOW_COVERAGE_RAW

    def mixed_planner(prompt):
        if "from gold.product_daily" in prompt:
            return _product_plan(_PRODUCT_SQL)
        return _sales_plan(_SALES_SQL)

    def mixed_final(prompt):
        if "product_daily" in prompt.lower():
            return _product_final(prompt)
        return _sales_final(prompt)

    _force_two_tasks(monkeypatch, ("gold.product_daily", "gold.daily_sales"))
    analyst_mixed, _ = _make_test_analyst(
        monkeypatch, mixed_planner, mixed_final, profile_fn=profile_fn
    )
    res_mixed = analyst_mixed.ask("tenant-1", "top 5 products by revenue")
    assert res_mixed["answer"].count(_LINE_ITEM_NOTE_05) == 1
    assert res_mixed["answer"].endswith(_LINE_ITEM_NOTE_05)

    def two_product_planner(prompt):
        return _product_plan(_PRODUCT_SQL)

    _force_two_tasks(monkeypatch, ("gold.product_daily", "gold.product_daily"))
    analyst_two, _ = _make_test_analyst(
        monkeypatch, two_product_planner, _product_final, profile_fn=profile_fn
    )
    res_two = analyst_two.ask("tenant-1", "top 5 products by revenue")
    assert res_two["answer"].count(_LINE_ITEM_NOTE_05) == 1
    assert res_two["answer"].endswith(_LINE_ITEM_NOTE_05)
    assert res_two["answer"] == (
        f"{_BASELINE_PRODUCT_ANSWER} {_BASELINE_PRODUCT_ANSWER} {_LINE_ITEM_NOTE_05}"
    )


# f) good coverage + product SQL -> no note; answer and keys match the no-note baseline.
def test_f_good_coverage_product_sql_no_note(monkeypatch):
    def good_profile(t):
        return _GOOD_COVERAGE_RAW

    def low_profile(t):
        return _LOW_COVERAGE_RAW

    analyst_good, _ = _make_test_analyst(
        monkeypatch,
        lambda p: _product_plan(_PRODUCT_SQL),
        _product_final,
        profile_fn=good_profile,
    )
    res_good = analyst_good.ask("tenant-1", "top 5 products by revenue")

    analyst_low, _ = _make_test_analyst(
        monkeypatch,
        lambda p: _product_plan(_PRODUCT_SQL),
        _product_final,
        profile_fn=low_profile,
    )
    res_low = analyst_low.ask("tenant-1", "top 5 products by revenue")

    assert res_good["answer"] == _BASELINE_PRODUCT_ANSWER
    assert "Note: product-level figures" not in res_good["answer"]
    assert set(res_good.keys()) == set(res_low.keys())


# g) get_data_profile_raw raises or returns a non-dict -> fail-OPEN.
def test_g_profile_raises_fail_open(monkeypatch):
    # Fail-OPEN: if get_data_profile_raw raises or returns a non-dict, ask() still
    # returns a normal answer: no note, currencies=[], no crash, no new exception type.
    # Fail-CLOSED would be: crash, change the answer, or add an error-shaped note.
    prompts: list[str] = []

    def product_planner(prompt):
        prompts.append(prompt)
        return _product_plan(_PRODUCT_SQL)

    def profile_raises(t):
        raise RuntimeError("database connection error")

    analyst_raises, _ = _make_test_analyst(
        monkeypatch, product_planner, _product_final, profile_fn=profile_raises
    )
    res_raises = analyst_raises.ask("tenant-1", "top 5 products by revenue")
    assert res_raises["answer"] == _BASELINE_PRODUCT_ANSWER
    assert "Note: product-level figures" not in res_raises["answer"]
    assert all("multiple currencies" not in p.lower() for p in prompts)

    prompts.clear()

    def profile_non_dict(t):
        return ["not", "a", "dict"]

    analyst_bad, _ = _make_test_analyst(
        monkeypatch, product_planner, _product_final, profile_fn=profile_non_dict
    )
    res_bad = analyst_bad.ask("tenant-1", "top 5 products by revenue")
    assert res_bad["answer"] == _BASELINE_PRODUCT_ANSWER
    assert set(res_bad.keys()) == set(res_raises.keys())
    assert all("multiple currencies" not in p.lower() for p in prompts)


# i) empty product_daily result does not trigger the note ([] and all-null row).
def test_i_empty_product_result_no_note(monkeypatch):
    def low_profile(t):
        return _LOW_COVERAGE_RAW

    def good_profile(t):
        return _GOOD_COVERAGE_RAW

    def empty_execute(sql, tenant_id):
        return []

    def all_null_execute(sql, tenant_id):
        return [{"net_sales": None}]

    analyst_empty, fake_empty = _make_test_analyst(
        monkeypatch,
        lambda p: _agg_product_plan(_PRODUCT_AGG_SQL),
        _product_final,
        execute_fn=empty_execute,
        profile_fn=low_profile,
    )
    monkeypatch.setattr(
        fake_empty,
        "get_data_coverage",
        lambda *a, **k: {"first_date": None, "last_date": None, "days_with_data": 0},
    )
    res_empty = analyst_empty.ask("tenant-1", "top 5 products by revenue")

    analyst_empty_good, fake_empty_good = _make_test_analyst(
        monkeypatch,
        lambda p: _agg_product_plan(_PRODUCT_AGG_SQL),
        _product_final,
        execute_fn=empty_execute,
        profile_fn=good_profile,
    )
    monkeypatch.setattr(
        fake_empty_good,
        "get_data_coverage",
        lambda *a, **k: {"first_date": None, "last_date": None, "days_with_data": 0},
    )
    res_empty_good = analyst_empty_good.ask("tenant-1", "top 5 products by revenue")

    assert res_empty["answer"] == _EMPTY_ANSWER
    assert res_empty["answer"] == res_empty_good["answer"]
    assert "Note: product-level figures" not in res_empty["answer"]
    assert set(res_empty.keys()) == set(res_empty_good.keys())

    analyst_null, fake_null = _make_test_analyst(
        monkeypatch,
        lambda p: _agg_product_plan(_PRODUCT_AGG_SQL),
        _product_final,
        execute_fn=all_null_execute,
        profile_fn=low_profile,
    )
    monkeypatch.setattr(
        fake_null,
        "get_data_coverage",
        lambda *a, **k: {"first_date": None, "last_date": None, "days_with_data": 0},
    )
    res_null = analyst_null.ask("tenant-1", "top 5 products by revenue")
    assert res_null["answer"] == _EMPTY_ANSWER
    assert "Note: product-level figures" not in res_null["answer"]
    assert set(res_null.keys()) == set(res_empty.keys())

    def mixed_planner(prompt):
        if "from gold.product_daily" in prompt:
            return _agg_product_plan(_PRODUCT_AGG_SQL)
        return _sales_plan(_SALES_SQL)

    def mixed_final(prompt):
        if "product_daily" in prompt.lower():
            return _product_final(prompt)
        return _sales_final(prompt)

    def mixed_execute(sql, tenant_id):
        if "product_daily" in sql.lower():
            return []
        return [{"net_sales": 1000}]

    _force_two_tasks(monkeypatch, ("gold.product_daily", "gold.daily_sales"))
    analyst_mixed, fake_mixed = _make_test_analyst(
        monkeypatch,
        mixed_planner,
        mixed_final,
        execute_fn=mixed_execute,
        profile_fn=low_profile,
    )
    monkeypatch.setattr(
        fake_mixed,
        "get_data_coverage",
        lambda *a, **k: {"first_date": None, "last_date": None, "days_with_data": 0},
    )
    res_mixed = analyst_mixed.ask("tenant-1", "top 5 products by revenue")
    assert res_mixed["answer"] == f"{_EMPTY_ANSWER} Here are the sales totals."
    assert "Note: product-level figures" not in res_mixed["answer"]


# Extra: uppercase PRODUCT_DAILY and silver.order_items JOIN count as product refs.
def test_extra_uppercase_and_join_product_refs(monkeypatch):
    def low_profile(t):
        return _LOW_COVERAGE_RAW

    analyst_upper, _ = _make_test_analyst(
        monkeypatch,
        lambda p: _product_plan(_UPPER_PRODUCT_SQL),
        _product_final,
        profile_fn=low_profile,
    )
    res_upper = analyst_upper.ask("tenant-1", "top 5 products by revenue")
    assert res_upper["answer"].count(_LINE_ITEM_NOTE_05) == 1
    assert res_upper["answer"].endswith(_LINE_ITEM_NOTE_05)

    analyst_join, _ = _make_test_analyst(
        monkeypatch,
        lambda p: _product_plan(_JOIN_ORDER_ITEMS_SQL),
        _product_final,
        profile_fn=low_profile,
    )
    res_join = analyst_join.ask("tenant-1", "top 5 products by revenue")
    assert res_join["answer"].count(_LINE_ITEM_NOTE_05) == 1
    assert res_join["answer"].endswith(_LINE_ITEM_NOTE_05)


# Extra: a product SQL sub-query that FAILED all retries does not add the note.
def test_extra_failed_product_sql_no_note(monkeypatch):
    def low_profile(t):
        return _LOW_COVERAGE_RAW

    analyst, _ = _make_test_analyst(
        monkeypatch,
        lambda p: _product_plan(_INVALID_PRODUCT_SQL),
        _product_final,
        profile_fn=low_profile,
    )
    res = analyst.ask("tenant-1", "top 5 products by revenue")
    assert "Note: product-level figures" not in res["answer"]
    assert res["answer"] == "I couldn't produce one requested section after checking its query."
