from __future__ import annotations

import urllib.error

import pytest

from commerce_connector.platform.gemini import (
    GeminiAPIError,
    GeminiClient,
    GeminiTransportError,
)


class _HTTPErrorOpener:
    def __init__(self, code: int, body: bytes):
        self.code = code
        self.body = body

    def open(self, request, timeout=0):
        raise urllib.error.HTTPError(
            request.full_url,
            self.code,
            "provider error",
            {"Content-Type": "application/json"},
            __import__("io").BytesIO(self.body),
        )


def test_gemini_503_is_classified_as_provider_http_error(monkeypatch):
    client = GeminiClient("key", embedding_provider="ollama")
    opener = _HTTPErrorOpener(503, b'{"error":{"status":"UNAVAILABLE"}}')
    monkeypatch.setattr(client, "_post", lambda url, payload: (_ for _ in ()).throw(GeminiAPIError(503, opener.body)))

    with pytest.raises(GeminiAPIError) as exc:
        client.generate_json('Return {"ok": true}')

    assert exc.value.status_code == 503
    assert "UNAVAILABLE" in exc.value.body


def test_gemini_transport_error_is_distinct(monkeypatch):
    client = GeminiClient("key", embedding_provider="ollama")
    monkeypatch.setattr(
        client,
        "_post",
        lambda url, payload: (_ for _ in ()).throw(GeminiTransportError("TLS EOF")),
    )

    with pytest.raises(GeminiTransportError, match="TLS EOF"):
        client.generate_text("hello")

def test_gemini_post_returns_http_error_as_provider_response(monkeypatch):
    import commerce_connector.platform.gemini as gemini_module

    client = GeminiClient("key", embedding_provider="ollama")
    body = b'{"error":{"status":"UNAVAILABLE"}}'

    class Always503:
        def open(self, request, timeout=0):
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "provider error",
                {"Content-Type": "application/json"},
                __import__("io").BytesIO(body),
            )

    monkeypatch.setattr(gemini_module.urllib.request, "build_opener", lambda *a, **k: Always503())
    monkeypatch.setattr(gemini_module.time, "sleep", lambda _: None)

    response = client._post("https://example.test", {"x": 1})

    assert response.status_code == 503
    assert "UNAVAILABLE" in response.text


def test_gemini_post_distinguishes_transport_failure(monkeypatch):
    import commerce_connector.platform.gemini as gemini_module

    client = GeminiClient("key", embedding_provider="ollama")

    class AlwaysTLSFailure:
        def open(self, request, timeout=0):
            raise urllib.error.URLError("SSL: UNEXPECTED_EOF_WHILE_READING")

    monkeypatch.setattr(gemini_module.urllib.request, "build_opener", lambda *a, **k: AlwaysTLSFailure())
    monkeypatch.setattr(gemini_module.time, "sleep", lambda _: None)

    with pytest.raises(GeminiTransportError, match="network/TLS/proxy"):
        client._post("https://example.test", {"x": 1})
