from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlatformSettings:
    """Runtime settings entered by an operator/user.

    Secrets are intentionally kept in memory only. The application never writes
    these values to source files.
    """

    database_url: str
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    bronze_bucket: str = "commerce-bronze"
    user_files_bucket: str = "commerce-files"
    max_user_file_bytes: int = 20 * 1024 * 1024
    max_concurrent_connections: int = 5
    max_pages_per_resource: int | None = None

    def validate_database(self) -> None:
        if not self.database_url.strip():
            raise ValueError("Supabase/Postgres database URL is required.")

    def validate_storage(self) -> None:
        if not self.supabase_url.strip() or not self.supabase_service_role_key.strip():
            raise ValueError("Supabase URL and service-role key are required for Bronze object storage.")

    def validate_ai(self) -> None:
        if not self.gemini_api_key.strip():
            raise ValueError("Gemini API key is required for RAG / AI Analyst.")
