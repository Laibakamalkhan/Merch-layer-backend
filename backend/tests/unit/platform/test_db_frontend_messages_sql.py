from __future__ import annotations

from contextlib import contextmanager
from typing import Any
import uuid

import pytest
from commerce_connector.platform.db import PostgresGateway


AI_MESSAGES_COLUMNS = [
    "id",
    "conversation_id",
    "tenant_id",
    "role",
    "content",
    "metadata",
    "file_ids",
    "created_at",
]


class _CapturedCursor:
    def __init__(self, rows: list[dict[str, Any]] | None = None):
        self.calls: list[tuple[Any, Any]] = []
        self._rows = rows or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: Any, params: Any = None):
        self.calls.append((sql, params))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _CapturedConnection:
    def __init__(self, cursor_obj: _CapturedCursor):
        self._cursor = cursor_obj

    def cursor(self):
        return self._cursor


def _build_test_gateway(
    cursor_obj: _CapturedCursor,
    table_columns: list[str] | None = None,
) -> PostgresGateway:
    gateway = PostgresGateway.__new__(PostgresGateway)
    connection = _CapturedConnection(cursor_obj)

    @contextmanager
    def fake_connection():
        yield connection

    gateway.connection = fake_connection  # type: ignore[assignment]
    gateway.table_columns = lambda schema, table: list(table_columns or AI_MESSAGES_COLUMNS)  # type: ignore[assignment]
    return gateway


def test_read_frontend_table_ai_messages_sql_structure_and_parameters():
    """Verify that read_frontend_table generates the parent EXISTS clause

    inside WHERE, before ORDER BY and LIMIT, with bound parameters.
    """
    cursor = _CapturedCursor(rows=[{"id": "msg-1", "content": "hello"}])
    gateway = _build_test_gateway(cursor)

    tenant_id = str(uuid.uuid4())
    owner_user_id = str(uuid.uuid4())

    results = gateway.read_frontend_table(
        schema="ai",
        table="messages",
        scope="tenant",
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        parent_schema="ai",
        parent_table="conversations",
        parent_fk="conversation_id",
        limit=50,
        offset=10,
    )

    assert results == [{"id": "msg-1", "content": "hello"}]
    assert len(cursor.calls) == 1

    statement, params = cursor.calls[0]
    sql_text = statement.as_string(None)

    # 1. SQL includes parent EXISTS ownership condition
    expected_exists = (
        'exists(select 1 from "ai"."conversations" '
        'where "ai"."conversations"."id" = "ai"."messages"."conversation_id" '
        'and "ai"."conversations"."user_id" = %s '
        'and "ai"."conversations"."tenant_id" = %s)'
    )
    assert expected_exists in sql_text

    # 2. Condition is placed inside WHERE, before ORDER BY and LIMIT/OFFSET
    where_idx = sql_text.index("where ")
    exists_idx = sql_text.index(expected_exists)
    order_idx = sql_text.index("order by ")
    limit_idx = sql_text.index("limit %s offset %s")

    assert where_idx < exists_idx < order_idx < limit_idx

    # 3. Parameter safety: user and tenant values are bound, NOT string-interpolated
    assert tenant_id not in sql_text
    assert owner_user_id not in sql_text
    assert params == [tenant_id, owner_user_id, tenant_id, 50, 10]


def test_count_frontend_table_ai_messages_sql_structure_and_parameters():
    """Verify that count_frontend_table applies parent EXISTS inside WHERE

    before counting rows, with bound parameters.
    """
    cursor = _CapturedCursor(rows=[{"total": 7}])
    gateway = _build_test_gateway(cursor)

    tenant_id = str(uuid.uuid4())
    owner_user_id = str(uuid.uuid4())

    total = gateway.count_frontend_table(
        schema="ai",
        table="messages",
        scope="tenant",
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        parent_schema="ai",
        parent_table="conversations",
        parent_fk="conversation_id",
    )

    assert total == 7
    assert len(cursor.calls) == 1

    statement, params = cursor.calls[0]
    sql_text = statement.as_string(None)

    # 1. SQL selects count with WHERE filtering
    assert sql_text.startswith('select count(*)::bigint as total from "ai"."messages" where ')
    expected_exists = (
        'exists(select 1 from "ai"."conversations" '
        'where "ai"."conversations"."id" = "ai"."messages"."conversation_id" '
        'and "ai"."conversations"."user_id" = %s '
        'and "ai"."conversations"."tenant_id" = %s)'
    )
    assert expected_exists in sql_text

    # 2. No string interpolation of user or tenant IDs
    assert tenant_id not in sql_text
    assert owner_user_id not in sql_text
    assert params == [tenant_id, owner_user_id, tenant_id]


def test_get_frontend_record_forwards_parent_scope_parameters():
    """Verify get_frontend_record forwards parent-scope kwargs to read_frontend_table."""
    cursor = _CapturedCursor(rows=[{"id": "msg-target", "role": "user"}])
    gateway = _build_test_gateway(cursor)

    tenant_id = str(uuid.uuid4())
    owner_user_id = str(uuid.uuid4())
    record_id = str(uuid.uuid4())

    record = gateway.get_frontend_record(
        schema="ai",
        table="messages",
        record_id=record_id,
        scope="tenant",
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        parent_schema="ai",
        parent_table="conversations",
        parent_fk="conversation_id",
    )

    assert record == {"id": "msg-target", "role": "user"}
    assert len(cursor.calls) == 1

    statement, params = cursor.calls[0]
    sql_text = statement.as_string(None)

    # Parent EXISTS clause is preserved in detail fetch
    assert 'exists(select 1 from "ai"."conversations"' in sql_text
    assert '"ai"."messages"."id" = %s' in sql_text or '"id" = %s' in sql_text
    assert tenant_id not in sql_text
    assert owner_user_id not in sql_text
    assert record_id not in sql_text

    # Positional parameters: tenant_id, owner_user_id, tenant_id, id_filter, limit, offset
    assert params == [tenant_id, owner_user_id, tenant_id, record_id, 1, 0]


def test_read_frontend_table_rejects_missing_parent_fk():
    """Verify that an unknown parent FK column raises ValueError immediately."""
    cursor = _CapturedCursor()
    gateway = _build_test_gateway(cursor)

    with pytest.raises(ValueError, match="Parent FK column 'bad_fk' does not exist"):
        gateway.read_frontend_table(
            schema="ai",
            table="messages",
            scope="tenant",
            tenant_id="t-1",
            owner_user_id="u-1",
            parent_schema="ai",
            parent_table="conversations",
            parent_fk="bad_fk",
        )
