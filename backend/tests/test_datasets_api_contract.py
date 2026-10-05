from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user

TENANT_ID = str(uuid.uuid4())
OTHER_TENANT_ID = str(uuid.uuid4())
USER_ID = "user-dataset-test"


@dataclass
class FakeSettings:
    max_user_file_bytes: int = 25 * 1024 * 1024
    user_files_bucket: str = "test-bucket"


class FakeUserStoredFile:
    def __init__(self, path: str, size: int):
        self.path = path
        self.byte_size = size
        self.sha256 = "dummy_sha256"
        self.content_type = "text/csv"


class FakeUserFiles:
    def __init__(self):
        self.stored: dict[str, bytes] = {}

    async def upload(self, object_path: str, data: bytes, content_type: str):
        self.stored[object_path] = data
        return FakeUserStoredFile(object_path, len(data))

    async def download(self, object_path: str) -> bytes:
        if object_path not in self.stored:
            raise KeyError("File not found")
        return self.stored[object_path]


class FakeDB:
    def __init__(self):
        self.datasets: dict[str, dict[str, Any]] = {}
        self.connections: dict[str, dict[str, Any]] = {}

    def is_tenant_member(self, tenant_id: str, user_id: str) -> bool:
        return str(tenant_id) == TENANT_ID

    def create_uploaded_dataset(self, tenant_id, created_by, filename, file_type, storage_path, byte_size, checksum_sha256):
        ds_id = str(uuid.uuid4())
        row = {
            "id": ds_id,
            "tenant_id": str(tenant_id),
            "created_by": created_by,
            "filename": filename,
            "file_type": file_type,
            "storage_path": storage_path,
            "byte_size": byte_size,
            "checksum_sha256": checksum_sha256,
            "status": "uploaded",
            "has_validation_errors": False,
            "detected_entity": None,
            "profile_summary": {},
            "mapping_config": {},
            "quality_summary": {},
            "row_count": 0,
            "error_message": None,
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-01T00:00:00Z",
        }
        self.datasets[ds_id] = row
        return row

    def get_uploaded_dataset(self, dataset_id: str, tenant_id: str):
        row = self.datasets.get(str(dataset_id))
        if row and str(row["tenant_id"]) == str(tenant_id):
            return row
        return None

    def list_uploaded_datasets(self, tenant_id: str, limit: int = 50, offset: int = 0):
        rows = [d for d in self.datasets.values() if str(d["tenant_id"]) == str(tenant_id)]
        return rows[offset : offset + limit]

    def update_dataset_profile(self, dataset_id, tenant_id, status, has_validation_errors, detected_entity=None, profile_summary=None, quality_summary=None, row_count=0, error_message=None):
        row = self.get_uploaded_dataset(dataset_id, tenant_id)
        if row:
            row["status"] = status
            row["has_validation_errors"] = has_validation_errors
            if detected_entity:
                row["detected_entity"] = detected_entity
            if profile_summary:
                row["profile_summary"] = profile_summary
            if quality_summary:
                row["quality_summary"] = quality_summary
            row["row_count"] = row_count
            row["error_message"] = error_message
        return row

    def update_dataset_status(self, dataset_id, tenant_id, status, connection_id=None, mapping_config=None, quality_summary=None, row_count=None, error_message=None):
        row = self.get_uploaded_dataset(dataset_id, tenant_id)
        if row:
            row["status"] = status
            if connection_id:
                row["connection_id"] = connection_id
            if mapping_config:
                row["mapping_config"] = mapping_config
            if quality_summary:
                row["quality_summary"] = quality_summary
            if row_count is not None:
                row["row_count"] = row_count
            if error_message:
                row["error_message"] = error_message
        return row


class FakeDatasetsEngine:
    async def ingest_dataset(self, tenant_id, user_id, dataset_id, target_entity, column_mappings, natural_key_column, raw_file_bytes, rebuild_rag_after_sync=False, indexer=None):
        return {"dataset_id": dataset_id, "status": "completed", "records_written": 10}


class FakeService:
    def __init__(self):
        self.settings = FakeSettings()
        self.db = FakeDB()
        self.user_files = FakeUserFiles()
        self.indexer = None
        self.datasets_engine = FakeDatasetsEngine()


@pytest.fixture()
def client_and_service():
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=USER_ID, email="user@example.com", raw={})
    client = TestClient(app)
    yield client, service
    app.dependency_overrides.clear()


def test_upload_dataset_csv_success(client_and_service):
    client, service = client_and_service
    csv_content = b"order_id,amount,date\n1001,150.00,2026-09-01\n1002,75.50,2026-09-02"
    files = {"upload": ("orders.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"tenant_id": TENANT_ID}

    response = client.post("/api/v1/datasets/upload", data=data, files=files)
    assert response.status_code == 201
    body = response.json()
    assert "dataset" in body
    assert "profile" in body
    assert body["dataset"]["filename"] == "orders.csv"
    assert body["profile"]["detected_entity"] == "orders"
    assert body["profile"]["row_count"] == 2


def test_upload_dataset_unauthorized_tenant_rejected(client_and_service):
    client, service = client_and_service
    csv_content = b"order_id,amount\n1001,150.00"
    files = {"upload": ("orders.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"tenant_id": OTHER_TENANT_ID}

    response = client.post("/api/v1/datasets/upload", data=data, files=files)
    assert response.status_code == 403


def test_list_and_get_dataset(client_and_service):
    client, service = client_and_service
    # Seed a dataset
    ds = service.db.create_uploaded_dataset(
        TENANT_ID, USER_ID, "sales.csv", "csv", "path/to/file", 100, "sha256"
    )

    # List datasets
    list_res = client.get("/api/v1/datasets", params={"tenant_id": TENANT_ID})
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) == 1

    # Get single dataset
    get_res = client.get(f"/api/v1/datasets/{ds['id']}", params={"tenant_id": TENANT_ID})
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ds["id"]


def test_ingest_dataset_endpoint(client_and_service):
    client, service = client_and_service
    # Seed a dataset and storage file
    ds = service.db.create_uploaded_dataset(
        TENANT_ID, USER_ID, "sales.csv", "csv", "datasets/test/sales.csv", 100, "sha256"
    )
    service.user_files.stored["datasets/test/sales.csv"] = b"order_id,amount\n1001,50.00"

    payload = {
        "tenant_id": TENANT_ID,
        "target_entity": "orders",
        "column_mappings": {"order_id": "source_id", "amount": "gross_amount"},
        "natural_key_column": "order_id",
        "rebuild_rag_after_sync": False,
    }

    res = client.post(f"/api/v1/datasets/{ds['id']}/ingest", json=payload)
    assert res.status_code == 202
    body = res.json()
    assert "task_id" in body
    assert body["dataset_id"] == ds["id"]
