from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# FIX #1: the backend never read backend/.env. Load it here (backend/.env),
# real environment variables (production) still win because override=False.
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

DEFAULT_CORS = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000")


@dataclass(frozen=True, slots=True)
class APISettings:
    database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
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

    @classmethod
    def from_env(cls) -> "APISettings":
        raw_pages = os.getenv("MAX_PAGES_PER_RESOURCE", "").strip()
        raw_origins = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS))
        origins = tuple(x.strip() for x in raw_origins.split(",") if x.strip())
        return cls(
            database_url=(os.getenv("DATABASE_URL", "") or os.getenv("SUPABASE_DATABASE_URL", "")).strip(),
            supabase_url=os.getenv("SUPABASE_URL", "").strip(),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", "").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
            gemini_embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip(),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
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
        )
