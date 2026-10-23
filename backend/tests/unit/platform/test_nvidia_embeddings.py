from __future__ import annotations

import json

import pytest

import commerce_connector.platform.nvidia_embeddings as nvidia_module
from commerce_connector.platform.nvidia_embeddings import (
    DEFAULT_NVIDIA_BASE_URL,
    DEFAULT_NVIDIA_EMBEDDING_MODEL,
    NvidiaEmbeddingClient,
    NvidiaEmbeddingError,
)

FAKE_KEY = "fake-test-key-not-real"


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body if isinstance(body, str) else json.dumps(body if body is not None else {})
        self.headers = headers or {}

    @property
    def text(self):
        return self._body

    def json(self):
        return json.loads(self._body)


def ok_body(vector=None):
    return {"data": [{"index": 0, "embedding": vector if vector is not None else [0.25] * 768}]}


def install_fake_post(monkeypatch, steps):
    """Replace httpx.post. Each step is a FakeResponse or an Exception to raise.

    The last step repeats if more calls arrive than steps. Returns (calls, sleeps).
    """
    calls: list[dict] = []
    sleeps: list[float] = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        step = steps[min(len(calls) - 1, len(steps) - 1)]
        if isinstance(step, Exception):
            raise step
        return step

    monkeypatch.setattr(nvidia_module.httpx, "post", fake_post)
    monkeypatch.setattr(nvidia_module.time, "sleep", lambda seconds: sleeps.append(seconds))
    return calls, sleeps


def make_client(**kwargs):
    return NvidiaEmbeddingClient(FAKE_KEY, **kwargs)


# ---------------------------------------------------------------- request shape


