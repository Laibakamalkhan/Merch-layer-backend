#!/usr/bin/env python3
"""Diagnose AI/RAG stage-by-stage without starting FastAPI.

  python scripts/diagnose_ai.py --tenant-id <TENANT_UUID>
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def step(name: str, fn):
    try:
        detail = fn()
        print(f"[PASS] {name}" + (f"  -> {detail}" if detail else ""))
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {name}  -> {type(exc).__name__}: {exc}")
        if os.getenv("DEBUG_TRACE"):
            traceback.print_exc()
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-id", required=True)
    args = ap.parse_args()
    load_env()

    from commerce_connector.api.deps import get_api_settings
    from commerce_connector.platform.db import PostgresGateway
    from commerce_connector.platform.groq import GroqClient

    cfg = get_api_settings()
    print("\nConfig")
    print(f"  DATABASE_URL set : {bool(cfg.database_url)}")
    print(f"  GROQ_API_KEY   : {'set' if cfg.groq_api_key else 'MISSING'}")
    print(f"  Groq model     : {cfg.groq_model}")
    print(f"  Embedding        : {cfg.embedding_provider} / {cfg.ollama_embedding_model} ({cfg.embedding_dimensions} dims)")

    print("\nStages")
    db = PostgresGateway(cfg.database_url)
    ok = step("1. Database reachable", lambda: db.ping()["database"])
    gem = GroqClient(
        cfg.groq_api_key,
        model=cfg.groq_model,
        embedding_dimensions=cfg.embedding_dimensions,
        embedding_provider=cfg.embedding_provider,
        ollama_base_url=cfg.ollama_base_url,
        ollama_embedding_model=cfg.ollama_embedding_model,
    )
    emb: list[float] = []

    def _embed():
        emb.extend(gem.embed("total sales last 30 days", task="query"))
        return f"{len(emb)} dims"

    ok &= step("2. Embedding provider works", _embed)
    groq_diag_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}},
    }
    ok &= step(
        "3. Groq text/JSON works",
        lambda: str(
            gem.generate_json(
                'Return a JSON object with ok set to true.',
                schema_name="diagnostic",
                schema=groq_diag_schema,
            )
        ),
    )
    ok &= step(
        "4. pgvector functions exist (extensions.cosine_distance)",
        lambda: db.fetch_one("select extensions.cosine_distance('[1,0]'::extensions.vector,'[0,1]'::extensions.vector) as d")["d"],
    )
    ok &= step(
        "5. Tenant is a real workspace",
        lambda: (db.get_tenant(args.tenant_id) or (_ for _ in ()).throw(RuntimeError("tenant not found")))["name"],
    )

    def _rag():
        row = db.fetch_one(
            """
            select
              count(distinct d.id) filter (where d.source_type in ('schema','metric','connection')) as docs,
              count(c.id) filter (where d.source_type in ('schema','metric','connection')) as chunks,
              count(c.id) filter (where c.embedding is not null and d.source_type in ('schema','metric','connection')) as embedded_chunks
            from ai.documents d
            left join ai.document_chunks c on c.document_id=d.id
            where d.tenant_id=%s
            """,
            (args.tenant_id,),
        )
        docs = int(row["docs"] or 0)
        chunks = int(row["chunks"] or 0)
        embedded = int(row["embedded_chunks"] or 0)
        if docs == 0 or embedded == 0:
            raise RuntimeError("RAG index is EMPTY")
        if embedded < docs:
            raise RuntimeError(f"RAG index is PARTIAL: {embedded} embedded chunks for {docs} documents")
        return f"{docs} docs / {embedded} embedded chunks"

    ok &= step("6. RAG index is complete", _rag)
    if emb:
        ok &= step("7. Vector search runs", lambda: f"{len(db.match_chunks(args.tenant_id, emb, count=3, min_similarity=None))} matches")

    print("\nAll stages passed." if ok else "\nFix the first FAIL above, then run again (set DEBUG_TRACE=1 for full traceback).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
