"""Validate executed query rows before any dashboard or LLM wording step.

PostgreSQL/Supabase remains the only numerical source of truth. This layer
never invents, fills, or recalculates business metrics; it only checks that
returned rows are bounded, structurally complete, serializable, and finite.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal, Mapping, Sequence
from uuid import UUID

from commerce_connector.platform.analytics.metric_resolver import MetricDefinition

ResultShape = Literal["empty", "one_row_aggregate", "grouped"]

_NON_TOKEN = re.compile(r"[^a-z0-9]+")
_METRIC_PREFIXES = (
    "total_",
    "sum_",
    "avg_",
    "average_",
    "count_",
    "num_",
    "n_",
)
DEFAULT_MAX_ROWS = 5000


@dataclass(frozen=True, slots=True)
class VerifiedQueryResult:
    ok: bool
    rows: tuple[dict[str, Any], ...] = ()
    columns: tuple[str, ...] = ()
    metric_columns: tuple[str, ...] = ()
    dimension_columns: tuple[str, ...] = ()
    shape: ResultShape = "empty"
    row_count: int = 0
    already_aggregated: bool = False
    message: str | None = None
    errors: tuple[str, ...] = ()

    def as_dicts(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]


@dataclass(slots=True)
class _ValidationState:
    errors: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)


def validate_query_result(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    expected_metrics: Sequence[MetricDefinition | str] | None = None,
    expected_dimensions: Sequence[str] | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> VerifiedQueryResult:
    """Verify database rows without substituting missing or invalid values."""

    state = _ValidationState()
    if rows is None:
        return _invalid(state, "Query result is missing; no replacement values were generated.")
    if not isinstance(rows, (list, tuple)):
        return _invalid(
            state,
            "Query result must be a list of row mappings; no replacement values were generated.",
        )

    limit = int(max_rows)
    if limit < 1:
        return _invalid(state, "Result row limit must be a positive integer.")
    if len(rows) > limit:
        return _invalid(
            state,
            f"Query returned {len(rows)} rows, which exceeds the allowed maximum of {limit}. "
            "No replacement values were generated.",
        )

    if len(rows) == 0:
        return VerifiedQueryResult(
            ok=True,
            rows=(),
            columns=(),
            metric_columns=(),
            dimension_columns=(),
            shape="empty",
            row_count=0,
            already_aggregated=False,
            message="Query returned no matching rows.",
        )

    header: list[str] | None = None
    serializable: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            return _invalid(state, f"Row {index} is not a mapping; no replacement values were generated.")
        keys = tuple(row.keys())
        if header is None:
            header = [str(key) for key in keys]
        elif [str(key) for key in keys] != header:
            return _invalid(
                state,
                f"Row {index} columns do not match the result header; no replacement values were generated.",
            )
        converted: dict[str, Any] = {}
        for key in header:
            ok, value, error = _serializable_value(row[key], field=key, row=index)
            if not ok:
                state.fail(error or "Unserializable value.")
                return _invalid(state, error or "Unserializable value.")
            converted[key] = value
        serializable.append(converted)

    assert header is not None
    columns = tuple(header)
    column_keys = {_column_key(name): name for name in columns}

    metric_columns = _resolve_metric_columns(column_keys, expected_metrics, state)
    dimension_columns = _resolve_dimension_columns(column_keys, expected_dimensions, state)
    if state.errors:
        return _invalid(state, state.errors[0])

    try:
        json.dumps(serializable, allow_nan=False)
    except (TypeError, ValueError) as exc:
        return _invalid(
            state,
            f"Query result is not JSON-serializable: {exc}. No replacement values were generated.",
        )

    shape = _result_shape(serializable, dimension_columns)
    already_aggregated = True

    return VerifiedQueryResult(
        ok=True,
        rows=tuple(serializable),
        columns=columns,
        metric_columns=tuple(metric_columns),
        dimension_columns=tuple(dimension_columns),
        shape=shape,
        row_count=len(serializable),
        already_aggregated=already_aggregated,
        message=None,
    )


def _result_shape(
    rows: Sequence[Mapping[str, Any]],
    dimension_columns: Sequence[str],
) -> ResultShape:
    if not rows:
        return "empty"
    if len(rows) > 1:
        return "grouped"
    if dimension_columns:
        return "grouped"
    if _row_is_numeric_only(rows[0]):
        return "one_row_aggregate"
    return "grouped"


def _row_is_numeric_only(row: Mapping[str, Any]) -> bool:
    for value in row.values():
        if value is None:
            continue
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            continue
        return False
    return True


def _invalid(state: _ValidationState, message: str) -> VerifiedQueryResult:
    state.fail(message)
    return VerifiedQueryResult(
        ok=False,
        rows=(),
        columns=(),
        metric_columns=(),
        dimension_columns=(),
        shape="empty",
        row_count=0,
        already_aggregated=False,
        message=message,
        errors=tuple(state.errors),
    )


def _column_key(name: str) -> str:
    return _NON_TOKEN.sub("_", str(name or "").lower()).strip("_")


def _metric_keys(metric: MetricDefinition | str) -> set[str]:
    aliases: list[str]
    if isinstance(metric, MetricDefinition):
        aliases = [metric.code, metric.name, *metric.aliases()]
    else:
        aliases = [str(metric)]
    keys = {_column_key(item) for item in aliases if str(item).strip()}
    expanded = set(keys)
    for key in keys:
        for prefix in _METRIC_PREFIXES:
            expanded.add(f"{prefix}{key}")
    return {item for item in expanded if item}


def _resolve_metric_columns(
    column_keys: Mapping[str, str],
    expected_metrics: Sequence[MetricDefinition | str] | None,
    state: _ValidationState,
) -> list[str]:
    if not expected_metrics:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for metric in expected_metrics:
        label = metric.code if isinstance(metric, MetricDefinition) else str(metric)
        keys = _metric_keys(metric)
        match = next((column_keys[key] for key in keys if key in column_keys), None)
        if match is None:
            for col_key, col_name in column_keys.items():
                if any(col_key == key or col_key.endswith(f"_{key}") for key in keys):
                    match = col_name
                    break
        if match is None:
            state.fail(
                f"Expected metric column for '{label}' is missing from the query result. "
                "No replacement value was generated."
            )
            continue
        if match not in seen:
            found.append(match)
            seen.add(match)
    return found


def _resolve_dimension_columns(
    column_keys: Mapping[str, str],
    expected_dimensions: Sequence[str] | None,
    state: _ValidationState,
) -> list[str]:
    wanted = [str(item).strip() for item in (expected_dimensions or []) if str(item).strip()]
    if not wanted:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for dimension in wanted:
        key = _column_key(dimension)
        match = column_keys.get(key)
        if match is None:
            for col_key, col_name in column_keys.items():
                if col_key == key or col_key.endswith(f"_{key}") or key.endswith(f"_{col_key}"):
                    match = col_name
                    break
        if match is None:
            state.fail(
                f"Requested dimension '{dimension}' is missing from the query result. "
                "No replacement value was generated."
            )
            continue
        if match not in seen:
            found.append(match)
            seen.add(match)
    return found


def _serializable_value(value: Any, *, field: str, row: int) -> tuple[bool, Any, str | None]:
    if value is None or isinstance(value, (str, bool)):
        return True, value, None
    if isinstance(value, UUID):
        return True, str(value), None
    if isinstance(value, datetime):
        return True, value.isoformat(), None
    if isinstance(value, date):
        return True, value.isoformat(), None
    if isinstance(value, time):
        return True, value.isoformat(), None
    if isinstance(value, bytes):
        return (
            False,
            None,
            f"Column '{field}' in row {row} is binary and not dashboard-serializable. "
            "No replacement value was generated.",
        )
    if isinstance(value, Decimal):
        if not value.is_finite():
            return (
                False,
                None,
                f"Column '{field}' in row {row} is not a finite numeric value. "
                "No replacement value was generated.",
            )
        if value == value.to_integral_value():
            return True, int(value), None
        return True, float(value), None
    if isinstance(value, int) and not isinstance(value, bool):
        return True, value, None
    if isinstance(value, float):
        if not math.isfinite(value):
            return (
                False,
                None,
                f"Column '{field}' in row {row} is not a finite numeric value. "
                "No replacement value was generated.",
            )
        return True, value, None
    if isinstance(value, (list, tuple)):
        converted_items: list[Any] = []
        for item in value:
            ok, converted, error = _serializable_value(item, field=field, row=row)
            if not ok:
                return False, None, error
            converted_items.append(converted)
        return True, converted_items, None
    if isinstance(value, dict):
        converted_map: dict[str, Any] = {}
        for nested_key, nested_value in value.items():
            ok, converted, error = _serializable_value(nested_value, field=field, row=row)
            if not ok:
                return False, None, error
            converted_map[str(nested_key)] = converted
        return True, converted_map, None
    return (
        False,
        None,
        f"Column '{field}' in row {row} has a non-serializable type {type(value).__name__}. "
        "No replacement value was generated.",
    )
