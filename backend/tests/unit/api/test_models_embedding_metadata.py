from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import commerce_connector.api.routers.models as models_router
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user
from commerce_connector.api.config import APISettings

GROQ_FAKE_KEY = "groq-fake-key-not-real"
NVIDIA_FAKE_KEY = "nvidia-fake-key-not-real"


def _get_item(monkeypatch, settings: APISettings) -> dict:
    monkeypatch.setattr(models_router, "get_api_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="user-models-test", email="user@example.com", raw={}
    )
    try:
        response = TestClient(app).get("/api/v1/models")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    return response.json()["items"][0]


def test_models_reports_active_nvidia_embedding(monkeypatch):
    settings = APISettings(
        groq_api_key=GROQ_FAKE_KEY,
        embedding_provider="nvidia",
        nvidia_api_key=NVIDIA_FAKE_KEY,
        nvidia_embedding_model="custom/model-x",
        ollama_embedding_model="custom-ollama:latest",
    )

    item = _get_item(monkeypatch, settings)

    assert item["embedding_provider"] == "nvidia"
    assert item["embedding_model"] == "custom/model-x"
    assert item["embedding_dimensions"] == 768


def test_models_reports_active_ollama_embedding(monkeypatch):
    settings = APISettings(
        groq_api_key=GROQ_FAKE_KEY,
        embedding_provider="ollama",
        nvidia_embedding_model="custom/model-x",
        ollama_embedding_model="custom-ollama:latest",
    )

    item = _get_item(monkeypatch, settings)

    assert item["embedding_provider"] == "ollama"
    assert item["embedding_model"] == "custom-ollama:latest"


def test_models_keeps_groq_generation_metadata(monkeypatch):
    settings = APISettings(
        groq_api_key=GROQ_FAKE_KEY,
        groq_model="openai/gpt-oss-20b",
        embedding_provider="nvidia",
        nvidia_api_key=NVIDIA_FAKE_KEY,
    )

    item = _get_item(monkeypatch, settings)

    assert item["provider"] == "groq"
    assert item["backend_model"] == "openai/gpt-oss-20b"
    assert item["available"] is True


def test_models_response_never_contains_api_keys(monkeypatch):
    settings = APISettings(
        groq_api_key=GROQ_FAKE_KEY,
        embedding_provider="nvidia",
        nvidia_api_key=NVIDIA_FAKE_KEY,
    )

    item = _get_item(monkeypatch, settings)

    dumped = repr(item)
    assert NVIDIA_FAKE_KEY not in dumped
    assert GROQ_FAKE_KEY not in dumped