from __future__ import annotations

import re
from commerce_connector.platform.analytics.recipes import build_recipes
from commerce_connector.platform.sql_guard import SQLGuard


def test_normal_profile():
    # 1. Normal profile (USD only, first 2026-01-01, anchor 2026-08-10, products True, refunds False):
    # ids == kpi_summary, revenue_trend, orders_trend, top_products;
    # window start "2026-05-13", end "2026-08-10".
    profile = {
        "has_data": True,
        "primary_currency": "USD",
        "currencies": ["USD"],
        "anchor_date": "2026-08-10",
        "date_range": {
            "first_date": "2026-01-01",
            "last_date": "2026-08-10",
        },
        "available": {
            "daily_sales": True,
            "products": True,
            "refunds": False,
        },
    }

    res = build_recipes(profile, window_days=90)
    recipe_ids = [r["id"] for r in res["recipes"]]
    assert recipe_ids == ["kpi_summary", "revenue_trend", "orders_trend", "top_products"]
    assert res["window"]["start_date"] == "2026-05-13"
    assert res["window"]["end_date"] == "2026-08-10"
    assert res["currency"] == "USD"
    assert res["excluded_currencies"] == []
    assert res["note"] is None


def test_has_data_false():
    # 2. has_data False -> recipes == [].
    profile = {
        "has_data": False,
        "primary_currency": "USD",
        "currencies": ["USD"],
        "anchor_date": "2026-08-10",
        "date_range": {"first_date": "2026-01-01", "last_date": "2026-08-10"},
        "available": {"daily_sales": True},
    }
    res = build_recipes(profile)
    assert res["recipes"] == []
    assert res["currency"] is None
    assert res["excluded_currencies"] == []
    assert res["note"] is None
    assert res["window"]["start_date"] is None
    assert res["window"]["end_date"] is None


def test_multi_currency():
    # 3. Multi-currency (USD primary, CAD/EUR/GBP): currency "USD", excluded_currencies
    # ["CAD","EUR","GBP"], note mentions them, and SQL contains 'USD' only.
    profile = {
        "has_data": True,
        "primary_currency": "USD",
        "currencies": ["GBP", "USD", "EUR", "CAD"],
        "anchor_date": "2026-08-10",
        "date_range": {"first_date": "2026-01-01", "last_date": "2026-08-10"},
        "available": {
            "daily_sales": True,
            "products": True,
            "refunds": True,
        },
    }
    res = build_recipes(profile)
    assert res["currency"] == "USD"
    assert res["excluded_currencies"] == ["CAD", "EUR", "GBP"]
    assert res["note"] is not None
    assert "CAD" in res["note"] and "EUR" in res["note"] and "GBP" in res["note"]
    assert "USD" in res["note"]
    for r in res["recipes"]:
        assert "'USD'" in r["sql"]
        for excluded in ["CAD", "EUR", "GBP"]:
            assert f"'{excluded}'" not in r["sql"]


def test_sql_guard_validation():
    # 4. Every recipe SQL passes the real SQLGuard().validate(sql).ok
    # Also assert ":tenant_id" in sql, and no "current_date" / "now()" in any sql.
    profile = {
        "has_data": True,
        "primary_currency": "USD",
        "currencies": ["USD"],
        "anchor_date": "2026-08-10",
        "date_range": {"first_date": "2026-01-01", "last_date": "2026-08-10"},
        "available": {
            "daily_sales": True,
            "products": True,
            "refunds": True,
        },
    }
    res = build_recipes(profile)
    guard = SQLGuard()
    assert len(res["recipes"]) == 5
    for r in res["recipes"]:
        sql = r["sql"]
        assert ":tenant_id" in sql, f":tenant_id missing in {r['id']}"
        assert not re.search(r"\bcurrent_date\b", sql, re.IGNORECASE), f"current_date found in {r['id']}"
        assert not re.search(r"\bnow\s*\(", sql, re.IGNORECASE), f"now() found in {r['id']}"
        check = guard.validate(sql)
        assert check.ok is True, f"SQLGuard failed for {r['id']}: {check.reason}\nSQL:\n{sql}"


def test_short_data():
    # 5. Short data (first_date 2026-08-01, anchor 2026-08-10): start_date == "2026-08-01".
    profile = {
        "has_data": True,
        "primary_currency": "USD",
        "currencies": ["USD"],
        "anchor_date": "2026-08-10",
        "date_range": {
            "first_date": "2026-08-01",
            "last_date": "2026-08-10",
        },
        "available": {
            "daily_sales": True,
            "products": True,
            "refunds": True,
        },
    }
    res = build_recipes(profile, window_days=90)
    assert res["window"]["start_date"] == "2026-08-01"
    assert res["window"]["end_date"] == "2026-08-10"


def test_bad_currency_injection():
    # 6. Bad currency code like "US'; drop table x;--" -> recipes == [] (no SQL produced).
    profile = {
        "has_data": True,
        "primary_currency": "US'; drop table x;--",
        "currencies": ["US'; drop table x;--"],
        "anchor_date": "2026-08-10",
        "date_range": {"first_date": "2026-01-01", "last_date": "2026-08-10"},
        "available": {
            "daily_sales": True,
            "products": True,
            "refunds": True,
        },
    }
    res = build_recipes(profile)
    assert res["recipes"] == []
    assert res["currency"] is None
