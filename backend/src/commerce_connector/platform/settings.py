from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PlatformSettings:
    """Runtime settings entered by an operator/user.

    Secrets are intentionally kept in memory only. The application never writes
    these values to source files.
    """

    database_url: str = field(repr=False)
    supabase_url: str = ""
    supabase_service_role_key: str = field(default="", repr=False)
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
    max_concurrent_connections: int = 5
    max_pages_per_resource: int | None = None

    def validate_database(self) -> None:
        if not self.database_url.strip():
            raise ValueError("Supabase/Postgres database URL is required.")

    def validate_storage(self) -> None:
        if not self.supabase_url.strip() or not self.supabase_service_role_key.strip():
            raise ValueError("Supabase URL and service-role key are required for Bronze object storage.")

    def validate_ai(self) -> None:
        if self.llm_provider != "groq":
            raise ValueError("LLM_PROVIDER must currently be 'groq'.")
        if not self.groq_api_key.strip():
            raise ValueError("Groq API key is required for AI Analyst text generation.")
        if self.embedding_provider not in {"ollama", "nvidia"}:
            raise ValueError("EMBEDDING_PROVIDER must be 'nvidia' or 'ollama'.")
        if self.embedding_provider == "nvidia" and not self.nvidia_api_key.strip():
            raise ValueError("NVIDIA_API_KEY is required when EMBEDDING_PROVIDER=nvidia.")