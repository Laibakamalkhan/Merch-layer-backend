from __future__ import annotations

import json

import pytest

import commerce_connector.platform.groq as groq_module
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.groq import GroqClient
from commerce_connector.platform.rag import RagRetriever, SemanticIndexer

TENANT_ID = "tenant-rag-test"
ACTIVE_MODEL = "test/active-embed-model"
DIMENSIONS = 4


class FakeLLM:
    embedding_model = ACTIVE_MODEL
    embedding_dimensions = DIMENSIONS

    def __init__(self, fail_on_call: int | None = None):
        self.calls: list[dict] = []
        self.fail_on_call = fail_on_call

    def embed(self, text, *, task="query", title=None):
        self.calls.append({"text": text, "task": task, "title": title})
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise RuntimeError("embedding provider failed")
        return [0.5, 0.25, 0.125, 1.0]


class FakeDB:
    def __init__(self):
        self.events: list[str] = []
        self.job_args: tuple | None = None
        self.replaced_chunks: list[dict] | None = None
        self.finish_args: tuple | None = None
        self.replace_semantic_args: dict | None = None
        self.match_args: dict | None = None

    def semantic_catalog_snapshot(self, tenant_id):
        return {
            "columns": [
                {
                    "table_schema": "silver",
                    "table_name": "orders",
                    "column_name": "total",
                    "data_type": "numeric",
                }
            ],
            "metrics": [
                {
                    "code": "revenue",
                    "name": "Revenue",
                    "description": "Total sales",
                    "preferred_source_schema": "gold",
                    "preferred_source_table": "daily_sales",
                }
            ],
            "connections": [
                {"name": "My Shop", "platform_code": "shopify", "id": "conn-1"}
            ],
        }

    def create_embedding_job(self, tenant_id, document_id, model, dimensions):
        self.events.append("create_job")
        self.job_args = (tenant_id, document_id, model, dimensions)
        return {"id": "job-1"}

    def replace_document_chunks(self, document_id, tenant_id, chunks):
        self.events.append("replace_chunks")
        self.replaced_chunks = chunks

    def finish_embedding_job(self, job_id, status, error=None):
        self.events.append("finish_job")
        self.finish_args = (job_id, status, error)

    def replace_semantic_documents_with_chunks(
        self, tenant_id, prepared, *, embedding_model, output_dimensions
    ):
        self.events.append("replace_semantic")
        self.replace_semantic_args = {
            "tenant_id": tenant_id,
            "prepared": prepared,
            "embedding_model": embedding_model,
            "output_dimensions": output_dimensions,
        }
        return {"documents": len(prepared)}

    def match_chunks(self, tenant_id, embedding, count=8, min_similarity=None, embedding_model=None):
        self.match_args = {
            "tenant_id": tenant_id,
            "embedding": embedding,
            "count": count,
            "min_similarity": min_similarity,
            "embedding_model": embedding_model,
        }
        return [{"content": "hit"}]


def _document():
    return {
        "id": "doc-1",
        "title": "Uploaded sales file",
        "content": "Some uploaded file content.",
        "metadata": {"source": "file"},
    }


# ---------------------------------------------------------------- index_document (uploaded files)


def test_index_document_embeds_as_document_with_title():
    llm, db = FakeLLM(), FakeDB()

    SemanticIndexer(db, llm).index_document(TENANT_ID, _document())

    assert llm.calls == [
        {
            "text": "Some uploaded file content.",
            "task": "document",
            "title": "Uploaded sales file",
        }
    ]


def test_index_document_records_active_model_on_job_and_chunks():
    llm, db = FakeLLM(), FakeDB()

    count = SemanticIndexer(db, llm).index_document(TENANT_ID, _document())

    assert count == 1
    assert db.job_args == (TENANT_ID, "doc-1", ACTIVE_MODEL, DIMENSIONS)
    assert [c["embedding_model"] for c in db.replaced_chunks] == [ACTIVE_MODEL]
    assert db.replaced_chunks[0]["embedding"] == "[0.5,0.25,0.125,1]"
    assert db.finish_args == ("job-1", "completed", None)


