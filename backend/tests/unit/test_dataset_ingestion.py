from __future__ import annotations

import uuid
from typing import Any
import pytest

from commerce_connector.platform.datasets.ingestor import DatasetIngestionOrchestrator


class FakeDB:
    def __init__(self):
        self.datasets: dict[str, dict[str, Any]] = {}
        self.connections: dict[str, dict[str, Any]] = {}
        self.silver_orders: list[dict[str, Any]] = []
        self.gold_daily_sales: list[dict[str, Any]] = []
        self.quality_runs: list[dict[str, Any]] = []

    def get_uploaded_dataset(self, dataset_id: str, tenant_id: str):
        return self.datasets.get(dataset_id)

    def create_job(self, tenant_id, connection_ids, trigger_type="manual"):
        return {"id": str(uuid.uuid4()), "tenant_id": tenant_id}

    def start_job(self, job_id):
        pass

    def create_run(self, tenant_id, job_id, connection_id, resource_key, canonical_resource, sync_mode="incremental"):
        return {"id": str(uuid.uuid4()), "job_id": job_id, "connection_id": connection_id}

    def finish_run(self, run_id, status, records_fetched=0, records_written=0, records_rejected=0, pages_fetched=0, bytes_fetched=0, checkpoint_after=None, error_summary=None):
        pass

    def update_job_connection_status(self, job_id, connection_id, status, error_summary=None):
        pass

    def finalize_job(self, job_id):
        return "completed"

    def record_quality_run(self, tenant_id, sync_run_id, entity_name, input_records, valid_records, rejected_records):
        return {"id": str(uuid.uuid4()), "status": "passed"}

    def create_connection(self, tenant_id, platform_code, name, base_url, config, metadata, enabled_resources):
        cid = str(uuid.uuid4())
        conn = {
            "id": cid,
            "tenant_id": tenant_id,
            "platform_code": platform_code,
            "name": name,
            "base_url": base_url,
            "config": config,
            "metadata": metadata,
            "enabled_resources": enabled_resources,
        }
        self.connections[cid] = conn
        return conn

    def update_dataset_status(self, dataset_id, tenant_id, status, connection_id=None, mapping_config=None, quality_summary=None, row_count=None, error_message=None):
        ds = self.datasets.get(dataset_id, {})
        ds["status"] = status
        if connection_id:
            ds["connection_id"] = connection_id
        if mapping_config:
            ds["mapping_config"] = mapping_config
        if quality_summary:
            ds["quality_summary"] = quality_summary
        if row_count is not None:
            ds["row_count"] = row_count
        if error_message:
            ds["error_message"] = error_message
        self.datasets[dataset_id] = ds
        return ds

    def purge_connection_silver_records(self, connection_id: str):
        self.silver_orders = [o for o in self.silver_orders if o["connection_id"] != connection_id]

    def prune_stale_silver_records(self, table: str, connection_id: str, active_source_ids: list[str]):
        initial_len = len(self.silver_orders)
        self.silver_orders = [
            o for o in self.silver_orders
            if o["connection_id"] != connection_id or o["source_id"] in set(active_source_ids)
        ]
        return initial_len - len(self.silver_orders)

    def upsert_row(self, table: str, row: dict[str, Any], conflict_columns: list[str]):
        if table == "silver.orders":
            # Match on conflict columns
            conn_id = row.get("connection_id")
            src_id = row.get("source_id")
            for idx, existing in enumerate(self.silver_orders):
                if existing.get("connection_id") == conn_id and existing.get("source_id") == src_id:
                    self.silver_orders[idx] = {**existing, **row}
                    return
            self.silver_orders.append(dict(row))


class FakeBronze:
    async def write_page(self, tenant_id, job_id, run_id, connection_id, resource_key, page):
        records = page.records if isinstance(page.records, list) else [page.records]
        inserted = []
        for r in records:
            inserted.append({"bronze_id": str(uuid.uuid4()), "record": r, "record_hash": "hash_123"})
        return {"raw_object_id": str(uuid.uuid4()), "records": inserted}


class FakeSilver:
    def __init__(self, db: FakeDB):
        self.db = db

    async def transform_records(self, tenant_id, connection_id, platform, resource, records):
        written = 0
        for wrapper in records:
            r = wrapper["record"]
            row = {
                "tenant_id": tenant_id,
                "connection_id": connection_id,
                "source_id": r.get("source_id"),
                "gross_amount": float(r.get("gross_amount", 0) or 0),
                "source_created_at": r.get("source_created_at"),
            }
            self.db.upsert_row("silver.orders", row, ["connection_id", "source_id"])
            written += 1
        return {"written": written, "rejected": 0}


class FakeGold:
    def __init__(self, db: FakeDB):
        self.db = db
        self.refresh_calls = []

    def refresh_tenant(self, tenant_id: str):
        self.refresh_calls.append(tenant_id)


