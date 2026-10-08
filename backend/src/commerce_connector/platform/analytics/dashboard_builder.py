"""Build a canonical dashboard from verified PostgreSQL results.

KPI and chart numbers are copied from executed rows. This module never sums,
averages, or otherwise recalculates business metrics in Python.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from commerce_connector.platform.analytics.metric_resolver import MetricDefinition
from commerce_connector.platform.analytics.result_validator import (
    VerifiedQueryResult,
    validate_query_result,
)
from commerce_connector.platform.analytics.visualization import (
    VisualizationRecommendation,
    coerce_chart_type,
    recommend_visualizations,
)

MAX_CHART_POINTS = 60
_NON_TOKEN = re.compile(r"[^a-z0-9]+")


def build_verified_dashboard(
    result: VerifiedQueryResult | Sequence[Mapping[str, Any]] | None,
    *,
    title: str | None = None,
    llm_dashboard: Mapping[str, Any] | None = None,
    intent: Mapping[str, Any] | None = None,
    metrics: Sequence[MetricDefinition] | None = None,
    viz: VisualizationRecommendation | None = None,
) -> dict[str, Any]:
    verified = _as_verified(result)
    rows = verified.as_dicts()
    available = set(verified.columns)
    raw = llm_dashboard if isinstance(llm_dashboard, Mapping) else {}
    recommendation = viz or recommend_visualizations(verified, intent=intent)

    display_title = str(raw.get("title") or title or "AI Analytics")
    if verified.shape == "empty" or verified.row_count == 0:
        return {
            "title": display_title,
            "kpis": [],
            "charts": [],
            "filters": [],
            "no_data": True,
        }

    kpis = _build_kpis(raw.get("kpis") or [], rows, available, verified, metrics)
    if not kpis and recommendation.show_kpis:
        kpis = _auto_kpis(rows, verified, metrics)

    charts = _build_charts(
        raw.get("charts") or [],
        rows,
        available,
        recommendation,
    )
    if not charts:
        charts = _auto_charts(rows, available, recommendation)

    filters = _build_filters(raw.get("filters") or [], available)

    return {
        "title": display_title,
        "kpis": kpis,
        "charts": charts,
        "filters": filters,
        "no_data": False,
    }


def compact_verified_payload(verified: VerifiedQueryResult, *, max_rows: int = 50) -> dict[str, Any]:
    """Bounded DB payload for LLM wording. Not a place to invent numbers."""

    rows = verified.as_dicts()[: max(0, int(max_rows))]
    return {
        "shape": verified.shape,
        "row_count": verified.row_count,
        "columns": list(verified.columns),
        "metric_columns": list(verified.metric_columns),
        "dimension_columns": list(verified.dimension_columns),
        "already_aggregated": verified.already_aggregated,
        "rows": rows,
    }


def copy_metric_value(
    rows: Sequence[Mapping[str, Any]],
    column: str,
) -> tuple[Any, bool]:
    """Copy a KPI cell from PostgreSQL output. Never aggregate in Python."""

    if not rows or column not in rows[0]:
        return None, False
    if len(rows) == 1:
        return rows[0].get(column), True
    values = [row.get(column) for row in rows]
    first = values[0]
    if all(item == first for item in values):
        return first, True
    return None, False


def _as_verified(
    result: VerifiedQueryResult | Sequence[Mapping[str, Any]] | None,
) -> VerifiedQueryResult:
    if isinstance(result, VerifiedQueryResult):
        return result
    return validate_query_result(list(result or []))


def _build_kpis(
    items: Any,
    rows: list[dict[str, Any]],
    available: set[str],
    verified: VerifiedQueryResult,
    metrics: Sequence[MetricDefinition] | None,
) -> list[dict[str, Any]]:
    kpis: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        column = item.get("column") or item.get("source_column")
        if not isinstance(column, str) or column not in available:
            continue
        value, ok = copy_metric_value(rows, column)
        if not ok:
            continue
        kpi = _kpi_record(
            column=column,
            label=str(item.get("label") or column),
            value=value,
            metrics=metrics,
        )
        if kpi["id"] in seen:
            continue
        seen.add(kpi["id"])
        kpis.append(kpi)
    return kpis


def _auto_kpis(
    rows: list[dict[str, Any]],
    verified: VerifiedQueryResult,
    metrics: Sequence[MetricDefinition] | None,
) -> list[dict[str, Any]]:
    if verified.shape != "one_row_aggregate" or not rows:
        return []
    columns = list(verified.metric_columns) or [
        name for name, value in rows[0].items() if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    kpis: list[dict[str, Any]] = []
    for column in columns:
        value, ok = copy_metric_value(rows, column)
        if not ok:
            continue
        kpis.append(_kpi_record(column=column, label=column, value=value, metrics=metrics))
    return kpis


def _kpi_record(
    *,
    column: str,
    label: str,
    value: Any,
    metrics: Sequence[MetricDefinition] | None,
) -> dict[str, Any]:
    return {
        "id": _slug(column),
        "label": label,
        "value": value,
        "format": _format_for(column, value, metrics),
        "source_column": column,
        "column": column,
        "aggregation": "value",
    }


def _build_charts(
    items: Any,
    rows: list[dict[str, Any]],
    available: set[str],
    recommendation: VisualizationRecommendation,
) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    for index, item in enumerate(items or []):
        if not isinstance(item, Mapping):
            continue
        chart = _chart_from_spec(item, rows, available, recommendation, index=index)
        if chart:
            charts.append(chart)
    return charts


def _auto_charts(
    rows: list[dict[str, Any]],
    available: set[str],
    recommendation: VisualizationRecommendation,
) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    for index, candidate in enumerate(recommendation.candidates):
        if candidate.role == "kpi":
            continue
        spec = {
            "type": candidate.chart_type,
            "title": candidate.role.replace("_", " ").title(),
            "x": candidate.x_field,
            "y": candidate.y_field,
            "series": None,
        }
        chart = _chart_from_spec(spec, rows, available, recommendation, index=index)
        if chart:
            charts.append(chart)
    return charts


def _chart_from_spec(
    item: Mapping[str, Any],
    rows: list[dict[str, Any]],
    available: set[str],
    recommendation: VisualizationRecommendation,
    *,
    index: int,
) -> dict[str, Any] | None:
    chart_type = coerce_chart_type(item.get("type"), recommendation)
    x = item.get("x") or item.get("x_field")
    y = item.get("y") or item.get("y_field")
    series = item.get("series")
    x_ok = isinstance(x, str) and x in available
    y_ok = isinstance(y, str) and y in available
    series_ok = isinstance(series, str) and series in available

    if chart_type in {"line", "bar", "area"} and not (x_ok and y_ok):
        return None

    if chart_type == "table":
        data = [dict(row) for row in rows[:MAX_CHART_POINTS]]
    else:
        data = _copy_chart_rows(rows, x=x, y=y, series=series if series_ok else None)

    return {
        "id": _slug(str(item.get("id") or item.get("title") or f"{chart_type}_{index}")),
        "type": chart_type,
        "title": str(item.get("title") or "Chart"),
        "x_field": x if x_ok else None,
        "y_field": y if y_ok else None,
        "x": x if x_ok else None,
        "y": y if y_ok else None,
        "series": series if series_ok else None,
        "data": data,
    }


def _copy_chart_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    x: str,
    y: str,
    series: str | None,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for row in rows[:MAX_CHART_POINTS]:
        point = {x: row.get(x), y: row.get(y)}
        if series:
            point[series] = row.get(series)
        points.append(point)
    return points


def _build_filters(items: Any, available: set[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        field = item.get("field")
        filter_type = item.get("type")
        if isinstance(field, str) and field in available and filter_type in {"date_range", "select"}:
            filters.append({"field": field, "type": filter_type})
    return filters


def _format_for(
    column: str,
    value: Any,
    metrics: Sequence[MetricDefinition] | None,
) -> str:
    key = _slug(column)
    for metric in metrics or []:
        aliases = {_slug(metric.code), _slug(metric.name), *(_slug(alias) for alias in metric.aliases())}
        if key in aliases or key.endswith(f"_{_slug(metric.code)}"):
            data_type = (metric.data_type or "").lower()
            if data_type in {"currency", "money"}:
                return "currency"
            if data_type in {"integer", "int", "count"}:
                return "integer"
            if data_type in {"percent", "percentage", "ratio"}:
                return "percent"
            if data_type:
                return "number"
    lowered = column.lower()
    if any(token in lowered for token in ("revenue", "sales", "amount", "price", "aov")):
        return "currency"
    if isinstance(value, bool):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _slug(text: str) -> str:
    return _NON_TOKEN.sub("_", str(text or "").lower()).strip("_") or "item"
