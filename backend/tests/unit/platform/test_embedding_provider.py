from __future__ import annotations

import json
import sys
import types

import pytest

import commerce_connector.api.deps as deps_module
import commerce_connector.platform.groq as groq_module
from commerce_connector.api.config import APISettings
from commerce_connector.platform.groq import GroqClient
from commerce_connector.platform.nvidia_embeddings import (
    DEFAULT_NVIDIA_BASE_URL,
    DEFAULT_NVIDIA_EMBEDDING_MODEL,
    NvidiaEmbeddingError,
)
from commerce_connector.platform.settings import PlatformSettings

GROQ_FAKE_KEY = "groq-fake-key-not-real"
NVIDIA_FAKE_KEY = "nvidia-fake-key-not-real"
FAKE_DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/testdb"

EMBEDDING_ENV_NAMES = [
    "EMBEDDING_PROVIDER",
    "EMBEDDING_DIMENSIONS",
    "OLLAMA_BASE_URL",
    "OLLAMA_EMBEDDING_MODEL",
    "NVIDIA_API_KEY",
    "NVIDIA_BASE_URL",
    "NVIDIA_EMBEDDING_MODEL",
]


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


def nvidia_body(size=768):
    return {"data": [{"index": 0, "embedding": [0.25] * size}]}


def install_fake_post(monkeypatch, response):
    calls: list[dict] = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(groq_module.httpx, "post", fake_post)
    return calls


def make_groq(**kwargs):
    return GroqClient(GROQ_FAKE_KEY, **kwargs)


def make_nvidia_groq(**kwargs):
    return GroqClient(
        GROQ_FAKE_KEY,
        embedding_provider="nvidia",
        nvidia_api_key=NVIDIA_FAKE_KEY,
        **kwargs,
    )


def clean_embedding_env(monkeypatch):
    for name in EMBEDDING_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------- GroqClient: provider selection


def test_nvidia_provider_reports_active_model_and_provider():
    client = make_nvidia_groq()

    assert client.embedding_provider == "nvidia"
    assert client.embedding_model == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert client.embedding_dimensions == 768


def test_nvidia_custom_model_is_reported():
    client = make_nvidia_groq(nvidia_embedding_model="custom/model-x")

    assert client.embedding_model == "custom/model-x"


def test_blank_nvidia_base_url_and_model_fall_back_to_defaults():
    # Railway can hold a blank variable; the client must still use safe defaults.
    client = make_nvidia_groq(nvidia_base_url="", nvidia_embedding_model="")

    assert client.embedding_model == DEFAULT_NVIDIA_EMBEDDING_MODEL
    assert client._nvidia.base_url == DEFAULT_NVIDIA_BASE_URL


def test_provider_name_is_trimmed_and_lowercased():
    client = GroqClient(
        GROQ_FAKE_KEY,
        embedding_provider="  NVIDIA ",
        nvidia_api_key=NVIDIA_FAKE_KEY,
    )

    assert client.embedding_provider == "nvidia"


def test_blank_provider_falls_back_to_ollama():
    client = make_groq(embedding_provider="   ")

    assert client.embedding_provider == "ollama"
    assert client.embedding_model == "embeddinggemma:latest"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
        make_groq(embedding_provider="openai")


def test_nvidia_provider_requires_api_key():
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        make_groq(embedding_provider="nvidia")


def test_ollama_provider_reports_ollama_model_and_needs_no_nvidia_key():
    client = make_groq()

    assert client.embedding_provider == "ollama"
    assert client.embedding_model == "embeddinggemma:latest"
    assert client._nvidia is None


def test_ollama_custom_model_is_reported():
    client = make_groq(ollama_embedding_model="custom-ollama:latest")

    assert client.embedding_model == "custom-ollama:latest"
    assert client.ollama_embedding_model == "custom-ollama:latest"


# ---------------------------------------------------------------- GroqClient: routing


