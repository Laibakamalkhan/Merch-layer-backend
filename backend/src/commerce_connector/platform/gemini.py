import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Any

import httpx


class _GeminiResponse:
    """Small response wrapper compatible with the existing Gemini code."""

    def __init__(self, status_code: int, body: bytes, headers: Any):
        self.status_code = status_code
        self._body = body
        self.headers = headers

    @property
    def text(self) -> str:
        return self._body.decode("utf-8", errors="replace")

    def json(self) -> dict[str, Any]:
        return json.loads(self.text)


class GeminiClient:
    """Gemini text-generation client plus configurable local/API embeddings."""

    API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.8-flash",
        embedding_model: str = "gemini-embedding-001",
        embedding_dimensions: int = 768,
        embedding_provider: str = "ollama",
        ollama_base_url: str = "http://localhost:11434",
        ollama_embedding_model: str = "embeddinggemma:latest",
    ):
        self.api_key = api_key
        self.model = model.replace("models/", "")
        self.embedding_model = embedding_model.replace("models/", "")
        self.embedding_dimensions = embedding_dimensions
        self.embedding_provider = embedding_provider.strip().lower() or "ollama"
        self.ollama_base_url = (
            ollama_base_url.strip().rstrip("/") or "http://localhost:11434"
        )
        self.ollama_embedding_model = (
            ollama_embedding_model.strip() or "embeddinggemma:latest"
        )

        if self.embedding_provider not in {"ollama", "gemini"}:
            raise ValueError(
                "EMBEDDING_PROVIDER must be 'ollama' or 'gemini'."
            )

    def _url(self, model: str, action: str) -> str:
        return f"{self.API_ROOT}/models/{model}:{action}?key={self.api_key}"

    def _post(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> _GeminiResponse:
        """
        POST to Gemini using Python's native HTTPS stack.

        Retries transient network failures and temporary Gemini
        server/rate-limit responses.
        """

        use_system_proxy = os.getenv(
            "GEMINI_USE_SYSTEM_PROXY",
            "",
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        request_body = json.dumps(payload).encode("utf-8")
        ssl_context = ssl.create_default_context()

        if use_system_proxy:
            # Allow urllib to use environment/system-configured proxy settings.
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ssl_context)
            )
        else:
            # Direct connection: disable proxy autodetection.
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl_context),
            )

        max_attempts = 6

        # These are transient Gemini/API responses and should be retried.
        transient_statuses = {
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        }

        last_error: Exception | None = None

        for attempt in range(max_attempts):
            # Build a fresh Request on every attempt.
            request = urllib.request.Request(
                url,
                data=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": (
                        "shopify-ai-analytics-platform/1.0"
                    ),
                },
                method="POST",
            )

            try:
                with opener.open(request, timeout=90) as response:
                    body = response.read()

                    return _GeminiResponse(
                        status_code=response.status,
                        body=body,
                        headers=response.headers,
                    )

            except urllib.error.HTTPError as exc:
                body = exc.read()

                # Retry temporary API/server failures.
                if (
                    exc.code in transient_statuses
                    and attempt < max_attempts - 1
                ):
                    retry_after = exc.headers.get("Retry-After")

                    try:
                        delay = (
                            float(retry_after)
                            if retry_after
                            else float(2 ** attempt)
                        )
                    except (TypeError, ValueError):
                        delay = float(2 ** attempt)

                    # Avoid extremely long waits during local development.
                    delay = min(delay, 30.0)

                    print(
                        f"Gemini returned HTTP {exc.code}. "
                        f"Retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_attempts})..."
                    )

                    time.sleep(delay)
                    continue

                # Non-transient errors, or final retry:
                # return response so generate_text/generate_json
                # can produce the existing detailed API error.
                return _GeminiResponse(
                    status_code=exc.code,
                    body=body,
                    headers=exc.headers,
                )

            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
            ) as exc:
                # URLError may wrap TLS failures such as:
                # SSL: UNEXPECTED_EOF_WHILE_READING
                last_error = exc

                if attempt < max_attempts - 1:
                    delay = min(2 ** attempt, 30)

                    print(
                        "Gemini HTTPS connection failed: "
                        f"{type(exc).__name__}. "
                        f"Retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts})..."
                    )

                    time.sleep(delay)
                    continue

                raise RuntimeError(
                    "Gemini server se HTTPS connection establish "
                    "nahi ho saka after multiple retries. "
                    f"Error: {type(exc).__name__}: {exc}"
                ) from None

        raise RuntimeError(
            "Gemini request failed after retries."
        ) from last_error

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> str:
        """Generate normal text from Gemini."""

        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}]
            }

        response = self._post(
            self._url(self.model, "generateContent"),
            payload,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                "Gemini generateContent failed "
                f"({response.status_code}): "
                f"{response.text[:800]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Gemini returned invalid JSON response: "
                f"{response.text[:1000]}"
            ) from exc

        try:
            parts = data["candidates"][0]["content"]["parts"]

            return "".join(
                part.get("text", "")
                for part in parts
            ).strip()

        except Exception as exc:
            raise RuntimeError(
                f"Unexpected Gemini response: {data}"
            ) from exc

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Generate a JSON object from Gemini."""

        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }

        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}]
            }

        response = self._post(
            self._url(self.model, "generateContent"),
            payload,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                "Gemini JSON generation failed "
                f"({response.status_code}): "
                f"{response.text[:800]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Gemini returned invalid JSON response: "
                f"{response.text[:1000]}"
            ) from exc

        text = "".join(
            part.get("text", "")
            for part in data.get(
                "candidates",
                [{}],
            )[0]
            .get("content", {})
            .get("parts", [])
        ).strip()

        # Remove markdown JSON fences if Gemini returns them.
        if text.startswith("```"):
            text = text.strip("`")

            if text.startswith("json"):
                text = text[4:].lstrip()

        try:
            result = json.loads(text)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Gemini did not return valid JSON: "
                f"{text[:1000]}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Gemini JSON response is not an object: "
                f"{type(result).__name__}"
            )

        return result

    def _embed_ollama(
        self,
        text: str,
        *,
        task: str,
        title: str | None,
    ) -> list[float]:
        """Create a local embedding using Ollama."""

        if task == "document":
            prompt = (
                f"title: {title or 'none'} | "
                f"text: {text}"
            )
        else:
            prompt = (
                f"task: search result | "
                f"query: {text}"
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
        ) as exc:
            raise RuntimeError(
                "Ollama embedding server tak connect nahi "
                "ho saka. Check karein ke Ollama chal raha hai "
                "aur http://localhost:11434 available hai."
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
                f"expected {self.embedding_dimensions}. "
                "Database vector dimension aur embedding "
                "model same rakhna zaroori hai."
            )

        try:
            return [
                float(value)
                for value in values
            ]

        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Ollama embedding response contained "
                "non-numeric values."
            ) from exc

    def _embed_gemini(
        self,
        text: str,
        *,
        task: str,
        title: str | None,
    ) -> list[float]:
        """Create a Gemini API embedding."""

        task_type = (
            "RETRIEVAL_DOCUMENT"
            if task == "document"
            else "RETRIEVAL_QUERY"
        )

        payload: dict[str, Any] = {
            "taskType": task_type,
            "content": {
                "parts": [
                    {
                        "text": text
                    }
                ]
            },
            "outputDimensionality": self.embedding_dimensions,
        }

        if task == "document" and title:
            payload["title"] = title

        response = self._post(
            self._url(
                self.embedding_model,
                "embedContent",
            ),
            payload,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                "Gemini embedding failed "
                f"({response.status_code}): "
                f"{response.text[:800]}"
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "Gemini returned invalid embedding response: "
                f"{response.text[:1000]}"
            ) from exc

        values = (
            data
            .get("embedding", {})
            .get("values")
        )

        if not isinstance(values, list):
            raise RuntimeError(
                f"Unexpected embedding response: {data}"
            )

        if len(values) != self.embedding_dimensions:
            raise RuntimeError(
                "Embedding dimension mismatch: "
                f"got {len(values)}, "
                f"expected {self.embedding_dimensions}."
            )

        try:
            return [
                float(value)
                for value in values
            ]

        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Gemini embedding response contained "
                "non-numeric values."
            ) from exc

    def embed(
        self,
        text: str,
        *,
        task: str = "query",
        title: str | None = None,
    ) -> list[float]:
        """Create a retrieval embedding using the configured provider."""

        if task not in {
            "query",
            "document",
        }:
            raise ValueError(
                "Embedding task must be 'query' or 'document'."
            )

        if self.embedding_provider == "ollama":
            return self._embed_ollama(
                text,
                task=task,
                title=title,
            )

        return self._embed_gemini(
            text,
            task=task,
            title=title,
        )