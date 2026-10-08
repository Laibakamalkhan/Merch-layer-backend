"""Trusted metric lookup on top of ``semantic_catalog_snapshot()``.

The catalog in ``ai.metric_definitions`` is the only source of metric SQL
expressions. The LLM may choose among those definitions; it may not invent a
replacement aggregate when a verified expression already exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


_AGGREGATE_CALL = re.compile(
    r"\b(sum|avg|average|min|max|count)\s*\(([^)]+)\)",
    re.IGNORECASE,
)
_NON_TOKEN = re.compile(r"[^a-z0-9]+")

# Named KPIs that must never be calculated unless a catalog definition exists.
UNSUPPORTED_WITHOUT_DEFINITION = {
    "profit": "Profit is not available because the semantic catalog has no cost/COGS metric.",
    "profit_margin": "Profit margin is not available because the semantic catalog has no cost/COGS metric.",
    "gross_margin": "Gross margin is not available because the semantic catalog has no cost/COGS metric.",
    "margin": "Margin is not available because the semantic catalog has no cost/COGS metric.",
    "cogs": "Cost of goods sold is not available in the semantic catalog.",
    "cost": "Cost is not available in the semantic catalog.",
}


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    code: str
    name: str
    description: str = ""
    sql_expression: str | None = None
    aggregation: str | None = None
    data_type: str | None = None
    default_time_column: str | None = None
    allowed_dimensions: tuple[str, ...] = ()
    preferred_source_schema: str | None = None
    preferred_source_table: str | None = None
    synonyms: tuple[str, ...] = ()

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MetricDefinition:
        dimensions = row.get("allowed_dimensions") or []
        synonyms = row.get("synonyms") or []
        if isinstance(dimensions, str):
            dimensions = [dimensions]
        if isinstance(synonyms, str):
            synonyms = [synonyms]
        expr = row.get("sql_expression")
        return cls(
            code=str(row.get("code") or "").strip(),
            name=str(row.get("name") or row.get("code") or "").strip(),
            description=str(row.get("description") or ""),
            sql_expression=str(expr).strip() if expr else None,
            aggregation=str(row["aggregation"]).strip() if row.get("aggregation") else None,
            data_type=str(row["data_type"]).strip() if row.get("data_type") else None,
            default_time_column=(
                str(row["default_time_column"]).strip() if row.get("default_time_column") else None
            ),
            allowed_dimensions=tuple(str(d) for d in dimensions if d),
            preferred_source_schema=(
                str(row["preferred_source_schema"]).strip() if row.get("preferred_source_schema") else None
            ),
            preferred_source_table=(
                str(row["preferred_source_table"]).strip() if row.get("preferred_source_table") else None
            ),
            synonyms=tuple(str(s) for s in synonyms if s),
        )

    def aliases(self) -> tuple[str, ...]:
        names = [self.code, self.name, *self.synonyms]
        expanded: list[str] = []
        for raw in names:
            text = str(raw or "").strip()
            if not text:
                continue
            expanded.append(text)
            collapsed = _NON_TOKEN.sub(" ", text.lower()).strip()
            if collapsed:
                expanded.append(collapsed)
        seen: set[str] = set()
        out: list[str] = []
        for item in expanded:
            key = item.lower()
            if key in seen or len(key) < 2:
                continue
            seen.add(key)
            out.append(item)
        return tuple(out)


@dataclass(slots=True)
class MetricResolution:
    ok: bool
    metrics: list[MetricDefinition] = field(default_factory=list)
    matched: list[MetricDefinition] = field(default_factory=list)
    unsupported_code: str | None = None
    message: str | None = None

    def matched_codes(self) -> list[str]:
        return [m.code for m in self.matched]


def metrics_from_snapshot(snapshot: dict[str, Any] | None) -> list[MetricDefinition]:
    rows = (snapshot or {}).get("metrics") or []
    out: list[MetricDefinition] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric = MetricDefinition.from_row(row)
        if metric.code:
            out.append(metric)
    return out


def lookup_metric(
    snapshot: dict[str, Any] | None,
    code: str | None,
) -> MetricDefinition | None:
    wanted = str(code or "").strip().lower()
    if not wanted:
        return None
    for metric in metrics_from_snapshot(snapshot):
        if metric.code.lower() == wanted:
            return metric
        if any(alias.lower() == wanted for alias in metric.aliases()):
            return metric
    return None


def resolve_metrics(
    question: str,
    snapshot: dict[str, Any] | None,
    *,
    intent: dict[str, Any] | None = None,
    dataset_profile: dict[str, Any] | None = None,
) -> MetricResolution:
    """Bind named KPIs in the question/intent to verified catalog definitions."""

    metrics = metrics_from_snapshot(snapshot)
    catalog_by_code = {m.code.lower(): m for m in metrics}
    unavailable = {
        str(code).strip().lower()
        for code in (dataset_profile or {}).get("unavailable_metrics") or []
        if code
    }

    phrases: list[str] = [question or ""]
    intent_metric = None
    if isinstance(intent, dict):
        intent_metric = intent.get("metric")
        if intent_metric:
            phrases.append(str(intent_metric))

    haystack = _normalize(" ".join(phrases))
    matched = _match_catalog_metrics(haystack, metrics)

    named_codes = _named_kpi_codes(haystack, intent_metric)
    for code in named_codes:
        if code in catalog_by_code:
            metric = catalog_by_code[code]
            if metric not in matched:
                matched.append(metric)
            continue
        if code in unavailable or code in UNSUPPORTED_WITHOUT_DEFINITION:
            return MetricResolution(
                ok=False,
                metrics=metrics,
                matched=matched,
                unsupported_code=code,
                message=unsupported_metric_message(code, unavailable=unavailable),
            )

    for metric in list(matched):
        if metric.code.lower() in unavailable:
            return MetricResolution(
                ok=False,
                metrics=metrics,
                matched=matched,
                unsupported_code=metric.code,
                message=unsupported_metric_message(metric.code, unavailable=unavailable),
            )

    return MetricResolution(ok=True, metrics=metrics, matched=matched)


def unsupported_metric_message(code: str, *, unavailable: Iterable[str] | None = None) -> str:
    key = str(code or "").strip().lower()
    if key in UNSUPPORTED_WITHOUT_DEFINITION:
        return UNSUPPORTED_WITHOUT_DEFINITION[key]
    if key in {str(item).lower() for item in (unavailable or [])}:
        return (
            f"Metric '{code}' is not supported by the current dataset. "
            "Required source fields are unavailable."
        )
    return (
        f"Metric '{code}' is not defined in the semantic catalog, "
        "so it cannot be calculated."
    )


def compact_semantic_context(
    snapshot: dict[str, Any] | None,
    resolution: MetricResolution | None = None,
    *,
    max_columns: int = 80,
) -> str:
    """Planner-facing catalog: verified metrics first, then bounded columns."""

    snapshot = snapshot or {}
    resolution = resolution or MetricResolution(ok=True, metrics=metrics_from_snapshot(snapshot))
    lines: list[str] = [
        "TRUSTED SEMANTIC CATALOG",
        "Use only these verified metric definitions and columns.",
        "Never invent a metric SQL expression when a verified definition exists.",
        "Never invent columns, tables, or numerical literals.",
        "",
        "Verified metrics:",
    ]
    metrics = resolution.metrics or metrics_from_snapshot(snapshot)
    matched_codes = {m.code.lower() for m in resolution.matched}
    if not metrics:
        lines.append("- none defined")
    for metric in metrics:
        marker = " [REQUIRED for this question]" if metric.code.lower() in matched_codes else ""
        source = ".".join(
            part for part in (metric.preferred_source_schema, metric.preferred_source_table) if part
        ) or "not specified"
        lines.append(f"- code={metric.code} name={metric.name}{marker}")
        lines.append(f"  description: {metric.description or 'n/a'}")
        lines.append(f"  sql_expression: {metric.sql_expression or 'not specified'}")
        lines.append(f"  aggregation: {metric.aggregation or 'not specified'}")
        lines.append(f"  data_type: {metric.data_type or 'not specified'}")
        lines.append(f"  default_time_column: {metric.default_time_column or 'not specified'}")
        lines.append(f"  allowed_dimensions: {', '.join(metric.allowed_dimensions) or 'none'}")
        lines.append(f"  preferred_source: {source}")

    preferred_tables = {
        (
            (m.preferred_source_schema or "").lower(),
            (m.preferred_source_table or "").lower(),
        )
        for m in resolution.matched
        if m.preferred_source_schema and m.preferred_source_table
    }
    columns = list(snapshot.get("columns") or [])
    if preferred_tables:
        filtered = [
            col
            for col in columns
            if (
                str(col.get("table_schema") or "").lower(),
                str(col.get("table_name") or "").lower(),
            )
            in preferred_tables
        ]
        if filtered:
            columns = filtered
    lines.append("")
    lines.append("Relevant columns:")
    shown = 0
    for col in columns:
        if shown >= max_columns:
            lines.append(f"- ... truncated {len(columns) - shown} additional columns")
            break
        lines.append(
            f"- {col.get('table_schema')}.{col.get('table_name')}.{col.get('column_name')}"
            f" ({col.get('data_type')})"
        )
        shown += 1
    if shown == 0:
        lines.append("- none")

    lines.append("")
    lines.append("Query permissions (SELECT allowed):")
    permissions = snapshot.get("permissions") or []
    if not permissions:
        lines.append("- inherit SQLGuard defaults for gold/silver/control")
    for perm in permissions:
        lines.append(f"- {perm.get('schema_name')}.{perm.get('table_name')} max_rows={perm.get('max_rows')}")

    connections = snapshot.get("connections") or []
    if connections:
        lines.append("")
        lines.append("Connected stores (labels only):")
        for connection in connections:
            lines.append(
                f"- {connection.get('name')} platform={connection.get('platform_code')}"
            )
    return "\n".join(lines)


def enforce_verified_metric_sql(
    sql: str,
    *,
    snapshot: dict[str, Any] | None,
    resolution: MetricResolution | None = None,
    intent: dict[str, Any] | None = None,
) -> None:
    """Reject invented aggregates when a verified metric definition exists."""

    intent_metric = None
    if isinstance(intent, dict):
        intent_metric = intent.get("metric")

    to_check: list[MetricDefinition] = []
    seen: set[str] = set()
    if resolution:
        for metric in resolution.matched:
            if metric.code.lower() not in seen:
                to_check.append(metric)
                seen.add(metric.code.lower())
    looked_up = lookup_metric(snapshot, intent_metric)
    if looked_up and looked_up.code.lower() not in seen:
        to_check.append(looked_up)
        seen.add(looked_up.code.lower())

    named = str(intent_metric or "").strip().lower()
    if named and named not in seen:
        if named in UNSUPPORTED_WITHOUT_DEFINITION or not looked_up:
            if named in UNSUPPORTED_WITHOUT_DEFINITION:
                raise RuntimeError(unsupported_metric_message(named))

    compact_sql = _compact_sql(sql)
    invented = _aggregate_calls(sql)
    for metric in to_check:
        if not metric.sql_expression:
            continue
        verified = _compact_sql(metric.sql_expression)
        if verified and verified in compact_sql:
            continue
        for fn, inner in invented:
            candidate = _compact_sql(f"{fn}({inner})")
            if candidate != verified:
                raise RuntimeError(
                    f"Invented metric expression {fn.upper()}({inner.strip()}) is not allowed "
                    f"because metric '{metric.code}' is defined as {metric.sql_expression}."
                )


def _normalize(text: str) -> str:
    return _NON_TOKEN.sub(" ", str(text or "").lower()).strip()


def _compact_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", str(sql or "")).strip().lower()


def _aggregate_calls(sql: str) -> list[tuple[str, str]]:
    return [(fn.lower(), inner.strip()) for fn, inner in _AGGREGATE_CALL.findall(sql or "")]


def _match_catalog_metrics(haystack: str, metrics: Sequence[MetricDefinition]) -> list[MetricDefinition]:
    padded = f" {haystack} "
    ranked: list[tuple[int, MetricDefinition]] = []
    for metric in metrics:
        best = 0
        for alias in metric.aliases():
            needle = f" {_normalize(alias)} "
            if needle.strip() and needle in padded:
                best = max(best, len(needle.strip()))
        if best:
            ranked.append((best, metric))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [metric for _, metric in ranked]


def _named_kpi_codes(haystack: str, intent_metric: Any) -> list[str]:
    padded = f" {haystack} "
    found: list[str] = []
    seen: set[str] = set()
    extras = [str(intent_metric)] if intent_metric else []
    candidates: list[tuple[int, str, str]] = []
    for raw in [*UNSUPPORTED_WITHOUT_DEFINITION.keys(), *extras]:
        phrase = _normalize(raw)
        if phrase:
            candidates.append((len(phrase), str(raw), phrase))
    candidates.sort(reverse=True)
    for _length, _raw, phrase in candidates:
        canonical = phrase.replace(" ", "_")
        if canonical in seen:
            continue
        if any(phrase != prior and phrase in prior for prior in seen):
            continue
        in_text = f" {phrase} " in padded
        intent_hit = _normalize(str(intent_metric or "")) == phrase
        if in_text or intent_hit:
            found.append(canonical)
            seen.add(canonical)
            seen.add(phrase)
    return found