def test_index_document_failure_marks_job_failed_and_keeps_old_chunks():
    llm, db = FakeLLM(fail_on_call=1), FakeDB()

    with pytest.raises(RuntimeError, match="embedding provider failed"):
        SemanticIndexer(db, llm).index_document(TENANT_ID, _document())

    assert "replace_chunks" not in db.events
    assert db.finish_args[0:2] == ("job-1", "failed")
    assert "embedding provider failed" in db.finish_args[2]


# ---------------------------------------------------------------- rebuild (semantic catalog)


def test_rebuild_embeds_every_catalog_document_as_document():
    llm, db = FakeLLM(), FakeDB()

    SemanticIndexer(db, llm).rebuild(TENANT_ID)

    # schema + metric + connection documents
    assert len(llm.calls) == 3
    assert {c["task"] for c in llm.calls} == {"document"}
    assert {c["title"] for c in llm.calls} == {
        "Schema: silver.orders",
        "Metric: Revenue",
        "Connected stores",
    }


def test_rebuild_passes_active_model_and_dimensions_to_database():
    llm, db = FakeLLM(), FakeDB()

    SemanticIndexer(db, llm).rebuild(TENANT_ID)

    args = db.replace_semantic_args
    assert args["tenant_id"] == TENANT_ID
    assert args["embedding_model"] == ACTIVE_MODEL
    assert args["output_dimensions"] == DIMENSIONS
    chunk_models = {
        chunk["embedding_model"]
        for doc in args["prepared"]
        for chunk in doc["chunks"]
    }
    assert chunk_models == {ACTIVE_MODEL}


def test_rebuild_embedding_failure_never_touches_existing_index():
    llm, db = FakeLLM(fail_on_call=2), FakeDB()

    with pytest.raises(RuntimeError, match="embedding provider failed"):
        SemanticIndexer(db, llm).rebuild(TENANT_ID)

    assert "replace_semantic" not in db.events


@pytest.mark.asyncio
async def test_run_pipeline_rag_status_on_embedder_failure():
    from unittest.mock import AsyncMock, MagicMock
    from commerce_connector.platform.service import CommercePlatformService

    service = MagicMock(spec=CommercePlatformService)
    service.sync_engine = MagicMock()
    service.sync_engine.run = AsyncMock(return_value={"job_id": "job-1", "status": "completed"})
    service.indexer = MagicMock()
    service.indexer.rebuild.side_effect = RuntimeError("nvidia embedding API timed out")

    res = await CommercePlatformService.run_pipeline(
        service,
        tenant_id=TENANT_ID,
        connection_ids=["conn-1"],
        rebuild_rag_after_sync=True,
    )
    assert res["rag"] == {"status": "failed", "error_type": "RuntimeError"}
    assert "rag_error" in res


@pytest.mark.asyncio
async def test_run_pipeline_rag_status_on_rebuild_success():
    from unittest.mock import AsyncMock, MagicMock
    from commerce_connector.platform.service import CommercePlatformService

    service = MagicMock(spec=CommercePlatformService)
    service.sync_engine = MagicMock()
    service.sync_engine.run = AsyncMock(return_value={"job_id": "job-1", "status": "completed"})
    service.indexer = MagicMock()
    service.indexer.rebuild.return_value = {"documents": 3}

    res = await CommercePlatformService.run_pipeline(
        service,
        tenant_id=TENANT_ID,
        connection_ids=["conn-1"],
        rebuild_rag_after_sync=True,
    )
    assert res["rag"] == {"status": "ok", "details": {"documents": 3}}


# ---------------------------------------------------------------- retrieval


def test_retrieve_embeds_question_as_query_and_searches_with_vector():
    llm, db = FakeLLM(), FakeDB()

    result = RagRetriever(db, llm).retrieve(TENANT_ID, "total revenue", count=5)

    assert result == [{"content": "hit"}]
    assert llm.calls == [{"text": "total revenue", "task": "query", "title": None}]
    assert db.match_args == {
        "tenant_id": TENANT_ID,
        "embedding": [0.5, 0.25, 0.125, 1.0],
        "count": 5,
        "min_similarity": 0.20,
        "embedding_model": ACTIVE_MODEL,
    }


# ---------------------------------------------------------------- real GroqClient + NVIDIA


class _FakeResponse:
    status_code = 200
    headers: dict = {}

    def __init__(self, size):
        self._body = {"data": [{"index": 0, "embedding": [0.1] * size}]}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


