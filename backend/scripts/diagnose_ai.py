#!/usr/bin/env python3
"""Find out WHY the AI answer fails, one stage at a time (no server needed).

  python scripts/diagnose_ai.py --tenant-id <TENANT_UUID>

Reads .env from the project folder. Each line prints PASS/FAIL with the real error.
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
    from commerce_connector.platform.gemini import GeminiClient

    cfg = get_api_settings()
    print("\nConfig")
    print(f"  DATABASE_URL set : {bool(cfg.database_url)}")
    print(f"  GEMINI_API_KEY   : {'set' if cfg.gemini_api_key else 'MISSING'}")
    print(f"  Gemini model     : {cfg.gemini_model} | embedding: {cfg.gemini_embedding_model} ({cfg.embedding_dimensions} dims)")

    print("\nStages")
    db = PostgresGateway(cfg.database_url)
    ok = step("1. Database reachable", lambda: db.ping()["database"])
    gem = GeminiClient(cfg.gemini_api_key, model=cfg.gemini_model,
                       embedding_model=cfg.gemini_embedding_model, embedding_dimensions=cfg.embedding_dimensions)
    emb: list = []

    def _embed():
        emb.extend(gem.embed("total sales last 30 days"))
        return f"{len(emb)} dims"

    ok &= step("2. Gemini embedding works", _embed)
    ok &= step("3. Gemini text/JSON works", lambda: str(gem.generate_json('Return {"ok": true}')))
    ok &= step("4. pgvector functions exist (extensions.cosine_distance)",
               lambda: db.fetch_one("select extensions.cosine_distance('[1,0]'::extensions.vector,'[0,1]'::extensions.vector) as d")["d"])
    ok &= step("5. Tenant is a real workspace", lambda: (db.get_tenant(args.tenant_id) or (_ for _ in ()).throw(RuntimeError("tenant not found")))["name"])

    def _rag():
        n = db.fetch_one("select count(*) as n from ai.document_chunks where tenant_id=%s and embedding is not null", (args.tenant_id,))["n"]
        if not n:
            raise RuntimeError("RAG index is EMPTY -> call POST /api/v1/ai/rag/rebuild once for this tenant")
        return f"{n} chunks"

    ok &= step("6. RAG index has chunks for this tenant", _rag)
    if emb:
        ok &= step("7. Vector search runs", lambda: f"{len(db.match_chunks(args.tenant_id, emb, count=3))} matches")

    print("\nAll stages passed." if ok else "\nFix the first FAIL above, then run again (set DEBUG_TRACE=1 for full traceback).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