def test_nvidia_document_embedding_goes_to_nvidia_as_passage(monkeypatch):
    calls = install_fake_post(monkeypatch, FakeResponse(200, nvidia_body()))

    vector = make_nvidia_groq().embed("net sales", task="document", title="Metric: Revenue")

    assert len(vector) == 768
    assert len(calls) == 1
    assert calls[0]["url"] == "https://integrate.api.nvidia.com/v1/embeddings"
    assert "11434" not in calls[0]["url"]
    assert calls[0]["json"]["input_type"] == "passage"
    # The Ollama title/text prompt format must not leak into NVIDIA requests.
    assert calls[0]["json"]["input"] == ["net sales"]
    assert calls[0]["headers"]["Authorization"] == f"Bearer {NVIDIA_FAKE_KEY}"


def test_nvidia_query_embedding_goes_to_nvidia_as_query(monkeypatch):
    calls = install_fake_post(monkeypatch, FakeResponse(200, nvidia_body()))

    make_nvidia_groq().embed("total revenue", task="query")

    assert calls[0]["json"]["input_type"] == "query"
    assert calls[0]["json"]["input"] == ["total revenue"]


def test_nvidia_embed_rejects_invalid_task_without_http_call(monkeypatch):
    calls = install_fake_post(monkeypatch, FakeResponse(200, nvidia_body()))

    with pytest.raises(ValueError, match="query"):
        make_nvidia_groq().embed("x", task="passage")

    assert calls == []


def test_nvidia_dimension_mismatch_surfaces_through_groq_client(monkeypatch):
    install_fake_post(monkeypatch, FakeResponse(200, nvidia_body(767)))

    with pytest.raises(NvidiaEmbeddingError, match="dimension mismatch"):
        make_nvidia_groq().embed("x", task="query")


def test_embedding_dimensions_are_forwarded_to_nvidia(monkeypatch):
    calls = install_fake_post(monkeypatch, FakeResponse(200, nvidia_body(512)))

    vector = make_nvidia_groq(embedding_dimensions=512).embed("x", task="query")

    assert calls[0]["json"]["dimensions"] == 512
    assert len(vector) == 512


def test_ollama_provider_ignores_nvidia_settings(monkeypatch):
    calls = install_fake_post(monkeypatch, FakeResponse(200, {"embeddings": [[0.1] * 768]}))
    client = make_groq(
        embedding_provider="ollama",
        nvidia_api_key=NVIDIA_FAKE_KEY,
        nvidia_embedding_model="custom/model-x",
    )

    vector = client.embed("total revenue", task="query")

    assert len(vector) == 768
    assert calls[0]["url"] == "http://localhost:11434/api/embed"
    assert client.embedding_model == "embeddinggemma:latest"
    assert "Authorization" not in calls[0].get("headers", {})


def test_groq_generation_still_uses_groq_key_and_groq_url(monkeypatch):
    calls = install_fake_post(
        monkeypatch,
        FakeResponse(200, {"choices": [{"message": {"content": "hello there"}}]}),
    )

    text = make_nvidia_groq().generate_text("hello")

    assert text == "hello there"
    assert calls[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == f"Bearer {GROQ_FAKE_KEY}"
    assert NVIDIA_FAKE_KEY not in json.dumps(calls[0]["headers"])
    assert calls[0]["json"]["model"] == "openai/gpt-oss-20b"


# ---------------------------------------------------------------- PlatformSettings


def make_platform_settings(**kwargs):
    return PlatformSettings(
        database_url=FAKE_DATABASE_URL,
        groq_api_key=GROQ_FAKE_KEY,
        **kwargs,
    )


def test_platform_settings_defaults_keep_ollama_and_nvidia_constants():
    settings = make_platform_settings()

    assert settings.embedding_provider == "ollama"
    assert settings.embedding_dimensions == 768
    assert settings.nvidia_api_key == ""
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia_embedding_model == "nvidia/llama-nemotron-embed-vl-1b-v2"


def test_ollama_provider_validates_without_nvidia_key():
    make_platform_settings(embedding_provider="ollama").validate_ai()


def test_nvidia_provider_validates_with_key():
    make_platform_settings(
        embedding_provider="nvidia", nvidia_api_key=NVIDIA_FAKE_KEY
    ).validate_ai()


@pytest.mark.parametrize("key", ["", "   "])
def test_nvidia_provider_without_key_is_rejected(key):
    settings = make_platform_settings(embedding_provider="nvidia", nvidia_api_key=key)

    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        settings.validate_ai()


def test_unknown_embedding_provider_is_rejected():
    settings = make_platform_settings(embedding_provider="openai")

    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
        settings.validate_ai()


def test_missing_groq_key_is_still_rejected():
    settings = PlatformSettings(database_url=FAKE_DATABASE_URL, groq_api_key="")

    with pytest.raises(ValueError, match="Groq API key"):
        settings.validate_ai()


def test_platform_settings_repr_hides_nvidia_key():
    settings = make_platform_settings(
        embedding_provider="nvidia", nvidia_api_key=NVIDIA_FAKE_KEY
    )

    assert NVIDIA_FAKE_KEY not in repr(settings)
    assert NVIDIA_FAKE_KEY not in str(settings)


# ---------------------------------------------------------------- APISettings.from_env


def test_from_env_defaults_keep_ollama_for_local_dev(monkeypatch):
    clean_embedding_env(monkeypatch)

    settings = APISettings.from_env()

    assert settings.embedding_provider == "ollama"
    assert settings.embedding_dimensions == 768
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_embedding_model == "embeddinggemma:latest"
    assert settings.nvidia_api_key == ""
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia_embedding_model == "nvidia/llama-nemotron-embed-vl-1b-v2"


def test_from_env_reads_and_normalises_nvidia_values(monkeypatch):
    clean_embedding_env(monkeypatch)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "  NVIDIA ")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setenv("NVIDIA_API_KEY", f"  {NVIDIA_FAKE_KEY}  ")
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("NVIDIA_EMBEDDING_MODEL", " custom/model-x ")

    settings = APISettings.from_env()

    assert settings.embedding_provider == "nvidia"
    assert settings.embedding_dimensions == 768
    assert settings.nvidia_api_key == NVIDIA_FAKE_KEY
    assert settings.nvidia_base_url == "https://example.test/v1"
    assert settings.nvidia_embedding_model == "custom/model-x"


