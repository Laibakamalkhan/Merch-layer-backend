from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock
import pytest

from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    _enforce_single_currency,
    _extract_tenant_currencies,
    _SubqueryValidationError,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from tests.unit.platform import test_metric_resolver


# Helper tests (a) - (g3)

def test_a_helper_multi_currency_raises():
    """Helper: 4 currencies + sum(net_sales) from daily_sales without currency_code -> raises."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id=:tenant_id"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_single_currency(sql, currencies)
    msg = str(exc_info.value)
    assert "multiple currencies" in msg
    assert "currency_code" in msg


def test_b_helper_group_by_currency_code_no_error():
    """Helper: same SQL + GROUP BY currency_code -> no error."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id=:tenant_id GROUP BY currency_code"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    _enforce_single_currency(sql, currencies)


def test_c_helper_filter_currency_code_no_error():
    """Helper: same SQL + AND currency_code = 'USD' -> no error."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id=:tenant_id AND currency_code = 'USD'"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    _enforce_single_currency(sql, currencies)


def test_d_helper_uppercase_currency_code_no_error():
    """Helper: uppercase variant CURRENCY_CODE -> no error."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id=:tenant_id GROUP BY CURRENCY_CODE"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    _enforce_single_currency(sql, currencies)


def test_e_helper_single_empty_none_currency_no_error():
    """Helper: 1 currency, empty list, or None -> no error."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id=:tenant_id"
    _enforce_single_currency(sql, ["USD"])
    _enforce_single_currency(sql, [])
    _enforce_single_currency(sql, None)


def test_f_helper_unverified_table_no_error():
    """Helper: SQL on a table NOT in the verified list -> no error."""
    sql = "SELECT sum(net_sales) FROM gold.some_other_table WHERE tenant_id=:tenant_id"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    _enforce_single_currency(sql, currencies)


def test_g_helper_order_counts_no_money_word_no_error():
    """Helper: SQL on gold.daily_sales that selects only order counts -> no error."""
    sql = "SELECT sum(orders_count) FROM gold.daily_sales WHERE tenant_id=:tenant_id"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    _enforce_single_currency(sql, currencies)


def test_g2_helper_product_daily_net_revenue_raises():
    """Helper: gold.product_daily with sum(net_revenue), no currency_code -> raises."""
    sql = "SELECT sum(net_revenue) FROM gold.product_daily WHERE tenant_id=:tenant_id"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_single_currency(sql, currencies)
    assert "multiple currencies" in str(exc_info.value)
    assert "currency_code" in str(exc_info.value)


def test_g3_helper_silver_orders_total_price_raises():
    """Helper: silver.orders with sum(total_price), no currency_code -> raises."""
    sql = "SELECT sum(total_price) FROM silver.orders WHERE tenant_id=:tenant_id"
    currencies = ["USD", "CAD", "EUR", "GBP"]
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_single_currency(sql, currencies)
    assert "multiple currencies" in str(exc_info.value)
    assert "currency_code" in str(exc_info.value)


# Defensive parsing tests for _extract_tenant_currencies

def test_extract_tenant_currencies_defensive_parsing():
    """_extract_tenant_currencies handles MagicMock, non-dicts, missing keys, and invalid items."""
    # MagicMock DB
    assert _extract_tenant_currencies(MagicMock(), "t-1") == []

    # Missing method
    class DummyDB:
        pass
    assert _extract_tenant_currencies(DummyDB(), "t-1") == []

    # Non-dict return
    class NonDictDB:
        def get_data_profile_raw(self, t):
            return "not-a-dict"
    assert _extract_tenant_currencies(NonDictDB(), "t-1") == []

    # Malformed daily_sales
    class MalformedDSDB:
        def get_data_profile_raw(self, t):
            return {"daily_sales": None}
    assert _extract_tenant_currencies(MalformedDSDB(), "t-1") == []

    # Malformed currencies
    class MalformedCurrDB:
        def get_data_profile_raw(self, t):
            return {"daily_sales": {"currencies": "not-a-list"}}
    assert _extract_tenant_currencies(MalformedCurrDB(), "t-1") == []

    # Valid profile with dirty items: dedupe, uppercase, strip, drop unknown/empty, sort
    class DirtyCurrDB:
        def get_data_profile_raw(self, t):
            return {
                "daily_sales": {
                    "currencies": [
                        {"currency_code": " usd "},
                        {"currency_code": "CAD"},
                        {"currency_code": "UNKNOWN"},
                        {"currency_code": ""},
                        {"currency_code": None},
                        "not-a-dict",
                        {"currency_code": 123},
                        {"currency_code": "cad"},
                        {"currency_code": "EUR"},
                    ]
                }
            }
    assert _extract_tenant_currencies(DirtyCurrDB(), "t-1") == ["CAD", "EUR", "USD"]


# Flow tests (h), (i), and all-attempts-fail

_VALID_SQL = (
    "select sum(ds.net_sales) as net_sales, "
    "case when sum(ds.orders_count)=0 then null else sum(ds.net_sales)/sum(ds.orders_count) end "
    "as average_order_value from gold.daily_sales ds where ds.tenant_id = :tenant_id "
    "and ds.metric_date >= current_date - interval '30 day'"
)
_VALID_SQL_WITH_CURRENCY = _VALID_SQL + " group by ds.currency_code"


def _kpi_plan(sql):
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


def test_h_flow_retried_with_currency_code_feedback(monkeypatch):
    """Flow: LLM returns SQL without currency_code first, then with GROUP BY currency_code on retry.
    Asserts feedback contains 'multiple currencies', final query uses second SQL, and DB is called once.
    """
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
    prompts = []
    answers = iter([
        _kpi_plan(_VALID_SQL),
        _kpi_plan(_VALID_SQL_WITH_CURRENCY),
    ])

    def planner(prompt):
        prompts.append(prompt)
        return next(answers)

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        planner,
        _kpi_final,
        profile_fn=lambda t: profile_4,
    )

    response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    assert len(prompts) == 2
    assert "multiple currencies" in prompts[1]
    assert "currency_code" in prompts[1]
    assert response["sql"] == _VALID_SQL_WITH_CURRENCY
    assert len(fake_db.executed_sql) == 1
    assert "group by ds.currency_code" in fake_db.executed_sql[0]


def test_i_flow_profile_raises_fails_open(monkeypatch):
    """Flow: get_data_profile_raw raises -> fails open without currency check; first SQL runs normally."""
    def profile_raises(t):
        raise RuntimeError("database connection error")

    prompts = []

    def planner(prompt):
        prompts.append(prompt)
        return _kpi_plan(_VALID_SQL)

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        planner,
        _kpi_final,
        profile_fn=profile_raises,
    )

    response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    assert len(prompts) == 1
    assert response["sql"] == _VALID_SQL
    assert len(fake_db.executed_sql) == 1
    assert "group by ds.currency_code" not in fake_db.executed_sql[0]


def test_flow_all_attempts_fail_ends_friendly(monkeypatch):
    """Flow: 4 currencies where LLM returns currency-less SQL on EVERY attempt -> friendly failure path."""
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

    def planner(prompt):
        return _kpi_plan(_VALID_SQL)

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        planner,
        _kpi_final,
        profile_fn=lambda t: profile_4,
    )

    response = analyst.ask("tenant-1", "Show revenue and average order value for the last 30 days")

    assert response["dashboard"]["no_data"] is True
    assert "couldn't produce" in response["answer"].lower()
    assert fake_db.executed_sql == []
