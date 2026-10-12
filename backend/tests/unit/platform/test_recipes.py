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
    # kpi_previous_period is added as the 5th active recipe because data coverage covers previous window
    assert recipe_ids == ["kpi_summary", "revenue_trend", "orders_trend", "top_products", "kpi_previous_period"]
    recipes_by_id = {r["id"]: r for r in res["recipes"]}
    assert recipes_by_id["revenue_trend"]["x"] == "metric_date"
    assert recipes_by_id["revenue_trend"]["y"] == "net_sales"
    assert recipes_by_id["orders_trend"]["x"] == "metric_date"
    assert recipes_by_id["orders_trend"]["y"] == "orders_count"
    assert recipes_by_id["top_products"]["x"] == "product"
    assert recipes_by_id["top_products"]["y"] == "net_sales"
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
    # 6 recipes now including internal kpi_previous_period recipe
    assert len(res["recipes"]) == 6
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


def test_line_items_incomplete():
    profile = {
        "has_data": True,
        "primary_currency": "USD",
        "currencies": ["USD", "CAD"],
        "anchor_date": "2026-08-10",
        "date_range": {"first_date": "2026-01-01", "last_date": "2026-08-10"},
        "available": {
            "daily_sales": True,
            "products": True,
            "refunds": True,
        },
        "line_items_ok": False,
    }
    res = build_recipes(profile)
    recipe_ids = [r["id"] for r in res["recipes"]]
    assert "top_products" not in recipe_ids
    assert "kpi_summary" in recipe_ids

    kpi = next(r for r in res["recipes"] if r["id"] == "kpi_summary")
    assert "units_sold" not in kpi["columns"]
    assert "units_sold" not in kpi["sql"]
    assert "Product and units data is incomplete, so it is not shown." in (res["note"] or "")
    assert "Excludes CAD" in (res["note"] or "")

    guard = SQLGuard()
    for r in res["recipes"]:
        sql = r["sql"]
        assert ":tenant_id" in sql
        assert not re.search(r"\bcurrent_date\b", sql, re.IGNORECASE)
        assert not re.search(r"\bnow\s*\(", sql, re.IGNORECASE)
        check = guard.validate(sql)
        assert check.ok is True, f"SQLGuard failed for {r['id']}: {check.reason}\nSQL:\n{sql}"


def test_previous_period_recipe_covered():
    # (a) recipes: anchor 2026-08-10, first_date 2026-01-01, window 90 -> previous window 2026-02-12..2026-05-12 and SQL passes SQLGuard
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
    assert res["window"]["start_date"] == "2026-05-13"
    assert res["window"]["end_date"] == "2026-08-10"
    assert res["previous_window"] == {
        "start_date": "2026-02-12",
        "end_date": "2026-05-12",
    }
    prev_recipe = next((r for r in res["recipes"] if r["id"] == "kpi_previous_period"), None)
    assert prev_recipe is not None
    assert prev_recipe["internal"] is True
    assert prev_recipe["chart"] == "kpi"
    assert prev_recipe["requires"] == ["daily_sales"]
    assert "'2026-02-12'" in prev_recipe["sql"]
    assert "'2026-05-12'" in prev_recipe["sql"]
    assert ":tenant_id" in prev_recipe["sql"]
    assert "'USD'" in prev_recipe["sql"]

    guard = SQLGuard()
    check = guard.validate(prev_recipe["sql"])
    assert check.ok is True, f"SQLGuard failed: {check.reason}"


def test_previous_period_recipe_short_data_skipped():
    # (b) first_date 2026-08-01 -> recipe skipped, previous_window None
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
            "refunds": False,
        },
    }
    res = build_recipes(profile, window_days=90)
    assert res["previous_window"] is None
    assert not any(r["id"] == "kpi_previous_period" for r in res["recipes"])