def test_api_settings_repr_hides_nvidia_key(monkeypatch):
    clean_embedding_env(monkeypatch)
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_FAKE_KEY)

    settings = APISettings.from_env()

    assert settings.nvidia_api_key == NVIDIA_FAKE_KEY
    assert NVIDIA_FAKE_KEY not in repr(settings)
    assert NVIDIA_FAKE_KEY not in str(settings)


# ---------------------------------------------------------------- deps wiring


def _capture_platform_settings(monkeypatch):
    """Replace the heavy service module so get_service() only builds PlatformSettings."""
    captured: dict = {}

    class FakeService:
        def __init__(self, settings, project_root):
            captured["settings"] = settings

    fake_module = types.ModuleType("commerce_connector.platform.service")
    fake_module.CommercePlatformService = FakeService
    monkeypatch.setitem(sys.modules, "commerce_connector.platform.service", fake_module)
    return captured


def test_get_service_passes_nvidia_settings_to_platform_settings(monkeypatch):
    clean_embedding_env(monkeypatch)
    captured = _capture_platform_settings(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", FAKE_DATABASE_URL)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_FAKE_KEY)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "nvidia")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_FAKE_KEY)
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("NVIDIA_EMBEDDING_MODEL", "custom/model-x")

    deps_module.reset_cached_dependencies()
    try:
        deps_module.get_service()
    finally:
        deps_module.reset_cached_dependencies()

    settings = captured["settings"]
    assert settings.embedding_provider == "nvidia"
    assert settings.embedding_dimensions == 768
    assert settings.nvidia_api_key == NVIDIA_FAKE_KEY
    assert settings.nvidia_base_url == "https://example.test/v1"
    assert settings.nvidia_embedding_model == "custom/model-x"
    assert settings.groq_api_key == GROQ_FAKE_KEY
    settings.validate_ai()


def test_get_service_keeps_ollama_wiring_for_local_dev(monkeypatch):
    clean_embedding_env(monkeypatch)
    captured = _capture_platform_settings(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", FAKE_DATABASE_URL)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_FAKE_KEY)
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "custom-ollama:latest")

    deps_module.reset_cached_dependencies()
    try:
        deps_module.get_service()
    finally:
        deps_module.reset_cached_dependencies()

    settings = captured["settings"]
    assert settings.embedding_provider == "ollama"
    assert settings.ollama_embedding_model == "custom-ollama:latest"
    assert settings.nvidia_api_key == ""
    settings.validate_ai()