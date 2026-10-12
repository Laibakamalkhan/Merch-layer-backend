from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

CURRENCY_REGEX = re.compile(r"^[A-Z0-9_]{2,10}$")


def build_recipes(profile: dict[str, Any] | None, window_days: int = 90) -> dict[str, Any]:
    """Generate ready-to-run verified SQL recipes given a tenant data profile."""
    empty_result: dict[str, Any] = {
        "recipes": [],
        "currency": None,
        "excluded_currencies": [],
        "note": None,
        "window": {"start_date": None, "end_date": None},
    }

    if not profile or not profile.get("has_data"):
        return empty_result

    primary_curr = profile.get("primary_currency")
    if not primary_curr or not isinstance(primary_curr, str) or not CURRENCY_REGEX.fullmatch(primary_curr):
        return empty_result

    anchor_date_str = profile.get("anchor_date")
    if not anchor_date_str or not isinstance(anchor_date_str, str):
        return empty_result

    try:
        end_d = date.fromisoformat(anchor_date_str)
    except ValueError:
        return empty_result

    date_range = profile.get("date_range") or {}
    first_date_str = date_range.get("first_date")
    if first_date_str and isinstance(first_date_str, str):
        try:
            first_d = date.fromisoformat(first_date_str)
        except ValueError:
            first_d = end_d
    else:
        first_d = end_d

    window_offset = timedelta(days=max(0, window_days - 1))
    calculated_start_d = end_d - window_offset
    start_d = max(first_d, calculated_start_d)

    start_date = start_d.isoformat()
    end_date = end_d.isoformat()

    all_currencies = profile.get("currencies") or []
    excluded_currencies = sorted(
        [
            c
            for c in all_currencies
            if c != primary_curr and isinstance(c, str) and c != "UNKNOWN"
        ]
    )

    line_items_ok = profile.get("line_items_ok", True)

    notes: list[str] = []
    if excluded_currencies:
        notes.append(f"Showing data in {primary_curr} only. Excludes {', '.join(excluded_currencies)}.")
    if not line_items_ok:
        notes.append("Product and units data is incomplete, so it is not shown.")

    note = " ".join(notes) if notes else None

    available = profile.get("available") or {}

    # Define candidate recipes
    # Note: literals primary_curr, start_date, end_date are safe and validated.
    # Every silver/gold table reference has <alias>.tenant_id = :tenant_id.
    kpi_select_clauses = [
        "    COALESCE(SUM(ds.gross_sales), 0) AS gross_sales,",
        "    COALESCE(SUM(ds.discounts), 0) AS discounts,",
        "    COALESCE(SUM(ds.refunds), 0) AS refunds,",
        "    COALESCE(SUM(ds.net_sales), 0) AS net_sales,",
        "    COALESCE(SUM(ds.orders_count), 0) AS orders_count,",
    ]
    kpi_columns = ["gross_sales", "discounts", "refunds", "net_sales", "orders_count"]

    if line_items_ok:
        kpi_select_clauses.append("    COALESCE(SUM(ds.units_sold), 0) AS units_sold,")
        kpi_columns.append("units_sold")

    kpi_select_clauses.append("    ROUND(COALESCE(SUM(ds.net_sales) / NULLIF(SUM(ds.orders_count), 0), 0), 2) AS aov")
    kpi_columns.append("aov")

    kpi_select_str = "\n".join(kpi_select_clauses)
    kpi_sql = (
        f"SELECT\n"
        f"{kpi_select_str}\n"
        f"FROM gold.daily_sales ds\n"
        f"WHERE ds.tenant_id = :tenant_id\n"
        f"  AND ds.currency_code = '{primary_curr}'\n"
        f"  AND ds.metric_date >= '{start_date}'\n"
        f"  AND ds.metric_date <= '{end_date}'"
    )

    candidate_recipes = [
        {
            "id": "kpi_summary",
            "title": f"Key performance indicators ({primary_curr})",
            "sql": kpi_sql,
            "requires": ["daily_sales"],
            "chart": "kpi",
            "columns": kpi_columns,
        },
        {
            "id": "revenue_trend",
            "title": f"Net sales trend ({primary_curr})",
            "sql": (
                f"SELECT\n"
                f"    ds.metric_date,\n"
                f"    COALESCE(SUM(ds.net_sales), 0) AS net_sales\n"
                f"FROM gold.daily_sales ds\n"
                f"WHERE ds.tenant_id = :tenant_id\n"
                f"  AND ds.currency_code = '{primary_curr}'\n"
                f"  AND ds.metric_date >= '{start_date}'\n"
                f"  AND ds.metric_date <= '{end_date}'\n"
                f"GROUP BY ds.metric_date\n"
                f"ORDER BY ds.metric_date"
            ),
            "requires": ["daily_sales"],
            "chart": "line",
            "columns": ["metric_date", "net_sales"],
        },
        {
            "id": "orders_trend",
            "title": f"Orders count trend ({primary_curr})",
            "sql": (
                f"SELECT\n"
                f"    ds.metric_date,\n"
                f"    COALESCE(SUM(ds.orders_count), 0) AS orders_count\n"
                f"FROM gold.daily_sales ds\n"
                f"WHERE ds.tenant_id = :tenant_id\n"
                f"  AND ds.currency_code = '{primary_curr}'\n"
                f"  AND ds.metric_date >= '{start_date}'\n"
                f"  AND ds.metric_date <= '{end_date}'\n"
                f"GROUP BY ds.metric_date\n"
                f"ORDER BY ds.metric_date"
            ),
            "requires": ["daily_sales"],
            "chart": "line",
            "columns": ["metric_date", "orders_count"],
        },
    ]

    if line_items_ok:
        candidate_recipes.append(
            {
                "id": "top_products",
                "title": f"Top products by net sales ({primary_curr})",
                "sql": (
                    f"SELECT\n"
                    f"    COALESCE(p.title, 'Unknown product') AS product,\n"
                    f"    COALESCE(NULLIF(p.product_type, ''), 'Uncategorized') AS category,\n"
                    f"    COALESCE(SUM(pd.net_sales), 0) AS net_sales,\n"
                    f"    COALESCE(SUM(pd.units_sold), 0) AS units_sold\n"
                    f"FROM gold.product_daily pd\n"
                    f"LEFT JOIN silver.products p ON p.id = pd.product_id AND p.tenant_id = :tenant_id\n"
                    f"WHERE pd.tenant_id = :tenant_id\n"
                    f"  AND pd.currency_code = '{primary_curr}'\n"
                    f"  AND pd.metric_date >= '{start_date}'\n"
                    f"  AND pd.metric_date <= '{end_date}'\n"
                    f"GROUP BY pd.product_id, p.title, p.product_type\n"
                    f"ORDER BY net_sales DESC\n"
                    f"LIMIT 10"
                ),
                "requires": ["products"],
                "chart": "bar",
                "columns": ["product", "category", "net_sales", "units_sold"],
            }
        )

    candidate_recipes.append(
        {
            "id": "refunds_summary",
            "title": f"Refunds summary ({primary_curr})",
            "sql": (
                f"SELECT\n"
                f"    COALESCE(SUM(rd.refund_count), 0) AS refund_count,\n"
                f"    COALESCE(SUM(rd.refund_amount), 0) AS refund_amount\n"
                f"FROM gold.refund_daily rd\n"
                f"WHERE rd.tenant_id = :tenant_id\n"
                f"  AND rd.currency_code = '{primary_curr}'\n"
                f"  AND rd.metric_date >= '{start_date}'\n"
                f"  AND rd.metric_date <= '{end_date}'"
            ),
            "requires": ["refunds"],
            "chart": "kpi",
            "columns": ["refund_count", "refund_amount"],
        }
    )

    active_recipes = [
        r
        for r in candidate_recipes
        if all(available.get(req, False) for req in r["requires"])
    ]

    return {
        "recipes": active_recipes,
        "currency": primary_curr,
        "excluded_currencies": excluded_currencies,
        "note": note,
        "window": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }
