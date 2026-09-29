from __future__ import annotations

from typing import Any, Protocol


class LLMClient(Protocol):
    """Provider-neutral contract used by the AI analyst and RAG layer."""

    model: str
    embedding_model: str
    embedding_dimensions: int
    embedding_provider: str
    ollama_embedding_model: str

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        reasoning_effort: str | None = None,
    ) -> str: ...

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        schema_name: str | None = None,
        schema: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]: ...

    def embed(
        self,
        text: str,
        *,
        task: str = "query",
        title: str | None = None,
    ) -> list[float]: ...
