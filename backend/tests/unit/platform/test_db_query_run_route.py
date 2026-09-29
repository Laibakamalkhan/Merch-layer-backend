from commerce_connector.platform.db import PostgresGateway


def test_update_query_run_ignores_unknown_route_without_enum_cast(monkeypatch):
    gateway = PostgresGateway.__new__(PostgresGateway)
    captured = {}

    def fake_execute(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params

    monkeypatch.setattr(gateway, "execute", fake_execute)

    gateway.update_query_run(
        "run-1",
        status="completed",
        route="summary",
        intent={"metric": "revenue"},
    )

    assert "e.enumlabel::app.ai_route" in captured["sql"]
    assert "e.enumlabel = %s" in captured["sql"]
    assert captured["params"][0] == "completed"
    assert captured["params"][1] == "summary"
    assert captured["params"][2] == '{"metric": "revenue"}'
    assert captured["params"][-1] == "run-1"