def test_nvidia_indexing_uses_passage_and_retrieval_uses_query(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return _FakeResponse(768)

    monkeypatch.setattr(groq_module.httpx, "post", fake_post)
    llm = GroqClient(
        "groq-fake-key-not-real",
        embedding_provider="nvidia",
        nvidia_api_key="nvidia-fake-key-not-real",
    )
    db = FakeDB()

    SemanticIndexer(db, llm).index_document(TENANT_ID, _document())
    RagRetriever(db, llm).retrieve(TENANT_ID, "total revenue")

    assert [c["json"]["input_type"] for c in calls] == ["passage", "query"]
    assert db.job_args[2] == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert db.replaced_chunks[0]["embedding_model"] == (
        "nvidia/llama-nemotron-embed-vl-1b-v2"
    )
    assert len(db.match_args["embedding"]) == 768
    assert (
        db.match_args["embedding_model"]
        == "nvidia/llama-nemotron-embed-vl-1b-v2"
    )


# ---------------------------------------------------------------- model forwarding & PostgresGateway


def test_retrieve_forwards_none_when_llm_has_no_embedding_model():
    class MinimalLLM:
        def embed(self, text, *, task="query", title=None):
            return [0.1, 0.2, 0.3, 0.4]

    db = FakeDB()
    RagRetriever(db, MinimalLLM()).retrieve(TENANT_ID, "sales query")
    assert db.match_args["embedding_model"] is None


def test_postgres_gateway_match_chunks_sql_and_params(monkeypatch):
    gateway = PostgresGateway.__new__(PostgresGateway)
    captured = []

    def fake_fetch_all(query, params):
        captured.append({"query": query, "params": params})
        return [{"chunk_id": "c1"}]

    monkeypatch.setattr(gateway, "fetch_all", fake_fetch_all)

    gateway.match_chunks(
        "t-1",
        [0.1, 0.2],
        count=6,
        min_similarity=0.30,
        embedding_model="nvidia/llama-nemotron-embed-vl-1b-v2",
    )
    assert len(captured) == 1
    q1, p1 = captured[0]["query"], captured[0]["params"]
    assert "(%s::text is null or c.embedding_model=%s)" in q1
    assert "c.tenant_id=%s" in q1
    assert "d.tenant_id=%s" in q1
    assert p1[1] == "t-1"
    assert p1[2] == "t-1"
    assert p1[3] == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert p1[4] == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert p1[5] == 0.30
    assert p1[9] == 6

    gateway.match_chunks("t-1", [0.1, 0.2])
    assert len(captured) == 2
    p2 = captured[1]["params"]
    assert p2[3] is None
    assert p2[4] is None


def test_postgres_gateway_match_file_chunks_sql_and_params(monkeypatch):
    gateway = PostgresGateway.__new__(PostgresGateway)
    captured = []

    def fake_fetch_all(query, params):
        captured.append({"query": query, "params": params})
        return [{"chunk_id": "c2"}]

    monkeypatch.setattr(gateway, "fetch_all", fake_fetch_all)

    assert gateway.match_file_chunks("t-1", "u-1", [], [0.1, 0.2]) == []
    assert len(captured) == 0

    gateway.match_file_chunks(
        "t-1",
        "u-1",
        ["f-1"],
        [0.1, 0.2],
        count=5,
        min_similarity=0.25,
        embedding_model="nvidia/llama-nemotron-embed-vl-1b-v2",
    )
    assert len(captured) == 1
    q1, p1 = captured[0]["query"], captured[0]["params"]
    assert "(%s::text is null or c.embedding_model=%s)" in q1
    assert "d.tenant_id=%s" in q1
    assert "d.metadata->>'user_id'=%s" in q1
    assert p1[1] == "t-1"
    assert p1[2] == "u-1"
    assert p1[3] == ["f-1"]
    assert p1[4] == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert p1[5] == "nvidia/llama-nemotron-embed-vl-1b-v2"
    assert p1[7] == 0.25
    assert p1[9] == 5

    gateway.match_file_chunks("t-1", "u-1", ["f-1"], [0.1, 0.2])
    assert len(captured) == 2
    p2 = captured[1]["params"]
    assert p2[4] is None
    assert p2[5] is None