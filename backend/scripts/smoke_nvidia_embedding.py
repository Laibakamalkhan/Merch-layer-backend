#!/usr/bin/env python3
"""Real NVIDIA embedding smoke test. Does NOT touch the database.

  python scripts/smoke_nvidia_embedding.py

Makes 4 small embedding calls through the same GroqClient the app uses and
prints only dimensions, similarity numbers and timings. It never prints keys,
DATABASE_URL, or any .env content.
"""
from __future__ import annotations

import math
import os
import sys
import time
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


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


def main() -> int:
    load_env()

    from commerce_connector.api.config import APISettings
    from commerce_connector.platform.groq import GroqClient

    cfg = APISettings.from_env()
    print("\nConfig")
    print(f"  provider         : {cfg.embedding_provider}")
    print(f"  NVIDIA key set   : {bool(cfg.nvidia_api_key)}")
    print(f"  expected dims    : {cfg.embedding_dimensions}")

    if cfg.embedding_provider != "nvidia":
        print("\n[STOP] EMBEDDING_PROVIDER is not 'nvidia'. Nothing was called.")
        return 2

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
    print(f"  active model     : {client.embedding_model}")
    print(f"  base url         : {cfg.nvidia_base_url}\n")

    query_text = "total revenue last month"
    relevant_doc = "Metric: net sales revenue. Total revenue is the sum of order totals after discounts."
    unrelated_doc = "Employee holiday policy: staff receive 20 days of paid leave each year."

    failures = 0
    vectors: dict[str, list[float]] = {}

    def run(label: str, text: str, task: str) -> None:
        nonlocal failures
        started = time.perf_counter()
        try:
            vec = client.embed(text, task=task)
            ms = (time.perf_counter() - started) * 1000
            problems = []
            if len(vec) != cfg.embedding_dimensions:
                problems.append(f"dims={len(vec)}")
            if not all(math.isfinite(v) for v in vec):
                problems.append("non-finite values")
            if not any(v != 0.0 for v in vec):
                problems.append("all-zero vector")
            if problems:
                failures += 1
                print(f"[FAIL] {label}  -> {', '.join(problems)}")
                return
            vectors[label] = vec
            print(f"[PASS] {label}  -> task={task}, dims={len(vec)}, {ms:.0f} ms")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {label}  -> {type(exc).__name__}: {exc}")

    run("query embedding", query_text, "query")
    time.sleep(0.8)
    run("relevant document embedding", relevant_doc, "document")
    time.sleep(0.8)
    run("unrelated document embedding", unrelated_doc, "document")
    time.sleep(0.8)
    run("query text embedded as document", query_text, "document")

    print()
    if {"query embedding", "relevant document embedding", "unrelated document embedding"} <= vectors.keys():
        q = vectors["query embedding"]
        sim_rel = cosine(q, vectors["relevant document embedding"])
        sim_unrel = cosine(q, vectors["unrelated document embedding"])
        ok = sim_rel > sim_unrel
        failures += 0 if ok else 1
        print(
            f"[{'PASS' if ok else 'FAIL'}] relevant doc ranks above unrelated doc"
            f"  -> relevant={sim_rel:.4f}, unrelated={sim_unrel:.4f}"
        )

    if {"query embedding", "query text embedded as document"} <= vectors.keys():
        same = cosine(vectors["query embedding"], vectors["query text embedded as document"])
        ok = same < 0.999999
        failures += 0 if ok else 1
        print(
            f"[{'PASS' if ok else 'FAIL'}] query vs passage input_type give different vectors"
            f"  -> cosine={same:.6f}"
        )

    print("\nRESULT:", "ALL PASSED" if failures == 0 else f"{failures} FAILED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())