@pytest.mark.asyncio
async def test_dataset_ingestion_natural_key_lifecycle():
    db = FakeDB()
    bronze = FakeBronze()
    silver = FakeSilver(db)
    gold = FakeGold(db)
    orchestrator = DatasetIngestionOrchestrator(db=db, bronze=bronze, silver=silver, gold=gold)

    tenant_id = str(uuid.uuid4())
    dataset_id = str(uuid.uuid4())

    # Step 1: Initial upload state
    db.datasets[dataset_id] = {
        "id": dataset_id,
        "tenant_id": tenant_id,
        "filename": "orders.csv",
        "file_type": "csv",
        "storage_path": f"datasets/{tenant_id}/{dataset_id}/orders.csv",
        "status": "profiled",
        "detected_entity": "orders",
        "profile_summary": {
            "available_metrics": ["revenue", "orders_count"],
            "unavailable_metrics": ["profit", "margin"],
            "detected_entity": "orders",
        },
    }

    raw_csv_v1 = b"order_id,amount,date\n1001,50.00,2026-09-01\n1002,75.00,2026-09-02\n1003,100.00,2026-09-03"

    res = await orchestrator.ingest_dataset(
        tenant_id=tenant_id,
        user_id="user_1",
        dataset_id=dataset_id,
        target_entity="orders",
        column_mappings={"order_id": "source_id", "amount": "gross_amount", "date": "source_created_at"},
        natural_key_column="order_id",
        raw_file_bytes=raw_csv_v1,
    )

    assert res["records_written"] == 3
    assert len(db.silver_orders) == 3
    assert len(gold.refresh_calls) == 1
    quality = db.datasets[dataset_id]["quality_summary"]
    assert quality["available_metrics"] == ["revenue", "orders_count"]
    assert "profit" in quality["unavailable_metrics"]
    assert quality["detected_entity"] == "orders"
    conn_id = res["connection_id"]

    # Step 2: Re-upload with modified row 1001, added row 1004, and deleted row 1003
    raw_csv_v2 = b"order_id,amount,date\n1001,55.00,2026-09-01\n1002,75.00,2026-09-02\n1004,200.00,2026-09-04"

    res_v2 = await orchestrator.ingest_dataset(
        tenant_id=tenant_id,
        user_id="user_1",
        dataset_id=dataset_id,
        target_entity="orders",
        column_mappings={"order_id": "source_id", "amount": "gross_amount", "date": "source_created_at"},
        natural_key_column="order_id",
        raw_file_bytes=raw_csv_v2,
    )

    assert res_v2["connection_id"] == conn_id  # Reused same connection
    assert len(db.silver_orders) == 3
    # 1001 was updated to 55.00
    row_1001 = next(r for r in db.silver_orders if r["source_id"] == "1001")
    assert row_1001["gross_amount"] == 55.0
    # 1004 was added
    assert any(r["source_id"] == "1004" for r in db.silver_orders)
    # 1003 was pruned
    assert not any(r["source_id"] == "1003" for r in db.silver_orders)


@pytest.mark.asyncio
async def test_dataset_ingestion_duplicate_natural_key_rejection():
    db = FakeDB()
    orchestrator = DatasetIngestionOrchestrator(db=db, bronze=FakeBronze(), silver=FakeSilver(db), gold=FakeGold(db))
    tenant_id = str(uuid.uuid4())
    dataset_id = str(uuid.uuid4())
    db.datasets[dataset_id] = {
        "id": dataset_id,
        "tenant_id": tenant_id,
        "filename": "dup.csv",
        "file_type": "csv",
        "storage_path": "path",
        "status": "profiled",
    }

    raw_csv = b"order_id,amount\n1001,50.00\n1001,75.00"

    with pytest.raises(ValueError, match="Duplicate natural identifier '1001'"):
        await orchestrator.ingest_dataset(
            tenant_id=tenant_id,
            user_id="user_1",
            dataset_id=dataset_id,
            target_entity="orders",
            column_mappings={"order_id": "source_id", "amount": "gross_amount"},
            natural_key_column="order_id",
            raw_file_bytes=raw_csv,
        )


@pytest.mark.asyncio
async def test_dataset_ingestion_anonymous_replace_semantics():
    db = FakeDB()
    orchestrator = DatasetIngestionOrchestrator(db=db, bronze=FakeBronze(), silver=FakeSilver(db), gold=FakeGold(db))
    tenant_id = str(uuid.uuid4())
    dataset_id = str(uuid.uuid4())
    db.datasets[dataset_id] = {
        "id": dataset_id,
        "tenant_id": tenant_id,
        "filename": "anon.csv",
        "file_type": "csv",
        "storage_path": "path",
        "status": "profiled",
    }

    raw_csv_v1 = b"amount,date\n50.00,2026-09-01\n75.00,2026-09-02"
    res1 = await orchestrator.ingest_dataset(
        tenant_id=tenant_id,
        user_id="user_1",
        dataset_id=dataset_id,
        target_entity="orders",
        column_mappings={"amount": "gross_amount", "date": "source_created_at"},
        natural_key_column=None,
        raw_file_bytes=raw_csv_v1,
    )
    assert len(db.silver_orders) == 2
    assert db.silver_orders[0]["source_id"] == "anon_000001"
    assert db.silver_orders[1]["source_id"] == "anon_000002"

    # Re-upload v2 with 1 row
    raw_csv_v2 = b"amount,date\n120.00,2026-09-03"
    res2 = await orchestrator.ingest_dataset(
        tenant_id=tenant_id,
        user_id="user_1",
        dataset_id=dataset_id,
        target_entity="orders",
        column_mappings={"amount": "gross_amount", "date": "source_created_at"},
        natural_key_column=None,
        raw_file_bytes=raw_csv_v2,
    )
    # Old 2 rows purged, only new row exists
    assert len(db.silver_orders) == 1
    assert db.silver_orders[0]["source_id"] == "anon_000001"
    assert db.silver_orders[0]["gross_amount"] == 120.0
