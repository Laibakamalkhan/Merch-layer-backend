from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(slots=True)
class UserStoredFile:
    path: str
    byte_size: int
    sha256: str
    content_type: str


class UserFileStorage:
    """Private Supabase Storage bucket for user-uploaded context files."""

    def __init__(self, supabase_url: str, service_role_key: str, bucket: str = "commerce-files"):
        self.base = supabase_url.rstrip("/")
        self.key = service_role_key.strip()
        self.bucket = bucket
        if not self.base or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for file storage")

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.key}", "apikey": self.key}

    async def ensure_bucket(self) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base}/storage/v1/bucket/{self.bucket}", headers=self.headers)
            if response.status_code == 200:
                return
            if response.status_code != 404:
                raise RuntimeError(f"Supabase bucket lookup failed ({response.status_code}): {response.text[:500]}")
            create = await client.post(
                f"{self.base}/storage/v1/bucket",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"id": self.bucket, "name": self.bucket, "public": False},
            )
            if create.status_code >= 300 and create.status_code != 409:
                raise RuntimeError(f"Supabase bucket creation failed ({create.status_code}): {create.text[:500]}")

    async def upload(self, path: str, data: bytes, content_type: str) -> UserStoredFile:
        await self.ensure_bucket()
        encoded = quote(path, safe="/")
        headers = {**self.headers, "Content-Type": content_type or "application/octet-stream", "x-upsert": "true"}
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(f"{self.base}/storage/v1/object/{self.bucket}/{encoded}", headers=headers, content=data)
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase file upload failed ({response.status_code}): {response.text[:500]}")
        return UserStoredFile(path=path, byte_size=len(data), sha256=hashlib.sha256(data).hexdigest(), content_type=content_type or "application/octet-stream")

    async def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        await self.ensure_bucket()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(
                f"{self.base}/storage/v1/object/{self.bucket}",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"prefixes": paths},
            )
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase file delete failed ({response.status_code}): {response.text[:500]}")

    async def download(self, path: str) -> bytes:
        await self.ensure_bucket()
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(f"{self.base}/storage/v1/object/{self.bucket}/{encoded}", headers=self.headers)
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase file download failed ({response.status_code}): {response.text[:500]}")
        return response.content


def extract_indexable_text(filename: str, content_type: str, data: bytes, *, max_chars: int = 200_000) -> tuple[str, str]:
    """Return (text, index_status). Unsupported files remain uploadable but are not indexed."""
    lower = filename.lower()
    mime = (content_type or "").lower()

    if lower.endswith((".txt", ".md", ".log", ".sql", ".py", ".js", ".ts", ".html", ".css")) or mime.startswith("text/"):
        return data.decode("utf-8", errors="replace")[:max_chars], "ready"

    if lower.endswith(".json") or mime == "application/json":
        try:
            parsed = json.loads(data.decode("utf-8", errors="replace"))
            return json.dumps(parsed, ensure_ascii=False, indent=2)[:max_chars], "ready"
        except Exception:
            return data.decode("utf-8", errors="replace")[:max_chars], "ready"

    if lower.endswith(".csv") or mime in {"text/csv", "application/csv"}:
        text = data.decode("utf-8", errors="replace")
        try:
            reader = csv.reader(io.StringIO(text))
            lines = [" | ".join(row) for _, row in zip(range(5000), reader)]
            return "\n".join(lines)[:max_chars], "ready"
        except Exception:
            return text[:max_chars], "ready"

    if lower.endswith(".pdf") or mime == "application/pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            return text[:max_chars], "ready" if text.strip() else "stored_only"
        except Exception:
            return "", "stored_only"

    return "", "stored_only"
