from __future__ import annotations

import hashlib
import json
from typing import Any

from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.gemini import GeminiClient


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunks(text: str, max_chars: int = 2600) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    out: list[str] = []
    current = ""
    for paragraph in paragraphs:
        proposed = paragraph if not current else current + "\n\n" + paragraph
        if len(proposed) > max_chars and current:
            out.append(current)
            current = paragraph
        else:
            current = proposed
    if current:
        out.append(current)
    return out or [text]


class SemanticIndexer:
    def __init__(self, db: PostgresGateway, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def build_documents(self, tenant_id: str) -> list[dict[str, Any]]:
        snapshot = self.db.semantic_catalog_snapshot(tenant_id)
        docs: list[dict[str, Any]] = []

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for col in snapshot["columns"]:
            grouped.setdefault((col["table_schema"], col["table_name"]), []).append(col)
        for (schema, table), cols in grouped.items():
            content = [f"Table {schema}.{table}"]
            content.append("This table is tenant-scoped. Always filter tenant_id = :tenant_id.")
            content.append("Columns:")
            for col in cols:
                content.append(f"- {col['column_name']}: {col['data_type']}")
            text = "\n".join(content)
            docs.append({
                "source_type": "schema",
                "source_ref": f"{schema}.{table}",
                "title": f"Schema: {schema}.{table}",
                "content": text,
                "content_hash": _hash(text),
                "metadata": {"schema": schema, "table": table},
            })

        for metric in snapshot["metrics"]:
            text = (
                f"Metric {metric['code']} ({metric['name']})\n"
                f"Definition: {metric['description']}\n"
                f"Preferred source: {metric['preferred_source_schema']}.{metric['preferred_source_table']}\n"
                f"SQL expression: {metric.get('sql_expression') or 'not specified'}\n"
                f"Aggregation: {metric.get('aggregation') or 'not specified'}\n"
                f"Default time column: {metric.get('default_time_column') or 'not specified'}\n"
                f"Allowed dimensions: {json.dumps(metric.get('allowed_dimensions') or [])}\n"
                f"Synonyms: {', '.join(metric.get('synonyms') or [])}"
            )
            docs.append({
                "source_type": "metric",
                "source_ref": metric["code"],
                "title": f"Metric: {metric['name']}",
                "content": text,
                "content_hash": _hash(text),
                "metadata": {"metric_code": metric["code"]},
            })

        connection_lines = ["Connected commerce stores/accounts for this tenant:"]
        for connection in snapshot["connections"]:
            connection_lines.append(
                f"- {connection['name']}: platform={connection['platform_code']}, connection_id={connection['id']}"
            )
        text = "\n".join(connection_lines)
        docs.append({
            "source_type": "connection",
            "source_ref": "connected-stores",
            "title": "Connected stores",
            "content": text,
            "content_hash": _hash(text),
            "metadata": {},
        })
        return docs


    def index_document(self, tenant_id: str, document: dict[str, Any]) -> int:
        """Embed one existing ai.documents row without rebuilding the semantic catalog."""
        embedding_job = self.db.create_embedding_job(tenant_id, document["id"], self.gemini.embedding_model)
        try:
            chunks = []
            for index, content in enumerate(_chunks(str(document.get("content") or ""))):
                if not content.strip():
                    continue
                embedding = self.gemini.embed(content)
                vector_literal = "[" + ",".join(f"{v:.10g}" for v in embedding) + "]"
                chunks.append({
                    "chunk_index": index,
                    "content": content,
                    "token_count": None,
                    "content_hash": _hash(content),
                    "embedding": vector_literal,
                    "embedding_model": self.gemini.embedding_model,
                    "metadata": document.get("metadata") or {},
                })
            self.db.replace_document_chunks(document["id"], tenant_id, chunks)
            self.db.finish_embedding_job(embedding_job["id"], "completed")
            return len(chunks)
        except Exception as exc:
            self.db.finish_embedding_job(embedding_job["id"], "failed", f"{type(exc).__name__}: {exc}")
            raise

    def rebuild(self, tenant_id: str) -> dict[str, int]:
        docs = self.db.replace_semantic_documents(tenant_id, self.build_documents(tenant_id))
        chunk_count = 0
        for doc in docs:
            embedding_job = self.db.create_embedding_job(tenant_id, doc["id"], self.gemini.embedding_model)
            try:
                chunks = []
                for index, content in enumerate(_chunks(doc["content"])):
                    embedding = self.gemini.embed(content)
                    vector_literal = "[" + ",".join(f"{v:.10g}" for v in embedding) + "]"
                    chunks.append({
                        "chunk_index": index,
                        "content": content,
                        "token_count": None,
                        "content_hash": _hash(content),
                        "embedding": vector_literal,
                        "embedding_model": self.gemini.embedding_model,
                        "metadata": doc.get("metadata") or {},
                    })
                self.db.replace_document_chunks(doc["id"], tenant_id, chunks)
                self.db.finish_embedding_job(embedding_job["id"], "completed")
                chunk_count += len(chunks)
            except Exception as exc:
                self.db.finish_embedding_job(embedding_job["id"], "failed", f"{type(exc).__name__}: {exc}")
                raise
        return {"documents": len(docs), "chunks": chunk_count}


class RagRetriever:
    def __init__(self, db: PostgresGateway, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def retrieve(self, tenant_id: str, question: str, count: int = 8) -> list[dict[str, Any]]:
        embedding = self.gemini.embed(question)
        return self.db.match_chunks(tenant_id, embedding, count=count)
