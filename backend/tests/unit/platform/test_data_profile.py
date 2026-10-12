from datetime import date
from commerce_connector.platform.analytics.data_profile import build_data_profile


def test_normal_tenant():
    # 1. Normal tenant: dates 2026-01-01..2026-08-10, one currency, products + refunds present
    # -> anchor_date "2026-08-10", has_data True, available flags correct.
    raw = {
        "daily_sales": {
            "first_date": date(2026, 1, 1),
            "last_date": date(2026, 8, 10),
            "rows": 150,
            "currencies": [
                {"currency_code": "USD", "orders_count_sum": 100, "net_sales_sum": 5000.0}
            ],
        },
        "tables": {
            "daily_sales": 150,
            "products": 50,
            "refunds": 5,
            "customers": 0,
            "channels": 0,
            "fulfillment": 0,
            "inventory": 0,
        },
        "silver_orders": 120,
    }

    profile = build_data_profile(raw)

    assert profile["has_data"] is True
    assert profile["anchor_date"] == "2026-08-10"
    assert profile["date_range"] == {
        "first_date": "2026-01-01",
        "last_date": "2026-08-10",
    }
    assert profile["currencies"] == ["USD"]
    assert profile["primary_currency"] == "USD"
    assert profile["multi_currency"] is False
    assert profile["available"]["daily_sales"] is True
    assert profile["available"]["products"] is True
    assert profile["available"]["refunds"] is True
    assert profile["available"]["customers"] is False
    assert profile["available"]["channels"] is False
    assert profile["available"]["fulfillment"] is False
    assert profile["available"]["inventory"] is False


def test_empty_raw():
    # 2. Empty raw ({} and rows == 0) -> has_data False, anchor_date None, no crash.
    profile_empty = build_data_profile({})
    assert profile_empty["has_data"] is False
    assert profile_empty["anchor_date"] is None
    assert profile_empty["date_range"] == {"first_date": None, "last_date": None}
    assert profile_empty["currencies"] == []
    assert profile_empty["primary_currency"] is None
    assert profile_empty["multi_currency"] is False
    assert all(v is False for v in profile_empty["available"].values())

    # None raw input
    profile_none = build_data_profile(None)
    assert profile_none["has_data"] is False
    assert profile_none["anchor_date"] is None

    # rows == 0 with date strings provided
    profile_zero_rows = build_data_profile({
        "daily_sales": {
            "first_date": "2026-01-01",
            "last_date": "2026-08-10",
            "rows": 0,
            "currencies": [],
        },
        "tables": {
            "daily_sales": 0,
        },
    })
    assert profile_zero_rows["has_data"] is False
    assert profile_zero_rows["anchor_date"] is None
    assert profile_zero_rows["date_range"] == {"first_date": None, "last_date": None}


def test_multi_currency_and_unknown():
    # 3. Two currencies (e.g. PKR bigger than USD, plus UNKNOWN) -> primary_currency "PKR",
    # multi_currency True, "UNKNOWN" last in currencies.
    raw = {
        "daily_sales": {
            "first_date": "2026-03-01",
            "last_date": "2026-09-01",
            "rows": 40,
            "currencies": [
                {"currency_code": "USD", "orders_count_sum": 20, "net_sales_sum": 1000.0},
                {"currency_code": "UNKNOWN", "orders_count_sum": 5, "net_sales_sum": 999999.0},
                {"currency_code": "PKR", "orders_count_sum": 50, "net_sales_sum": 50000.0},
            ],
        },
        "tables": {
            "daily_sales": 40,
        },
    }

    profile = build_data_profile(raw)

    assert profile["has_data"] is True
    assert profile["primary_currency"] == "PKR"
    assert profile["multi_currency"] is True
    # PKR (50000) > USD (1000), UNKNOWN last
    assert profile["currencies"] == ["PKR", "USD", "UNKNOWN"]
