from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _to_iso_date(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    val_str = str(val).strip()
    if not val_str:
        return None
    # If string contains time component, extract just YYYY-MM-DD
    if "T" in val_str:
        return val_str.split("T")[0]
    if " " in val_str:
        return val_str.split(" ")[0]
    return val_str


def build_data_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Pure function that describes what data a tenant has.

    Never crashes on missing/None keys in raw.
    Never adds numbers across different currencies.
    """
    if not raw or not isinstance(raw, dict):
        raw = {}

    daily_sales = raw.get("daily_sales")
    if not isinstance(daily_sales, dict):
        daily_sales = {}

    tables = raw.get("tables")
    if not isinstance(tables, dict):
        tables = {}

    rows_count = daily_sales.get("rows") or 0
    try:
        rows_count = int(rows_count)
    except (ValueError, TypeError):
        rows_count = 0

    has_data = rows_count > 0

    first_date = _to_iso_date(daily_sales.get("first_date"))
    last_date = _to_iso_date(daily_sales.get("last_date"))
    anchor_date = last_date if has_data else None

    # Currencies processing:
    # currencies list in daily_sales: [{currency_code, orders_count_sum, net_sales_sum}]
    raw_currencies = daily_sales.get("currencies")
    currency_totals: dict[str, float] = {}
    if isinstance(raw_currencies, list):
        for item in raw_currencies:
            if not isinstance(item, dict):
                continue
            code = item.get("currency_code")
            if not code:
                code = "UNKNOWN"
            code = str(code).strip() or "UNKNOWN"
            net_sales = item.get("net_sales_sum") or 0
            try:
                net_sales_val = float(net_sales)
            except (ValueError, TypeError):
                net_sales_val = 0.0

            # Store / accumulate if multiple entries for same code
            currency_totals[code] = currency_totals.get(code, 0.0) + net_sales_val

    # Sorting currencies: codes sorted by net_sales_sum desc, "UNKNOWN" last
    # Separate real currencies and UNKNOWN
    known_currencies = [
        (c, net) for c, net in currency_totals.items() if c.upper() != "UNKNOWN"
    ]
    has_unknown = any(c.upper() == "UNKNOWN" for c in currency_totals)

    # Sort known currencies descending by net_sales_sum, secondary sort alphabetically
    known_currencies.sort(key=lambda x: (-x[1], x[0]))
    sorted_known_codes = [c for c, _ in known_currencies]

    sorted_currencies: list[str] = list(sorted_known_codes)
    if has_unknown:
        sorted_currencies.append("UNKNOWN")

    # Primary currency: code with largest net_sales_sum (never "UNKNOWN" if another exists) or None
    if sorted_known_codes:
        primary_currency: str | None = sorted_known_codes[0]
    elif has_unknown:
        primary_currency = "UNKNOWN"
    else:
        primary_currency = None

    # multi_currency: True if more than 1 real currency
    multi_currency = len(sorted_known_codes) > 1

    # available flags: True if that table's rows > 0
    # {"daily_sales": bool, "products": bool, "refunds": bool,
    #  "customers": bool, "channels": bool, "fulfillment": bool,
    #  "inventory": bool}
    def _is_table_avail(key: str) -> bool:
        cnt = tables.get(key)
        try:
            return int(cnt or 0) > 0
        except (ValueError, TypeError):
            return False

    available = {
        "daily_sales": rows_count > 0 or _is_table_avail("daily_sales"),
        "products": _is_table_avail("products"),
        "refunds": _is_table_avail("refunds"),
        "customers": _is_table_avail("customers"),
        "channels": _is_table_avail("channels"),
        "fulfillment": _is_table_avail("fulfillment"),
        "inventory": _is_table_avail("inventory"),
    }

    return {
        "has_data": has_data,
        "date_range": {
            "first_date": first_date if has_data else None,
            "last_date": last_date if has_data else None,
        },
        "anchor_date": anchor_date,
        "currencies": sorted_currencies,
        "primary_currency": primary_currency,
        "multi_currency": multi_currency,
        "available": available,
    }
