"""Regression guard for the static SQL used by GET /tables/sources.

The route tests use a fake DB that never executes SQL, so a typo inside the SQL
text (for example a stray ']' before LEFT JOIN) would pass every test but fail
on the real Postgres database. These checks inspect the SQL text itself.
"""

from __future__ import annotations

import re

from commerce_connector.api.routers import tables


def test_sources_sql_has_no_stray_brackets():
    assert "]" not in tables._SOURCES_SQL
    assert "[" not in tables._SOURCES_SQL


def test_sources_sql_parentheses_are_balanced():
    sql = tables._SOURCES_SQL
    assert sql.count("(") == sql.count(")")


def test_sources_sql_is_read_only_and_tenant_scoped():
    sql = tables._SOURCES_SQL
    assert sql.lstrip().upper().startswith("SELECT")
    assert not re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", sql, re.I
    )
    assert "c.tenant_id = %s" in sql
    assert sql.count("%s") == 1
    assert "ORDER BY c.created_at DESC" in sql


def test_sources_sql_does_not_select_secret_columns():
    sql = tables._SOURCES_SQL.lower()
    for forbidden in (
        "config",
        "metadata",
        "base_url",
        "credential",
        "secret",
        "token",
    ):
        assert forbidden not in sql


def test_sources_sql_keywords_are_well_formed():
    # Every JOIN clause must start at a keyword boundary (catches glued tokens like ']LEFT').
    for line in tables._SOURCES_SQL.splitlines():
        stripped = line.strip()
        if "JOIN" in stripped:
            assert re.match(r"^(LEFT |INNER )?JOIN\b", stripped), stripped


def test_count_sql_template_is_grouped_and_tenant_scoped():
    sql = tables._COUNT_SQL_TMPL.format(table="orders")
    assert "GROUP BY connection_id" in sql
    assert "tenant_id = %s" in sql
    assert sql.count("%s") == 1
