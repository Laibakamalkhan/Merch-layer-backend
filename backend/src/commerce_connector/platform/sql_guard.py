from __future__ import annotations

import re
from dataclasses import dataclass


FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|truncate|create|grant|revoke|copy|call|do|execute|vacuum|analyze|refresh)\b",
    re.IGNORECASE,
)
TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)", re.IGNORECASE)


@dataclass(slots=True)
class GuardResult:
    ok: bool
    sql: str
    reason: str | None = None


class SQLGuard:
    """Conservative read-only guard for LLM-generated analytics SQL."""

    DEFAULT_ALLOWED_SCHEMAS = {"gold", "silver", "control"}
    BLOCKED_TABLES = {
        ("control", "connection_credentials"),
        ("bronze", "records"),
        ("bronze", "raw_objects"),
        ("ai", "messages"),
    }

    def __init__(self, allowed_tables: set[tuple[str, str]] | None = None, max_rows: int = 5000):
        self.allowed_tables = allowed_tables
        self.max_rows = max_rows

    def validate(self, sql: str) -> GuardResult:
        candidate = sql.strip()
        candidate = re.sub(r"^```(?:sql)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
        candidate = candidate.strip().rstrip(";").strip()

        if not candidate:
            return GuardResult(False, candidate, "Empty SQL")
        if ";" in candidate:
            return GuardResult(False, candidate, "Multiple SQL statements are not allowed")
        if not re.match(r"^(select|with)\b", candidate, re.IGNORECASE):
            return GuardResult(False, candidate, "Only SELECT/CTE queries are allowed")
        if FORBIDDEN.search(candidate):
            return GuardResult(False, candidate, "Mutation/DDL keyword detected")
        if ":tenant_id" not in candidate:
            return GuardResult(False, candidate, "Query must contain the :tenant_id tenant filter placeholder")

        refs = {(schema.lower(), table.lower()) for schema, table in TABLE_REF.findall(candidate)}
        if not refs:
            return GuardResult(False, candidate, "Query must reference qualified Silver/Gold tables")
        for ref in refs:
            if ref in self.BLOCKED_TABLES:
                return GuardResult(False, candidate, f"Blocked table: {ref[0]}.{ref[1]}")
            if ref[0] not in self.DEFAULT_ALLOWED_SCHEMAS:
                return GuardResult(False, candidate, f"Schema not allowed: {ref[0]}")
            if self.allowed_tables is not None and ref not in self.allowed_tables:
                return GuardResult(False, candidate, f"Table not allowed: {ref[0]}.{ref[1]}")

        # All tenant-scoped analytics queries must include a direct tenant predicate.
        if not re.search(r"\btenant_id\s*=\s*:tenant_id\b|\b[a-z_][a-z0-9_]*\.tenant_id\s*=\s*:tenant_id\b", candidate, re.IGNORECASE):
            return GuardResult(False, candidate, "An explicit tenant_id = :tenant_id predicate is required")

        # Convert the model-facing placeholder into psycopg named-parameter syntax.
        executable = candidate.replace(":tenant_id", "%(tenant_id)s")
        if not re.search(r"\blimit\s+\d+\b", executable, re.IGNORECASE):
            executable = f"{executable}\nLIMIT {self.max_rows}"
        return GuardResult(True, executable)
