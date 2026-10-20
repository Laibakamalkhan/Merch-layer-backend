#!/usr/bin/env python3
"""Rebuild the semantic RAG index for one tenant using backend configuration.

Usage:
    python scripts/rebuild_rag.py --tenant-id <TENANT_UUID> --dry-run
    python scripts/rebuild_rag.py --tenant-id <TENANT_UUID>

This does not modify Shopify/Silver/Gold data and does not touch uploaded
files. It replaces only the semantic catalog documents (source_type in
'schema', 'metric', 'connection') and their chunks for the given tenant.
Uploaded files are re-indexed one by one via POST /files/{id}/reindex.

--dry-run reads the catalog and makes ONE test embedding call. It writes
nothing to the database.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build catalog documents and test one embedding. No database writes.",
    )
    args = parser.parse_args()

    from commerce_connector.api.deps import get_api_settings
    from commerce_connector.platform.db import PostgresGateway
    from commerce_connector.platform.groq import GroqClient
    from commerce_connector.platform.rag import SemanticIndexer

    cfg = get_api_settings()
    if not cfg.database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if not cfg.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured. It is still required for AI text generation.")
    if cfg.embedding_provider == "nvidia" and not cfg.nvidia_api_key:
        raise RuntimeError("NVIDIA_API_KEY is not configured but EMBEDDING_PROVIDER=nvidia.")

    db = PostgresGateway(cfg.database_url)
    client = GroqClient(
        cfg.groq_api_key,
        model=cfg.groq_model,
        embedding_dimensions=cfg.embedding_dimensions,
        embedding_provider=cfg.embedding_provider,
        ollama_base_url=cfg.ollama_base_url,
        ollama_embedding_model=cfg.ollama_embedding_model,
        use_system_proxy=cfg.groq_use_system_proxy,
        nvidia_api_key=cfg.nvidia_api_key,
        nvidia_base_url=cfg.nvidia_base_url,
        nvidia_embedding_model=cfg.nvidia_embedding_model,
    )

    print("RAG rebuild" + (" (DRY RUN - no database writes)" if args.dry_run else ""))
    print(f"  tenant              : {args.tenant_id}")
    print(f"  text model          : {client.model}")
    print(f"  embedding provider  : {client.embedding_provider}")
    print(f"  embedding model     : {client.embedding_model}")
    print(f"  embedding dimension : {client.embedding_dimensions}")
    print("  scope               : schema/metric/connection documents only (uploaded files are NOT touched)")

    indexer = SemanticIndexer(db, client)

    if args.dry_run:
        docs = indexer.build_documents(args.tenant_id)
        sample = docs[0]
        vector = client.embed(sample["content"][:2000], task="document", title=sample["title"])
        print(f"  documents to build  : {len(docs)}")
        print(f"  test embedding      : {len(vector)} dims")
        print("Dry run completed. Nothing was written.")
        return 0

    result = indexer.rebuild(args.tenant_id)
    print(f"  documents           : {result['documents']}")
    print(f"  chunks              : {result['chunks']}")
    print("RAG rebuild completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())