from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# FIX #1: the backend never read backend/.env. Load it here (backend/.env),
# real environment variables (production) still win because override=False.
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

DEFAULT_CORS = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000")


@dataclass(frozen=True, slots=True)
class APISettings:
    database_url: str = field(default="", repr=False)
    supabase_url: str = ""
    supabase_service_role_key: str = field(default="", repr=False)
    supabase_anon_key: str = field(default="", repr=False)
    llm_provider: str = "groq"
    groq_api_key: str = field(default="", repr=False)
    groq_model: str = "openai/gpt-oss-20b"
    groq_use_system_proxy: bool = False
    embedding_dimensions: int = 768
    embedding_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_embedding_model: str = "embeddinggemma:latest"
    nvidia_api_key: str = field(default="", repr=False)
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2"
    bronze_bucket: str = "commerce-bronze"
    user_files_bucket: str = "commerce-files"
    max_user_file_bytes: int = 20 * 1024 * 1024
    free_store_limit: int = 1
    free_ai_query_limit_monthly: int = 100
    allow_direct_plan_change: bool = False
    billing_checkout_url: str = ""
    max_concurrent_connections: int = 5
    max_pages_per_resource: int | None = None
    cors_origins: tuple[str, ...] = DEFAULT_CORS
    # FIX #2: email confirmation link ab yahan redirect karega (pehle Supabase ka default Site URL = localhost:3000 use hota tha)
    frontend_url: str = "http://localhost:5173"
    app_env: str = "production"
    debug_user_ids: tuple[str, ...] = ()
    analyst_database_url: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "APISettings":
        raw_pages = os.getenv("MAX_PAGES_PER_RESOURCE", "").strip()
        raw_origins = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS))
        origins = tuple(x.strip() for x in raw_origins.split(",") if x.strip())
        raw_env = os.getenv("APP_ENV", "production").strip().lower()
        if raw_env not in {"development", "staging", "production"}:
            raw_env = "production"
        raw_debug_users = os.getenv("DEBUG_USER_IDS", "").strip()
        debug_users = tuple(x.strip() for x in raw_debug_users.split(",") if x.strip())
        return cls(
            database_url=(os.getenv("DATABASE_URL", "") or os.getenv("SUPABASE_DATABASE_URL", "")).strip(),
            supabase_url=os.getenv("SUPABASE_URL", "").strip(),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", "").strip(),
            llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower(),
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(),
            groq_use_system_proxy=os.getenv("GROQ_USE_SYSTEM_PROXY", "false").strip().lower() in {"1", "true", "yes", "on"},
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower(),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/"),
            ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma:latest").strip(),
            nvidia_api_key=os.getenv("NVIDIA_API_KEY", "").strip(),
            nvidia_base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip().rstrip("/"),
            nvidia_embedding_model=os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-vl-1b-v2").strip(),
            bronze_bucket=os.getenv("BRONZE_BUCKET", "commerce-bronze").strip(),
            user_files_bucket=os.getenv("USER_FILES_BUCKET", "commerce-files").strip(),
            max_user_file_bytes=int(os.getenv("MAX_USER_FILE_BYTES", str(20 * 1024 * 1024))),
            free_store_limit=int(os.getenv("FREE_STORE_LIMIT", "1")),
            free_ai_query_limit_monthly=int(os.getenv("FREE_AI_QUERY_LIMIT_MONTHLY", "100")),
            allow_direct_plan_change=os.getenv("ALLOW_DIRECT_PLAN_CHANGE", "false").strip().lower() in {"1","true","yes","on"},
            billing_checkout_url=os.getenv("BILLING_CHECKOUT_URL", "").strip(),
            max_concurrent_connections=int(os.getenv("MAX_CONCURRENT_CONNECTIONS", "5")),
            max_pages_per_resource=int(raw_pages) if raw_pages else None,
            cors_origins=origins or DEFAULT_CORS,
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/"),
            app_env=raw_env,
            debug_user_ids=debug_users,
            analyst_database_url=os.getenv("ANALYST_DATABASE_URL", "").strip(),
        )
