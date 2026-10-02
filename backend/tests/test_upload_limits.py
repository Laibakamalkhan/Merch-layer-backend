from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from commerce_connector.api import deps
from commerce_connector.api.app import create_app
from commerce_connector.api.auth import CurrentUser, get_current_user

TENANT_ID = str(uuid.uuid4())
USER_ID = "user-test"


@dataclass
class FakeSettings:
    max_user_file_bytes: int = 1024
    user_files_bucket: str = "test-bucket"


class FakeUserFiles:
    def __init__(self):
        self.upload_calls = []
        self.fail_with = None

    async def upload(self, object_path: str, data: bytes, content_type: str):
        self.upload_calls.append({"path": object_path, "data": data, "content_type": content_type})
        if self.fail_with:
            raise self.fail_with

        class Stored:
            path = object_path
            sha256 = "dummy-sha256"
            content_type = "text/plain"
            byte_size = len(data)

        return Stored()


class FakeDB:
    def __init__(self):
        self.documents = []

    def is_tenant_member(self, tenant_id: str, user_id: str) -> bool:
        return str(tenant_id) == TENANT_ID

    def create_file_document(self, tenant_id, user_id, title, content, content_hash, metadata):
        doc = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "title": title,
            "content": content,
            "content_hash": content_hash,
            "metadata": metadata,
        }
        self.documents.append(doc)
        return doc


class FakeService:
    def __init__(self):
        self.settings = FakeSettings()
        self.db = FakeDB()
        self.user_files = FakeUserFiles()
        self.indexer = None


@pytest.fixture()
def client_and_service():
    service = FakeService()
    app = create_app()
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=USER_ID, email="test@example.com", raw={})
    client = TestClient(app)
    yield client, service
    app.dependency_overrides.clear()


def test_upload_exceeding_limit_returns_413_and_stops_stream(client_and_service):
    client, service = client_and_service
    # 2048 bytes exceeds limit of 1024 bytes
    big_content = b"A" * 2048
    files = {"upload": ("large_file.txt", io.BytesIO(big_content), "text/plain")}
    data = {"tenant_id": TENANT_ID}

    response = client.post("/api/v1/files/upload", data=data, files=files)
    assert response.status_code == 413
    assert "File exceeds" in response.json()["detail"]
    assert len(service.user_files.upload_calls) == 0


def test_upload_empty_file_returns_400(client_and_service):
    client, service = client_and_service
    files = {"upload": ("empty.txt", io.BytesIO(b""), "text/plain")}
    data = {"tenant_id": TENANT_ID}

    response = client.post("/api/v1/files/upload", data=data, files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "File is empty"
    assert len(service.user_files.upload_calls) == 0


def test_upload_within_limit_succeeds_and_calls_storage(client_and_service):
    client, service = client_and_service
    small_content = b"Small file content within 1024 bytes"
    files = {"upload": ("small.txt", io.BytesIO(small_content), "text/plain")}
    data = {"tenant_id": TENANT_ID}

    response = client.post("/api/v1/files/upload", data=data, files=files)
    assert response.status_code == 201
    assert len(service.user_files.upload_calls) == 1
    assert service.user_files.upload_calls[0]["data"] == small_content


def test_upload_storage_error_does_not_leak_internal_exception(client_and_service):
    client, service = client_and_service
    service.user_files.fail_with = RuntimeError("sensitive_database_connection_leak_string")
    files = {"upload": ("doc.txt", io.BytesIO(b"hello world"), "text/plain")}
    data = {"tenant_id": TENANT_ID}

    response = client.post("/api/v1/files/upload", data=data, files=files)
    assert response.status_code == 500
    assert response.json()["detail"] == "File upload failed"
    assert "sensitive" not in response.text
