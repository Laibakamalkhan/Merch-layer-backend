from contextlib import contextmanager

from commerce_connector.platform.db import PostgresGateway


class _FakeCursor:
    def __init__(self):
        self.calls = []
        self._rows = [{"value": 42}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FakeCursor()

    def cursor(self):
        return self.cursor_obj


def test_execute_readonly_query_sets_transaction_local_timeout(monkeypatch):
    gateway = PostgresGateway.__new__(PostgresGateway)
    connection = _FakeConnection()

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(gateway, "connection", fake_connection)

    rows = gateway.execute_readonly_query(
        "select 42 as value where tenant_id = %(tenant_id)s",
        "tenant-1",
        timeout_ms=15000,
    )

    assert rows == [{"value": 42}]
    assert connection.cursor_obj.calls == [
        ("set transaction read only", None),
        (
            "select set_config('statement_timeout', %s, true)",
            ("15000ms",),
        ),
        (
            "select 42 as value where tenant_id = %(tenant_id)s",
            {"tenant_id": "tenant-1"},
        ),
    ]
