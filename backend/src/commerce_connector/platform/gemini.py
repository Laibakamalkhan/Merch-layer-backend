from __future__ import annotations

import json
import os
from typing import Any

import httpx


class GeminiClient:
    """Minimal Gemini REST client to keep the prototype dependency-light."""

    API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.8-flash",
        embedding_model: str = "gemini-embedding-001",
        embedding_dimensions: int = 768,
    ):
        self.api_key = api_key
        self.model = model.replace("models/", "")
        self.embedding_model = embedding_model.replace("models/", "")
        self.embedding_dimensions = embedding_dimensions

    def _url(self, model: str, action: str) -> str:
        return f"{self.API_ROOT}/models/{model}:{action}?key={self.api_key}"

    def _post(self, url: str, payload: dict[str, Any]) -> httpx.Response:
        """
        Send a Gemini REST request without inheriting system proxy settings.

        trust_env=False is intentional because the local environment was
        causing TLS/SSL EOF errors when httpx inherited proxy variables.
        """
        # Agar aap ke internet ke liye VPN/proxy zaroori hai to .env mein GEMINI_USE_SYSTEM_PROXY=true kar dein.
        use_system_proxy = os.getenv("GEMINI_USE_SYSTEM_PROXY", "").strip().lower() in {"1", "true", "yes", "on"}
        try:
            return httpx.post(
                url,
                json=payload,
                timeout=90,
                trust_env=use_system_proxy,
            )
        except httpx.ConnectError as exc:
            # URL mein API key hoti hai, isliye error text mein URL nahi dikhate.
            raise RuntimeError(
                "Gemini server (generativelanguage.googleapis.com) tak connect nahi ho saka "
                f"({type(exc).__name__}). Internet/VPN/firewall check karein, ya .env mein GEMINI_USE_SYSTEM_PROXY=true try karein."
            ) from None
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Gemini ne waqt par jawab nahi diya ({type(exc).__name__}). Dobara try karein.") from None

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> str:
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
                "parts": [{"text": system}],
            }

        response = self._post(
            self._url(self.model, "generateContent"),
            payload,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                "Gemini generateContent failed "
                f"({response.status_code}): {response.text[:800]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Gemini returned invalid JSON response: {response.text[:1000]}"
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
                "parts": [{"text": system}],
            }

        response = self._post(
            self._url(self.model, "generateContent"),
            payload,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                "Gemini JSON generation failed "
                f"({response.status_code}): {response.text[:800]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Gemini returned invalid JSON response: {response.text[:1000]}"
            ) from exc

        text = "".join(
            part.get("text", "")
            for part in data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        ).strip()

        # Gemini kabhi kabhi JSON ko markdown code fence mein return kar sakta hai.
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gemini did not return valid JSON: {text[:1000]}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                f"Gemini JSON response is not an object: {type(result).__name__}"
            )

        return result

    def embed(self, text: str) -> list[float]:
        model_name = f"models/{self.embedding_model}"

        payload: dict[str, Any] = {
            "model": model_name,
            "content": {
                "parts": [{"text": text}],
            },
            "outputDimensionality": self.embedding_dimensions,
        }

        response = self._post(
            self._url(self.embedding_model, "embedContent"),
            payload,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                "Gemini embedding failed "
                f"({response.status_code}): {response.text[:800]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Gemini returned invalid embedding response: "
                f"{response.text[:1000]}"
            ) from exc

        values = data.get("embedding", {}).get("values")

        if not isinstance(values, list):
            raise RuntimeError(
                f"Unexpected embedding response: {data}"
            )

        if len(values) != self.embedding_dimensions:
            raise RuntimeError(
                f"Embedding dimension mismatch: got {len(values)}, "
                f"expected {self.embedding_dimensions}. "
                "Use an embedding model/API configuration that supports "
                "the database vector dimension."
            )

        try:
            return [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Gemini embedding response contained non-numeric values."
            ) from exc