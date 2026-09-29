#!/usr/bin/env python3
"""Rebuild the semantic RAG index for one tenant using backend configuration.

Usage:
    python scripts/rebuild_rag.py --tenant-id <TENANT_UUID>

This does not modify Shopify/Silver/Gold data. It regenerates only the
semantic catalog documents/chunks used by the AI planner.
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
    args = parser.parse_args()

    from commerce_connector.api.deps import get_api_settings
    from commerce_connector.platform.db import PostgresGateway
    from commerce_connector.platform.gemini import GeminiClient
    from commerce_connector.platform.rag import SemanticIndexer

    cfg = get_api_settings()
    if not cfg.database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if not cfg.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured. It is still required for AI text generation.")

    db = PostgresGateway(cfg.database_url)
    client = GeminiClient(
        cfg.gemini_api_key,
        model=cfg.gemini_model,
        embedding_model=cfg.gemini_embedding_model,
        embedding_dimensions=cfg.embedding_dimensions,
        embedding_provider=cfg.embedding_provider,
        ollama_base_url=cfg.ollama_base_url,
        ollama_embedding_model=cfg.ollama_embedding_model,
    )

    print("RAG rebuild")
    print(f"  tenant              : {args.tenant_id}")
    print(f"  text model          : {client.model}")
    print(f"  embedding provider  : {client.embedding_provider}")
    print(f"  embedding model     : {client.ollama_embedding_model if client.embedding_provider == 'ollama' else client.embedding_model}")
    print(f"  embedding dimension : {client.embedding_dimensions}")

    result = SemanticIndexer(db, client).rebuild(args.tenant_id)
    print(f"  documents           : {result['documents']}")
    print(f"  chunks              : {result['chunks']}")
    print("RAG rebuild completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
