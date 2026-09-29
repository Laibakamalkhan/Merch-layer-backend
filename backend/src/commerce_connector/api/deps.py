from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from commerce_connector.api.config import APISettings


@lru_cache(maxsize=1)
def get_api_settings() -> APISettings:
    return APISettings.from_env()


@lru_cache(maxsize=1)
def get_service() -> Any:
    cfg = get_api_settings()
    # Check configuration BEFORE the heavy imports so a missing DATABASE_URL always
    # gives a clean 503, even if the database driver is not installed.
    if not cfg.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured on the backend.",
        )
    # Lazy imports keep OpenAPI/docs importable before optional DB runtime
    # dependencies/credentials are installed/configured.
    from commerce_connector.platform.service import CommercePlatformService
    from commerce_connector.platform.settings import PlatformSettings

    project_root = Path(__file__).resolve().parents[3]
    settings = PlatformSettings(
        database_url=cfg.database_url,
        supabase_url=cfg.supabase_url,
        supabase_service_role_key=cfg.supabase_service_role_key,
        gemini_api_key=cfg.gemini_api_key,
        gemini_model=cfg.gemini_model,
        gemini_embedding_model=cfg.gemini_embedding_model,
        embedding_dimensions=cfg.embedding_dimensions,
        bronze_bucket=cfg.bronze_bucket,
        user_files_bucket=cfg.user_files_bucket,
        max_user_file_bytes=cfg.max_user_file_bytes,
        max_concurrent_connections=cfg.max_concurrent_connections,
        max_pages_per_resource=cfg.max_pages_per_resource,
    )
    return CommercePlatformService(settings, project_root)


def reset_cached_dependencies() -> None:
    get_service.cache_clear()
    get_api_settings.cache_clear()
