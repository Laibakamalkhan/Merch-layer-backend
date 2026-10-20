from __future__ import annotations

import pytest

from commerce_connector.api.config import APISettings
from commerce_connector.platform.settings import PlatformSettings

FAKE_DB_PASSWORD = "fake-db-password-not-real"
FAKE_ANALYST_DB_PASSWORD = "fake-analyst-password-not-real"
FAKE_SERVICE_ROLE_KEY = "fake-service-role-key-not-real"
FAKE_ANON_KEY = "fake-anon-key-not-real"
FAKE_GROQ_KEY = "fake-groq-key-not-real"
FAKE_NVIDIA_KEY = "fake-nvidia-key-not-real"

# URLs are assembled at runtime so no literal here looks like a real connection string.
FAKE_DATABASE_URL = "postgresql" + "://dbuser:" + FAKE_DB_PASSWORD + "@localhost:5432/testdb"
FAKE_ANALYST_URL = "postgresql" + "://analyst:" + FAKE_ANALYST_DB_PASSWORD + "@localhost:5432/testdb"

API_SECRETS = [
    FAKE_DATABASE_URL,
    FAKE_DB_PASSWORD,
    FAKE_ANALYST_URL,
    FAKE_ANALYST_DB_PASSWORD,
    FAKE_SERVICE_ROLE_KEY,
    FAKE_ANON_KEY,
    FAKE_GROQ_KEY,
    FAKE_NVIDIA_KEY,
]
PLATFORM_SECRETS = [
    FAKE_DATABASE_URL,
    FAKE_DB_PASSWORD,
    FAKE_SERVICE_ROLE_KEY,
    FAKE_GROQ_KEY,
    FAKE_NVIDIA_KEY,
]


def _api_settings() -> APISettings:
    return APISettings(
        database_url=FAKE_DATABASE_URL,
        supabase_url="https://example.test",
        supabase_service_role_key=FAKE_SERVICE_ROLE_KEY,
        supabase_anon_key=FAKE_ANON_KEY,
        groq_api_key=FAKE_GROQ_KEY,
        nvidia_api_key=FAKE_NVIDIA_KEY,
        analyst_database_url=FAKE_ANALYST_URL,
    )


def _platform_settings() -> PlatformSettings:
    return PlatformSettings(
        database_url=FAKE_DATABASE_URL,
        supabase_url="https://example.test",
        supabase_service_role_key=FAKE_SERVICE_ROLE_KEY,
        groq_api_key=FAKE_GROQ_KEY,
        nvidia_api_key=FAKE_NVIDIA_KEY,
    )


@pytest.mark.parametrize("secret", API_SECRETS)
def test_api_settings_repr_and_str_hide_secret(secret):
    settings = _api_settings()

    assert secret not in repr(settings)
    assert secret not in str(settings)


@pytest.mark.parametrize("secret", PLATFORM_SECRETS)
def test_platform_settings_repr_and_str_hide_secret(secret):
    settings = _platform_settings()

    assert secret not in repr(settings)
    assert secret not in str(settings)


def test_api_settings_values_are_still_usable():
    settings = _api_settings()

    assert settings.database_url == FAKE_DATABASE_URL
    assert settings.supabase_service_role_key == FAKE_SERVICE_ROLE_KEY
    assert settings.supabase_anon_key == FAKE_ANON_KEY
    assert settings.groq_api_key == FAKE_GROQ_KEY
    assert settings.nvidia_api_key == FAKE_NVIDIA_KEY
    assert settings.analyst_database_url == FAKE_ANALYST_URL


def test_platform_settings_values_are_still_usable_and_validate():
    settings = _platform_settings()

    assert settings.database_url == FAKE_DATABASE_URL
    assert settings.supabase_service_role_key == FAKE_SERVICE_ROLE_KEY
    assert settings.groq_api_key == FAKE_GROQ_KEY
    settings.validate_database()
    settings.validate_ai()


def test_non_secret_fields_remain_visible_in_repr():
    api_repr = repr(_api_settings())
    platform_repr = repr(_platform_settings())

    for text in (api_repr, platform_repr):
        assert "embedding_provider='ollama'" in text
        assert "groq_model='openai/gpt-oss-20b'" in text
        assert "supabase_url='https://example.test'" in text


def test_from_env_settings_repr_hides_all_secrets(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", FAKE_DATABASE_URL)
    monkeypatch.setenv("ANALYST_DATABASE_URL", FAKE_ANALYST_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SERVICE_ROLE_KEY)
    monkeypatch.setenv("SUPABASE_ANON_KEY", FAKE_ANON_KEY)
    monkeypatch.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    monkeypatch.setenv("NVIDIA_API_KEY", FAKE_NVIDIA_KEY)

    settings = APISettings.from_env()

    assert settings.database_url == FAKE_DATABASE_URL
    for secret in API_SECRETS:
        assert secret not in repr(settings)
        assert secret not in str(settings)