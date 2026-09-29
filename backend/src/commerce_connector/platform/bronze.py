from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any

from commerce_connector.core.models import ConnectorPage
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.storage import SupabaseStorageClient


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_record_id(record: Any) -> str | None:
    if not isinstance(record, dict):
        return None
    for key in (
        "id", "ID", "Id", "AmazonOrderId", "order_id", "orderId", "sku", "SKU",
        "entity_id", "customer_id", "product_id",
    ):
        value = record.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def _source_updated_at(record: Any) -> Any | None:
    if not isinstance(record, dict):
        return None
    for key in (
        "updatedAt", "updated_at", "date_modified_gmt", "date_modified", "LastUpdateDate",
        "last_updated_at", "modified_at",
    ):
        if record.get(key):
            return record[key]
    return None


class BronzeWriter:
    def __init__(self, db: PostgresGateway, storage: SupabaseStorageClient | None, bucket: str = "commerce-bronze"):
        self.db = db
        self.storage = storage
        self.bucket = bucket

    async def write_page(
        self,
        *,
        tenant_id: str,
        job_id: str,
        run_id: str,
        connection_id: str,
        resource_key: str,
        page: ConnectorPage,
    ) -> dict[str, Any]:
        raw_object_id = None
        object_path = (
            f"tenant={tenant_id}/connection={connection_id}/resource={resource_key}/"
            f"job={job_id}/run={run_id}/page={page.page_number:06d}.json.gz"
        )

        if self.storage is not None:
            stored = await self.storage.upload_json_gzip(object_path, page.response.data)
            raw_object = await asyncio.to_thread(
                self.db.insert_raw_object,
                tenant_id=tenant_id,
                job_id=job_id,
                run_id=run_id,
                connection_id=connection_id,
                resource_key=resource_key,
                object_path=stored.path,
                content_type=stored.content_type,
                content_encoding=stored.content_encoding,
                compression=stored.compression,
                checksum_sha256=stored.checksum_sha256,
                byte_size=stored.byte_size,
                record_count=page.record_count or 0,
                page_number=page.page_number,
                source_cursor=json.dumps(page.checkpoint, default=str) if page.checkpoint else None,
                source_metadata={"http_status": page.response.status_code, "url": page.response.url},
                bucket_id=self.bucket,
            )
            raw_object_id = raw_object["id"]

        await asyncio.to_thread(
            self.db.insert_extraction_page,
            tenant_id=tenant_id,
            run_id=run_id,
            connection_id=connection_id,
            resource_key=resource_key,
            page_number=page.page_number,
            raw_object_id=raw_object_id,
            record_count=page.record_count or 0,
            http_status=page.response.status_code,
            cursor_out=json.dumps(page.checkpoint, default=str) if page.checkpoint else None,
            response_metadata={"url": page.response.url},
        )

        records = page.records if isinstance(page.records, list) else ([] if page.records is None else [page.records])
        inserted: list[dict[str, Any]] = []
        for record in records:
            record_hash = _stable_hash(record)
            bronze_id = await asyncio.to_thread(
                self.db.insert_bronze_record,
                tenant_id=tenant_id,
                job_id=job_id,
                run_id=run_id,
                connection_id=connection_id,
                resource_key=resource_key,
                source_record_id=_source_record_id(record),
                source_updated_at=_source_updated_at(record),
                record_hash=record_hash,
                payload=record,
                raw_object_id=raw_object_id,
            )
            inserted.append({"bronze_id": bronze_id, "record": record, "record_hash": record_hash})
        return {"raw_object_id": raw_object_id, "records": inserted}
