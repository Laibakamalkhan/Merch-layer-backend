from __future__ import annotations

import json

import pytest

import commerce_connector.platform.groq as groq_module
from commerce_connector.platform.groq import GroqAPIError, GroqClient, GroqTransportError


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body if isinstance(body, str) else json.dumps(body or {}).encode()
        self.headers = headers or {}

    @property
    def text(self):
        return self._body.decode()

    def json(self):
        return json.loads(self.text)


def test_groq_structured_output_uses_json_schema(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            body={"choices": [{"message": {"content": '{"ok":true}'}}]}
        )

    monkeypatch.setattr(groq_module.httpx, "post", fake_post)
    client = GroqClient("key")
    result = client.generate_json(
        "Return JSON",
        system="test",
        schema_name="test_schema",
        schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
        },
    )

    assert result == {"ok": True}
    assert calls[0][0] == "https://api.groq.com/openai/v1/chat/completions"
    payload = calls[0][1]["json"]
    assert payload["model"] == "openai/gpt-oss-20b"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True


def test_groq_http_error_is_classified():
    client = GroqClient("key")
    monkeypatch_response = FakeResponse(503, {"error": {"message": "unavailable"}})
    with pytest.raises(GroqAPIError) as exc:
        # Exercise the public error classification without making a network call.
        class Stub:
            def __init__(self, response):
                self.response = response
        client._post = lambda payload: monkeypatch_response
        client.generate_json(
            "Return JSON",
            schema_name="test_schema",
            schema={"type": "object", "additionalProperties": False, "required": [], "properties": {}},
        )
    assert exc.value.status_code == 503
    assert "unavailable" in exc.value.body


def test_groq_transport_error_is_distinct(monkeypatch):
    client = GroqClient("key")

    def fail(*args, **kwargs):
        raise groq_module.httpx.ConnectError("no internet")

    monkeypatch.setattr(groq_module.httpx, "post", fail)
    monkeypatch.setattr(groq_module.time, "sleep", lambda _: None)

    with pytest.raises(GroqTransportError, match="transport"):
        client.generate_text("hello")


def test_ollama_embedding_contract_stays_768(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(body={"embeddings": [[0.1] * 768]})

    monkeypatch.setattr(groq_module.httpx, "post", fake_post)
    client = GroqClient("key", embedding_provider="ollama")
    vector = client.embed("total revenue", task="query")

    assert len(vector) == 768
    assert calls[0][0] == "http://localhost:11434/api/embed"
    assert calls[0][1]["json"]["model"] == "embeddinggemma:latest"