def test_document_request_endpoint_payload_and_headers(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    vector = make_client().embed("net sales metric", task="document")

    assert len(vector) == 768
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://integrate.api.nvidia.com/v1/embeddings"
    assert call["json"] == {
        "model": "nvidia/llama-nemotron-embed-vl-1b-v2",
        "input": ["net sales metric"],
        "encoding_format": "float",
        "dimensions": 768,
        "input_type": "passage",
    }
    assert call["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["timeout"] == 15.0
    assert call["trust_env"] is False


def test_query_task_uses_query_input_type(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    make_client().embed("total revenue", task="query")

    assert calls[0]["json"]["input_type"] == "query"
    assert calls[0]["json"]["input"] == ["total revenue"]


def test_document_and_query_use_different_input_types(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])
    client = make_client()

    client.embed("same text", task="document")
    client.embed("same text", task="query")

    assert [c["json"]["input_type"] for c in calls] == ["passage", "query"]


def test_base_url_trailing_slash_is_normalised(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    make_client(base_url="https://example.test/v1/").embed("x", task="query")

    assert calls[0]["url"] == "https://example.test/v1/embeddings"


def test_system_proxy_flag_is_forwarded(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    make_client(use_system_proxy=True).embed("x", task="query")

    assert calls[0]["trust_env"] is True


def test_api_key_is_stripped_in_header(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    NvidiaEmbeddingClient(f"  {FAKE_KEY}  ").embed("x", task="query")

    assert calls[0]["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"


# ---------------------------------------------------------------- constructor


def test_defaults_match_confirmed_model_and_url():
    client = make_client()

    assert client.model == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert client.base_url == "https://integrate.api.nvidia.com/v1"
    assert client.dimensions == 768
    assert DEFAULT_NVIDIA_EMBEDDING_MODEL == client.model
    assert DEFAULT_NVIDIA_BASE_URL == client.base_url


def test_blank_model_and_base_url_fall_back_to_defaults():
    client = make_client(model="   ", base_url="  ")

    assert client.model == DEFAULT_NVIDIA_EMBEDDING_MODEL
    assert client.base_url == DEFAULT_NVIDIA_BASE_URL


@pytest.mark.parametrize("key", ["", "   "])
def test_missing_api_key_is_rejected(key):
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        NvidiaEmbeddingClient(key)


@pytest.mark.parametrize("dimensions", [0, -1])
def test_non_positive_dimensions_are_rejected(dimensions):
    with pytest.raises(ValueError, match="EMBEDDING_DIMENSIONS"):
        make_client(dimensions=dimensions)


def test_repr_does_not_expose_api_key():
    assert FAKE_KEY not in repr(make_client())


# ---------------------------------------------------------------- input validation


def test_invalid_task_is_rejected_without_http_call(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    with pytest.raises(ValueError, match="query"):
        make_client().embed("x", task="passage")

    assert calls == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_is_rejected_without_http_call(monkeypatch, text):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(200, ok_body())])

    with pytest.raises(ValueError, match="empty"):
        make_client().embed(text, task="document")

    assert calls == []


# ---------------------------------------------------------------- response parsing


def test_successful_response_returns_exactly_768_floats(monkeypatch):
    install_fake_post(monkeypatch, [FakeResponse(200, ok_body([1] * 768))])

    vector = make_client().embed("x", task="query")

    assert len(vector) == 768
    assert all(isinstance(v, float) for v in vector)


@pytest.mark.parametrize("size", [0, 1, 767, 769, 1024])
def test_wrong_dimension_is_rejected(monkeypatch, size):
    install_fake_post(monkeypatch, [FakeResponse(200, ok_body([0.1] * size))])

    with pytest.raises(NvidiaEmbeddingError, match="dimension mismatch"):
        make_client().embed("x", task="query")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": []},
        {"data": [{}]},
        {"data": ["not-a-dict"]},
        {"data": [{"embedding": "abc"}]},
        {"data": [{"embedding": None}]},
        {"data": {"embedding": [0.1] * 768}},
        {"data": None},
        {"embeddings": [[0.1] * 768]},
        [],
        None,
    ],
)
def test_unexpected_response_shapes_are_rejected(monkeypatch, body):
    install_fake_post(monkeypatch, [FakeResponse(200, json.dumps(body))])

    with pytest.raises(NvidiaEmbeddingError, match="Unexpected NVIDIA embedding response shape"):
        make_client().embed("x", task="query")


@pytest.mark.parametrize("bad_value", ["abc", None, [1], {"x": 1}])
def test_non_numeric_values_are_rejected(monkeypatch, bad_value):
    vector = [0.1] * 767 + [bad_value]
    install_fake_post(monkeypatch, [FakeResponse(200, ok_body(vector))])

    with pytest.raises(NvidiaEmbeddingError, match="non-numeric"):
        make_client().embed("x", task="query")


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinity_values_are_rejected(monkeypatch, bad_value):
    # json.dumps writes these as NaN / Infinity / -Infinity, which json.loads accepts.
    vector = [0.1] * 767 + [bad_value]
    install_fake_post(monkeypatch, [FakeResponse(200, ok_body(vector))])

    with pytest.raises(NvidiaEmbeddingError, match="NaN or infinite"):
        make_client().embed("x", task="query")


def test_finite_values_including_zero_and_negatives_still_pass(monkeypatch):
    vector = [0.0, -0.5, 1e-9] + [0.1] * 765
    install_fake_post(monkeypatch, [FakeResponse(200, ok_body(vector))])

    assert make_client().embed("x", task="query") == vector


def test_invalid_json_body_is_rejected(monkeypatch):
    install_fake_post(monkeypatch, [FakeResponse(200, "<html>gateway page</html>")])

    with pytest.raises(NvidiaEmbeddingError, match="invalid JSON"):
        make_client().embed("x", task="query")


# ---------------------------------------------------------------- HTTP errors / retries


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_non_transient_http_errors_fail_fast_without_retry(monkeypatch, status):
    calls, sleeps = install_fake_post(
        monkeypatch, [FakeResponse(status, {"error": "rejected"})]
    )

    with pytest.raises(NvidiaEmbeddingError, match=f"HTTP {status}"):
        make_client().embed("x", task="query")

    assert len(calls) == 1
    assert sleeps == []


def test_rate_limit_then_success_honours_retry_after(monkeypatch):
    calls, sleeps = install_fake_post(
        monkeypatch,
        [
            FakeResponse(429, {"error": "slow down"}, headers={"retry-after": "3"}),
            FakeResponse(200, ok_body()),
        ],
    )

    vector = make_client().embed("x", task="document")

    assert len(vector) == 768
    assert len(calls) == 2
    assert sleeps == [3.0]


def test_retry_after_is_capped_at_30_seconds(monkeypatch):
    _, sleeps = install_fake_post(
        monkeypatch,
        [
            FakeResponse(429, {}, headers={"retry-after": "9999"}),
            FakeResponse(200, ok_body()),
        ],
    )

    make_client().embed("x", task="query")

    assert sleeps == [30.0]


def test_invalid_retry_after_falls_back_to_exponential_backoff(monkeypatch):
    _, sleeps = install_fake_post(
        monkeypatch,
        [
            FakeResponse(503, {}, headers={"retry-after": "soon"}),
            FakeResponse(200, ok_body()),
        ],
    )

    make_client().embed("x", task="query")

    assert sleeps == [1.0]


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_every_transient_status_is_retried(monkeypatch, status):
    calls, _ = install_fake_post(
        monkeypatch, [FakeResponse(status, {}), FakeResponse(200, ok_body())]
    )

    make_client().embed("x", task="query")

    assert len(calls) == 2


def test_exponential_backoff_between_attempts(monkeypatch):
    calls, sleeps = install_fake_post(
        monkeypatch,
        [
            FakeResponse(503, {}),
            FakeResponse(503, {}),
            FakeResponse(200, ok_body()),
        ],
    )

    make_client().embed("x", task="query")

    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_rate_limit_exhausts_all_attempts_then_raises(monkeypatch):
    calls, sleeps = install_fake_post(
        monkeypatch, [FakeResponse(429, {"error": "rate limited"})]
    )

    with pytest.raises(NvidiaEmbeddingError, match="HTTP 429"):
        make_client(max_attempts=4).embed("x", task="query")

    assert len(calls) == 4
    assert len(sleeps) == 3


def test_max_attempts_one_means_no_retry(monkeypatch):
    calls, sleeps = install_fake_post(monkeypatch, [FakeResponse(503, {})])

    with pytest.raises(NvidiaEmbeddingError, match="HTTP 503"):
        make_client(max_attempts=1).embed("x", task="query")

    assert len(calls) == 1
    assert sleeps == []


def test_max_attempts_below_one_is_clamped_to_one(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [FakeResponse(503, {})])

    with pytest.raises(NvidiaEmbeddingError):
        make_client(max_attempts=0).embed("x", task="query")

    assert len(calls) == 1


def test_http_error_message_is_truncated_to_500_chars(monkeypatch):
    install_fake_post(monkeypatch, [FakeResponse(400, "x" * 5000)])

    with pytest.raises(NvidiaEmbeddingError) as exc:
        make_client().embed("x", task="query")

    assert len(str(exc.value)) < 600


# ---------------------------------------------------------------- network failures


def test_timeout_then_success_is_retried(monkeypatch):
    calls, sleeps = install_fake_post(
        monkeypatch,
        [nvidia_module.httpx.TimeoutException("timed out"), FakeResponse(200, ok_body())],
    )

    vector = make_client().embed("x", task="query")

    assert len(vector) == 768
    assert len(calls) == 2
    assert sleeps == [1.0]


def test_persistent_timeout_raises_clear_error_without_secrets(monkeypatch):
    calls, sleeps = install_fake_post(
        monkeypatch, [nvidia_module.httpx.TimeoutException("timed out")]
    )

    with pytest.raises(NvidiaEmbeddingError, match="Could not reach") as exc:
        make_client(max_attempts=3).embed("x", task="query")

    assert len(calls) == 3
    assert len(sleeps) == 2
    assert "TimeoutException" in str(exc.value)
    assert FAKE_KEY not in str(exc.value)


def test_connection_error_is_retried_and_then_reported(monkeypatch):
    calls, _ = install_fake_post(
        monkeypatch, [nvidia_module.httpx.ConnectError("no route")]
    )

    with pytest.raises(NvidiaEmbeddingError, match="Could not reach"):
        make_client(max_attempts=2).embed("x", task="query")

    assert len(calls) == 2


def test_oserror_is_treated_as_network_failure(monkeypatch):
    calls, _ = install_fake_post(monkeypatch, [OSError("socket closed")])

    with pytest.raises(NvidiaEmbeddingError, match="Could not reach"):
        make_client(max_attempts=2).embed("x", task="query")

    assert len(calls) == 2


# ---------------------------------------------------------------- secrets


@pytest.mark.parametrize(
    "step",
    [
        FakeResponse(401, {"error": "unauthorized"}),
        FakeResponse(200, {"unexpected": True}),
        FakeResponse(200, ok_body([0.1] * 10)),
        nvidia_module.httpx.TimeoutException("timed out"),
    ],
)
def test_error_messages_never_contain_api_key(monkeypatch, step):
    install_fake_post(monkeypatch, [step])

    with pytest.raises(NvidiaEmbeddingError) as exc:
        make_client(max_attempts=1).embed("x", task="query")

    assert FAKE_KEY not in str(exc.value)