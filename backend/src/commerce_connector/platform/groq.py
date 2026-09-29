from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx


class GroqTransportError(RuntimeError):
    """Groq request could not establish/maintain an HTTP connection."""


class GroqAPIError(RuntimeError):
    """Groq returned a valid HTTP error response."""

    def __init__(self, status_code: int, body: str | bytes):
        self.status_code = status_code
        self.body = (
            body.decode("utf-8", errors="replace")
            if isinstance(body, bytes)
            else str(body)
        )
        super().__init__(
            f"Groq API returned HTTP {status_code}: {self.body[:1200]}"
        )


class GroqClient:
    """Groq generation client with the existing Ollama embedding backend."""

    API_ROOT = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "openai/gpt-oss-20b",
        embedding_dimensions: int = 768,
        embedding_provider: str = "ollama",
        ollama_base_url: str = "http://localhost:11434",
        ollama_embedding_model: str = "embeddinggemma:latest",
        use_system_proxy: bool = False,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.embedding_model = ""
        self.embedding_dimensions = embedding_dimensions
        self.embedding_provider = (
            embedding_provider.strip().lower() or "ollama"
        )
        self.ollama_base_url = (
            ollama_base_url.strip().rstrip("/")
            or "http://localhost:11434"
        )
        self.ollama_embedding_model = (
            ollama_embedding_model.strip()
            or "embeddinggemma:latest"
        )
        self.use_system_proxy = use_system_proxy

        if not self.api_key:
            raise ValueError(
                "Groq API key is required for AI Analyst text generation."
            )

        if not self.model:
            raise ValueError("GROQ_MODEL must not be empty.")

        if self.embedding_provider != "ollama":
            raise ValueError(
                "Groq generation is separate from embeddings. "
                "EMBEDDING_PROVIDER must remain 'ollama' for the existing RAG index."
            )

    @staticmethod
    def _retry_delay(
        response: httpx.Response | None,
        attempt: int,
    ) -> float:
        retry_after = (
            response.headers.get("retry-after")
            if response is not None
            else None
        )

        try:
            return (
                min(float(retry_after), 30.0)
                if retry_after
                else min(float(2**attempt), 30.0)
            )
        except (TypeError, ValueError):
            return min(float(2**attempt), 30.0)

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        url = f"{self.API_ROOT}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "shopify-ai-analytics-platform/1.0",
        }

        transient = {429, 500, 502, 503, 504}
        max_attempts = 5

        for attempt in range(max_attempts):
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=90,
                    trust_env=self.use_system_proxy,
                )

            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
                OSError,
            ) as exc:
                if attempt < max_attempts - 1:
                    delay = min(2**attempt, 30)
                    time.sleep(delay)
                    continue

                raise GroqTransportError(
                    f"Groq HTTP transport failed after "
                    f"{max_attempts} attempts "
                    f"({type(exc).__name__}: {exc}). "
                    "Check internet, TLS, firewall or proxy settings."
                ) from None

            if (
                response.status_code not in transient
                or attempt >= max_attempts - 1
            ):
                return response

            time.sleep(
                self._retry_delay(
                    response,
                    attempt,
                )
            )

        raise GroqTransportError(
            "Groq request failed after retries."
        )

    @staticmethod
    def _messages(
        prompt: str,
        system: str | None,
    ) -> list[dict[str, str]]:
        """
        GPT-OSS works more reliably when the complete instruction is
        supplied in the user message.

        We preserve the existing system prompt semantics by combining it
        with the user prompt into one explicit instruction message.
        """

        if system:
            content = (
                "SYSTEM INSTRUCTIONS:\n"
                f"{system}\n\n"
                "USER REQUEST:\n"
                f"{prompt}"
            )
        else:
            content = prompt

        return [
            {
                "role": "user",
                "content": content,
            }
        ]

    @staticmethod
    def _content(response: httpx.Response) -> str:
        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "Groq returned invalid JSON response: "
                f"{response.text[:1000]}"
            ) from exc

        try:
            content = data["choices"][0]["message"]["content"]

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise RuntimeError(
                f"Unexpected Groq response: {data}"
            ) from exc

        if not isinstance(content, str):
            raise RuntimeError(
                "Groq returned non-text content: "
                f"{type(content).__name__}"
            )

        return content.strip()

    @staticmethod
    def _is_json_validation_error(
        response: httpx.Response,
    ) -> bool:
        if response.status_code != 400:
            return False

        try:
            data = response.json()
        except ValueError:
            return False

        error = data.get("error")

        if not isinstance(error, dict):
            return False

        return (
            error.get("code") == "json_validate_failed"
            or "json_validate_failed"
            in str(error.get("message") or "")
        )

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        reasoning_effort: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(
                prompt,
                system,
            ),
            "temperature": temperature,
        }

        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        response = self._post(payload)

        if response.status_code >= 300:
            raise GroqAPIError(
                response.status_code,
                response.text,
            )

        return self._content(response)

    def _generate_json_strict(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        schema_name: str | None,
        schema: dict[str, Any],
        reasoning_effort: str | None,
    ) -> httpx.Response:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(
                prompt,
                system,
            ),
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name or "structured_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        }

        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        return self._post(payload)

    def _generate_json_object(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        reasoning_effort: str | None,
    ) -> httpx.Response:
        """
        Fallback for Groq JSON-schema validation failures.

        JSON Object Mode guarantees valid JSON, while the application-level
        planner/SQLGuard remains responsible for validating what the model
        actually requested.
        """

        object_prompt = (
            f"{prompt}\n\n"
            "FINAL OUTPUT REQUIREMENT:\n"
            "Return exactly one valid JSON object.\n"
            "Do not return markdown.\n"
            "Do not return ``` fences.\n"
            "Do not return commentary before or after the JSON.\n"
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(
                object_prompt,
                system,
            ),
            "temperature": temperature,
            "response_format": {
                "type": "json_object",
            },
        }

        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        return self._post(payload)

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        schema_name: str | None = None,
        schema: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        if schema is None:
            raise ValueError(
                "A JSON schema is required for structured LLM output."
            )

        response = self._generate_json_strict(
            prompt,
            system=system,
            temperature=temperature,
            schema_name=schema_name,
            schema=schema,
            reasoning_effort=reasoning_effort,
        )

        if response.status_code < 300:
            text = self._content(response)

            try:
                result = json.loads(text)

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Groq returned invalid structured JSON: "
                    f"{text[:1000]}"
                ) from exc

            if not isinstance(result, dict):
                raise RuntimeError(
                    "Groq structured JSON is not an object: "
                    f"{type(result).__name__}"
                )

            return result

        # Groq's GPT-OSS structured-output endpoint can occasionally reject
        # an otherwise valid request with json_validate_failed.
        #
        # Retry only this specific error using JSON Object Mode.
        # All other API errors remain unchanged.
        if self._is_json_validation_error(response):
            fallback_response = self._generate_json_object(
                prompt,
                system=system,
                temperature=temperature,
                reasoning_effort="low",
            )

            if fallback_response.status_code >= 300:
                raise GroqAPIError(
                    fallback_response.status_code,
                    fallback_response.text,
                )

            text = self._content(fallback_response)

            try:
                result = json.loads(text)

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Groq JSON Object Mode returned invalid JSON: "
                    f"{text[:1000]}"
                ) from exc

            if not isinstance(result, dict):
                raise RuntimeError(
                    "Groq JSON Object Mode returned a non-object: "
                    f"{type(result).__name__}"
                )

            return result

        raise GroqAPIError(
            response.status_code,
            response.text,
        )

    def _embed_ollama(
        self,
        text: str,
        *,
        task: str,
        title: str | None,
    ) -> list[float]:
        prompt = (
            f"title: {title or 'none'} | text: {text}"
            if task == "document"
            else f"task: search result | query: {text}"
        )

        try:
            response = httpx.post(
                f"{self.ollama_base_url}/api/embed",
                json={
                    "model": self.ollama_embedding_model,
                    "input": prompt,
                },
                timeout=90,
                trust_env=False,
            )

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
        ):
            raise RuntimeError(
                "Ollama embedding server tak connect nahi ho saka. "
                "Check karein ke Ollama chal raha hai aur "
                "http://localhost:11434 available hai."
            ) from None

        if response.status_code >= 300:
            raise RuntimeError(
                "Ollama embedding failed "
                f"({response.status_code}): "
                f"{response.text[:800]}"
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON: "
                f"{response.text[:1000]}"
            ) from exc

        embeddings = data.get("embeddings")

        if (
            not isinstance(embeddings, list)
            or not embeddings
            or not isinstance(embeddings[0], list)
        ):
            raise RuntimeError(
                f"Unexpected Ollama embedding response: {data}"
            )

        values = embeddings[0]

        if len(values) != self.embedding_dimensions:
            raise RuntimeError(
                "Ollama embedding dimension mismatch: "
                f"got {len(values)}, "
                f"expected {self.embedding_dimensions}."
            )

        try:
            return [
                float(value)
                for value in values
            ]

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Ollama embedding response contained "
                "non-numeric values."
            ) from exc

    def embed(
        self,
        text: str,
        *,
        task: str = "query",
        title: str | None = None,
    ) -> list[float]:
        if task not in {
            "query",
            "document",
        }:
            raise ValueError(
                "Embedding task must be 'query' or 'document'."
            )

        return self._embed_ollama(
            text,
            task=task,
            title=title,
        )