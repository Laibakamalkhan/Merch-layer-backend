"""Deterministic visualization candidates for verified query results.

The LLM may choose among allowed types. These rules remain authoritative and
never emit chart types the current frontend cannot render.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from commerce_connector.platform.analytics.result_validator import VerifiedQueryResult

FRONTEND_CHART_TYPES = frozenset({"line", "bar", "area", "table"})
UNSUPPORTED_CHART_TYPES = frozenset({
    "pie",
    "donut",
    "scatter",
    "map",
    "heatmap",
    "bullet",
    "horizontal_bar",
    "horizontal-bar",
})
_TYPE_ALIASES = {
    "column": "bar",
    "timeseries": "line",
    "time_series": "line",
    "area_chart": "area",
    "line_chart": "line",
    "bar_chart": "bar",
}
HIGH_CATEGORY_CARDINALITY = 25
MAX_SERIES = 8
_DATE_NAME = re.compile(
    r"(^|_)(date|time|month|week|year|day|period|timestamp|dt)(_|$)",
    re.IGNORECASE,
)
_GEO_NAME = re.compile(
    r"(city|country|region|state|province|zip|postcode|postal|lat|lng|lon|geo|location)",
    re.IGNORECASE,
)
_DATE_VALUE = re.compile(
    r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?(?:[ t].*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ChartCandidate:
    chart_type: str
    fallback: str
    role: str
    x_field: str | None = None
    y_field: str | None = None
    allowed_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VisualizationRecommendation:
    shape: str
    intent: str
    show_kpis: bool
    preferred_chart_type: str
    allowed_chart_types: tuple[str, ...]
    candidates: tuple[ChartCandidate, ...]
    notes: tuple[str, ...] = ()

    def prompt_text(self) -> str:
        allowed = ", ".join(self.allowed_chart_types) or "table"
        return (
            f"Allowed chart types for this result: {allowed}. "
            f"Preferred: {self.preferred_chart_type}. "
            "Do not use pie, donut, scatter, map, or other unsupported types. "
            "Backend visualization rules are authoritative."
        )


def recommend_visualizations(
    result: VerifiedQueryResult | Sequence[Mapping[str, Any]] | None,
    *,
    intent: Mapping[str, Any] | None = None,
) -> VisualizationRecommendation:
    rows, shape, metric_fields, dimension_fields = _unpack(result)
    if not rows:
        return VisualizationRecommendation(
            shape="empty",
            intent=_analytical_intent(intent),
            show_kpis=False,
            preferred_chart_type="table",
            allowed_chart_types=("table",),
            candidates=(),
            notes=("empty result: no chart data",),
        )

    classified = _classify_fields(rows, metric_fields, dimension_fields)
    analysis_intent = _analytical_intent(intent)
    cardinality = _cardinality(rows, classified["x_category"] or classified["x_time"])
    series_count = _cardinality(rows, classified.get("series"))
    notes: list[str] = [
        f"shape={shape}",
        f"intent={analysis_intent}",
        f"cardinality={cardinality}",
        f"series_count={series_count}",
    ]

    if shape == "one_row_aggregate" or (
        len(rows) == 1 and classified["metrics"] and not classified["x_time"] and not classified["x_category"]
    ):
        return VisualizationRecommendation(
            shape=shape,
            intent="kpi",
            show_kpis=True,
            preferred_chart_type="table",
            allowed_chart_types=("table",),
            candidates=(
                ChartCandidate(
                    chart_type="table",
                    fallback="table",
                    role="kpi",
                    y_field=classified["metrics"][0] if classified["metrics"] else None,
                    allowed_types=("table",),
                ),
            ),
            notes=tuple(notes + ["one aggregated value -> KPI; chart fallback table"]),
        )

    if classified["geo"] and classified["metrics"] and not classified["x_time"]:
        notes.append("geographic dimension -> map unsupported; bar/table")
        return _chart_recommendation(
            shape=shape,
            intent="comparison",
            preferred="bar",
            fallback="table",
            role="geo_comparison",
            x_field=classified["geo"],
            y_field=classified["metrics"][0],
            allowed=("bar", "table"),
            notes=notes,
            show_kpis=len(rows) > 0,
        )

    if analysis_intent == "top_n" and classified["x_category"] and classified["metrics"]:
        notes.append("top-N -> horizontal bar unsupported; table")
        return _chart_recommendation(
            shape=shape,
            intent="top_n",
            preferred="table",
            fallback="table",
            role="top_n",
            x_field=classified["x_category"],
            y_field=classified["metrics"][0],
            allowed=("table",),
            notes=notes,
            show_kpis=True,
        )

    if classified["x_time"] and classified["metrics"]:
        notes.append("time + metric -> line, fallback area")
        return _chart_recommendation(
            shape=shape,
            intent="trend",
            preferred="line",
            fallback="area",
            role="trend",
            x_field=classified["x_time"],
            y_field=classified["metrics"][0],
            allowed=("line", "area", "table"),
            notes=notes,
            show_kpis=True,
        )

    if analysis_intent == "composition" and classified["x_category"] and classified["metrics"]:
        notes.append("composition -> pie unsupported; bar, fallback table")
        preferred, allowed = _category_chart(cardinality, series_count)
        return _chart_recommendation(
            shape=shape,
            intent="composition",
            preferred=preferred,
            fallback="table",
            role="composition",
            x_field=classified["x_category"],
            y_field=classified["metrics"][0],
            allowed=allowed,
            notes=notes,
            show_kpis=True,
        )

    if classified["x_category"] and classified["metrics"]:
        notes.append("category + metric -> bar, fallback table")
        preferred, allowed = _category_chart(cardinality, series_count)
        return _chart_recommendation(
            shape=shape,
            intent="comparison" if analysis_intent == "auto" else analysis_intent,
            preferred=preferred,
            fallback="table",
            role="comparison",
            x_field=classified["x_category"],
            y_field=classified["metrics"][0],
            allowed=allowed,
            notes=notes,
            show_kpis=True,
        )

    if len(classified["metrics"]) >= 2 and not classified["x_time"] and not classified["x_category"]:
        notes.append("multiple numeric variables -> scatter unsupported; table")
        return _chart_recommendation(
            shape=shape,
            intent="detail",
            preferred="table",
            fallback="table",
            role="detail",
            x_field=classified["metrics"][0],
            y_field=classified["metrics"][1],
            allowed=("table",),
            notes=notes,
            show_kpis=False,
        )

    notes.append("detailed records -> table")
    return _chart_recommendation(
        shape=shape,
        intent="detail",
        preferred="table",
        fallback="table",
        role="detail",
        x_field=classified["x_category"] or classified["x_time"],
        y_field=classified["metrics"][0] if classified["metrics"] else None,
        allowed=("table",),
        notes=notes,
        show_kpis=False,
    )


def coerce_chart_type(
    requested: str | None,
    recommendation: VisualizationRecommendation,
) -> str:
    """Map an LLM/user chart type onto an allowed frontend type."""

    allowed = tuple(
        t for t in recommendation.allowed_chart_types if t in FRONTEND_CHART_TYPES
    ) or ("table",)
    preferred = (
        recommendation.preferred_chart_type
        if recommendation.preferred_chart_type in allowed
        else allowed[0]
    )
    raw = str(requested or "").strip().lower()
    raw = _TYPE_ALIASES.get(raw, raw)
    if not raw:
        return preferred
    if raw in UNSUPPORTED_CHART_TYPES:
        return preferred
    if raw in allowed:
        return raw
    if raw in FRONTEND_CHART_TYPES:
        return preferred
    return preferred


def _chart_recommendation(
    *,
    shape: str,
    intent: str,
    preferred: str,
    fallback: str,
    role: str,
    x_field: str | None,
    y_field: str | None,
    allowed: tuple[str, ...],
    notes: list[str],
    show_kpis: bool,
) -> VisualizationRecommendation:
    allowed_types = tuple(t for t in allowed if t in FRONTEND_CHART_TYPES) or ("table",)
    preferred_type = preferred if preferred in allowed_types else allowed_types[0]
    fallback_type = fallback if fallback in FRONTEND_CHART_TYPES else "table"
    return VisualizationRecommendation(
        shape=shape,
        intent=intent,
        show_kpis=show_kpis,
        preferred_chart_type=preferred_type,
        allowed_chart_types=allowed_types,
        candidates=(
            ChartCandidate(
                chart_type=preferred_type,
                fallback=fallback_type,
                role=role,
                x_field=x_field,
                y_field=y_field,
                allowed_types=allowed_types,
            ),
        ),
        notes=tuple(notes),
    )


def _category_chart(cardinality: int, series_count: int) -> tuple[str, tuple[str, ...]]:
    if cardinality > HIGH_CATEGORY_CARDINALITY or series_count > MAX_SERIES:
        return "table", ("table",)
    return "bar", ("bar", "table")


def _unpack(
    result: VerifiedQueryResult | Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], str, tuple[str, ...], tuple[str, ...]]:
    if result is None:
        return [], "empty", (), ()
    if isinstance(result, VerifiedQueryResult):
        return result.as_dicts(), result.shape, result.metric_columns, result.dimension_columns
    rows = [dict(row) for row in result]
    if not rows:
        return [], "empty", (), ()
    if len(rows) == 1 and _numeric_only(rows[0]):
        return rows, "one_row_aggregate", tuple(rows[0].keys()), ()
    return rows, "grouped", (), ()


def _numeric_only(row: Mapping[str, Any]) -> bool:
    for value in row.values():
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
    return True


def _classify_fields(
    rows: Sequence[Mapping[str, Any]],
    metric_fields: Sequence[str],
    dimension_fields: Sequence[str],
) -> dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    metrics: list[str] = []
    times: list[str] = []
    categories: list[str] = []
    geos: list[str] = []
    hinted_metrics = {str(name) for name in metric_fields}
    hinted_dims = {str(name) for name in dimension_fields}

    for name in columns:
        samples = [row.get(name) for row in rows[:25]]
        kind = _field_kind(name, samples)
        if name in hinted_metrics or kind == "metric":
            if name not in metrics:
                metrics.append(name)
            continue
        if kind == "time" or (name in hinted_dims and kind == "time"):
            times.append(name)
        elif kind == "geo":
            geos.append(name)
            categories.append(name)
        elif kind == "category" or name in hinted_dims:
            categories.append(name)

    if not metrics:
        metrics = [name for name in columns if _field_kind(name, [row.get(name) for row in rows[:25]]) == "metric"]

    x_time = times[0] if times else None
    x_category = None
    for name in categories:
        if name != x_time:
            x_category = name
            break
    series = None
    leftover = [name for name in categories if name not in {x_time, x_category}]
    if leftover:
        series = leftover[0]
    return {
        "metrics": metrics,
        "x_time": x_time,
        "x_category": x_category,
        "geo": geos[0] if geos else None,
        "series": series,
    }


def _field_kind(name: str, samples: Sequence[Any]) -> str:
    if _GEO_NAME.search(name or ""):
        return "geo"
    if _DATE_NAME.search(name or "") or _mostly_dates(samples):
        return "time"
    numeric = 0
    textual = 0
    for value in samples:
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            textual += 1
        elif isinstance(value, (int, float)):
            numeric += 1
        elif isinstance(value, (date, datetime)) or _DATE_VALUE.match(str(value).strip()):
            return "time"
        else:
            textual += 1
    if numeric and not textual:
        return "metric"
    return "category"


def _mostly_dates(samples: Sequence[Any]) -> bool:
    seen = 0
    dates = 0
    for value in samples:
        if value is None or value == "":
            continue
        seen += 1
        if isinstance(value, (date, datetime)) or _DATE_VALUE.match(str(value).strip()):
            dates += 1
    return seen > 0 and dates == seen


def _cardinality(rows: Sequence[Mapping[str, Any]], field: str | None) -> int:
    if not field:
        return 0
    return len({_norm_key(row.get(field)) for row in rows})


def _norm_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _analytical_intent(intent: Mapping[str, Any] | None) -> str:
    if not intent:
        return "auto"
    parts = [
        str(intent.get("comparison") or ""),
        str(intent.get("metric") or ""),
        str(intent.get("date_range") or ""),
        " ".join(str(item) for item in (intent.get("dimensions") or [])),
    ]
    blob = " ".join(parts).lower()
    if any(token in blob for token in ("top", "rank", "best selling", "worst")):
        return "top_n"
    if any(token in blob for token in ("share", "composition", "percent of", "part to whole")):
        return "composition"
    if any(token in blob for token in ("trend", "over time", "time series", "daily", "monthly", "weekly")):
        return "trend"
    if any(token in blob for token in ("compare", "vs", "versus", "against")):
        return "comparison"
    return "auto"
