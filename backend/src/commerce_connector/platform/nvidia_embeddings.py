from __future__ import annotations

import math
import time
from typing import Any

import httpx

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"

# Project task names -> NVIDIA `input_type` values.
_INPUT_TYPES = {"query": "query", "document": "passage"}
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class NvidiaEmbeddingError(RuntimeError):
    """NVIDIA embedding request failed (message never contains the API key)."""


class NvidiaEmbeddingClient:
    """Small httpx client for NVIDIA's OpenAI-compatible /embeddings endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_NVIDIA_EMBEDDING_MODEL,
        base_url: str = DEFAULT_NVIDIA_BASE_URL,
        dimensions: int = 768,
        timeout: float = 60.0,
        max_attempts: int = 4,
        use_system_proxy: bool = False,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip() or DEFAULT_NVIDIA_EMBEDDING_MODEL
        self.base_url = base_url.strip().rstrip("/") or DEFAULT_NVIDIA_BASE_URL
        self.dimensions = dimensions
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.use_system_proxy = use_system_proxy

        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is required when EMBEDDING_PROVIDER=nvidia.")
        if self.dimensions <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be a positive integer.")

    @staticmethod
    def _delay(response: httpx.Response | None, attempt: int) -> float:
        retry_after = response.headers.get("retry-after") if response is not None else None
        try:
            if retry_after:
                return min(float(retry_after), 30.0)
        except (TypeError, ValueError):
            pass
        return min(float(2**attempt), 20.0)

    def embed(self, text: str, *, task: str) -> list[float]:
        input_type = _INPUT_TYPES.get(task)
        if input_type is None:
            raise ValueError("Embedding task must be 'query' or 'document'.")
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text.")

        payload: dict[str, Any] = {
            "model": self.model,
            "input": [text],
            "encoding_format": "float",
            "dimensions": self.dimensions,
            "input_type": input_type,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response: httpx.Response | None = None
        for attempt in range(self.max_attempts):
            last_attempt = attempt == self.max_attempts - 1
            try:
                response = httpx.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    trust_env=self.use_system_proxy,
                )
            except (httpx.TimeoutException, httpx.NetworkError, OSError) as exc:
                if not last_attempt:
                    time.sleep(self._delay(None, attempt))
                    continue
                raise NvidiaEmbeddingError(
                    f"Could not reach the NVIDIA embedding API ({type(exc).__name__})."
                ) from None

            if response.status_code in _TRANSIENT_STATUS and not last_attempt:
                time.sleep(self._delay(response, attempt))
                continue
            break

        assert response is not None
        if response.status_code >= 300:
            raise NvidiaEmbeddingError(
                f"NVIDIA embedding API returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> list[float]:
        try:
            data = response.json()
        except ValueError as exc:
            raise NvidiaEmbeddingError(
                f"NVIDIA embedding API returned invalid JSON: {response.text[:500]}"
            ) from exc

        items = data.get("data") if isinstance(data, dict) else None
        if (
            not isinstance(items, list)
            or not items
            or not isinstance(items[0], dict)
            or not isinstance(items[0].get("embedding"), list)
        ):
            raise NvidiaEmbeddingError("Unexpected NVIDIA embedding response shape.")

        values = items[0]["embedding"]
        if len(values) != self.dimensions:
            raise NvidiaEmbeddingError(
                f"NVIDIA embedding dimension mismatch: got {len(values)}, "
                f"expected {self.dimensions}."
            )
        try:
            vector = [float(v) for v in values]
            if not all(math.isfinite(v) for v in vector):
                raise NvidiaEmbeddingError(
                    "NVIDIA embedding response contained NaN or infinite values."
                )
            return vector
        except (TypeError, ValueError) as exc:
            raise NvidiaEmbeddingError(
                "NVIDIA embedding response contained non-numeric values."
            ) from exc