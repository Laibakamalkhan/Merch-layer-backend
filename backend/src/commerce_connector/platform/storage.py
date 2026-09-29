from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(slots=True)
class StoredObject:
    path: str
    checksum_sha256: str
    byte_size: int
    content_type: str = "application/json"
    content_encoding: str | None = "gzip"
    compression: str | None = "gzip"


class SupabaseStorageClient:
    def __init__(self, supabase_url: str, service_role_key: str, bucket: str = "commerce-bronze"):
        self.supabase_url = supabase_url.rstrip("/")
        self.key = service_role_key
        self.bucket = bucket

    async def upload_json_gzip(self, path: str, payload: Any) -> StoredObject:
        if not self.supabase_url or not self.key:
            raise ValueError("Supabase URL/service-role key are required for object storage")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        body = gzip.compress(raw, compresslevel=6)
        checksum = hashlib.sha256(body).hexdigest()
        encoded_path = quote(path, safe="/")
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{encoded_path}"
        headers = {
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "x-upsert": "true",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, content=body)
            if response.status_code >= 300:
                raise RuntimeError(f"Supabase Storage upload failed ({response.status_code}): {response.text[:500]}")
        return StoredObject(path=path, checksum_sha256=checksum, byte_size=len(body))
