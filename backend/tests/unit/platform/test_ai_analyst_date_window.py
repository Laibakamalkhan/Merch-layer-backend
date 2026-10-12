from __future__ import annotations

from copy import deepcopy
import pytest

from commerce_connector.platform.ai_analyst import (
    AIAnalyst,
    _enforce_no_unrequested_date_window,
    _enforce_single_currency,
    _SubqueryValidationError,
)
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.llm import LLMClient
from tests.unit.platform import test_metric_resolver


_SQL_CURRENT_DATE = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id "
    "and pd.metric_date >= (CURRENT_DATE - INTERVAL '30 days') "
    "group by 1 order by 2 desc limit 5"
)
_SQL_NO_DATE = (
    "select pd.product_title, sum(pd.net_sales) as net_sales "
    "from gold.product_daily pd where pd.tenant_id = :tenant_id "
    "group by 1 order by 2 desc limit 5"
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


def test_a_top_5_products_by_revenue_with_current_date_raises():
    """a) 'top 5 products by revenue' + SQL with CURRENT_DATE window on metric_date -> raises."""
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_no_unrequested_date_window("top 5 products by revenue", _SQL_CURRENT_DATE)
    assert "do not filter by today's date" in str(exc_info.value)


def test_b_top_5_products_by_revenue_without_date_no_error():
    """b) same question + SQL without any date -> no error."""
    _enforce_no_unrequested_date_window("top 5 products by revenue", _SQL_NO_DATE)


def test_c_relative_period_with_current_date_no_error():
    """c) 'top 5 products in the last 30 days' + CURRENT_DATE SQL -> no error."""
    _enforce_no_unrequested_date_window("top 5 products in the last 30 days", _SQL_CURRENT_DATE)


@pytest.mark.parametrize(
    "question",
    [
        "revenue this month",
        "sales recently",
        "latest orders",
        "pichle hafte ki sales",
        "revenue yesterday",
    ],
)
def test_d_time_wording_questions_with_current_date_no_error(question):
    """d) questions containing time wording + CURRENT_DATE SQL -> no error each."""
    _enforce_no_unrequested_date_window(question, _SQL_CURRENT_DATE)


def test_e_total_revenue_with_now_and_metric_date_raises():
    """e) 'total revenue' + SQL using NOW() with metric_date -> raises."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id = :tenant_id AND metric_date >= NOW() - INTERVAL '30 days'"
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_no_unrequested_date_window("total revenue", sql)
    assert "do not filter by today's date" in str(exc_info.value)


def test_f_total_revenue_with_current_date_no_metric_date_no_error():
    """f) 'total revenue' + SQL with CURRENT_DATE but NO metric_date -> no error."""
    sql = "SELECT sum(net_sales) FROM gold.daily_sales WHERE tenant_id = :tenant_id AND created_at >= CURRENT_DATE"
    _enforce_no_unrequested_date_window("total revenue", sql)


def test_g_empty_or_none_inputs_no_error():
    """g) empty/None question or sql (or non-str) -> no error."""
    _enforce_no_unrequested_date_window(None, "SELECT 1")
    _enforce_no_unrequested_date_window("", "SELECT 1")
    _enforce_no_unrequested_date_window("top 5 products", None)
    _enforce_no_unrequested_date_window("top 5 products", "")
    _enforce_no_unrequested_date_window(None, None)
    _enforce_no_unrequested_date_window(123, "SELECT 1")
    _enforce_no_unrequested_date_window("top 5 products", 123)


def test_h_flow_retried_with_date_window_feedback(monkeypatch):
    """h) Flow: LLM returns CURRENT_DATE SQL first, retry returns SQL without date; second SQL executed once."""
    prompts = []
    answers = iter([
        _product_plan(_SQL_CURRENT_DATE),
        _product_plan(_SQL_NO_DATE),
    ])

    def planner(prompt):
        prompts.append(prompt)
        return next(answers)

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        planner,
        _product_final,
    )

    response = analyst.ask("tenant-1", "top 5 products by revenue")

    assert len(prompts) == 2
    assert "do not filter by today's date" in prompts[1]
    assert response["sql"] == _SQL_NO_DATE
    assert len(fake_db.executed_sql) == 1
    assert "metric_date" not in fake_db.executed_sql[0]
    assert _SQL_CURRENT_DATE not in fake_db.executed_sql
    assert "current_date" not in fake_db.executed_sql[0].lower()


def test_i_currency_helper_total_orders_alias_no_error():
    """i) Currency helper: 4 currencies + sum(ds.orders_count) AS total_orders -> no error."""
    currencies = ["USD", "CAD", "EUR", "GBP"]
    sql = "SELECT sum(ds.orders_count) AS total_orders FROM gold.daily_sales ds WHERE ds.tenant_id=:tenant_id"
    _enforce_single_currency(sql, currencies)


def test_j_currency_helper_total_price_still_raises():
    """j) Currency helper: 4 currencies + sum(total_price) FROM silver.orders -> still raises."""
    currencies = ["USD", "CAD", "EUR", "GBP"]
    sql = "SELECT sum(total_price) FROM silver.orders WHERE tenant_id=:tenant_id"
    with pytest.raises(_SubqueryValidationError) as exc_info:
        _enforce_single_currency(sql, currencies)
    msg = str(exc_info.value)
    assert "multiple currencies" in msg
    assert "currency_code" in msg


def test_k_flow_all_attempts_fail_ends_friendly(monkeypatch):
    """k) Flow: LLM returns CURRENT_DATE SQL on every attempt -> friendly failure path, no crash, no rows."""
    def planner(prompt):
        return _product_plan(_SQL_CURRENT_DATE)

    analyst, fake_db = _make_test_analyst(
        monkeypatch,
        planner,
        _product_final,
    )

    response = analyst.ask("tenant-1", "top 5 products by revenue")

    assert response["dashboard"]["no_data"] is True
    assert "couldn't produce" in response["answer"].lower()
    assert "No data was found for the requested period" not in response["answer"]
    assert response.get("rows") == []
    assert fake_db.executed_sql == []
