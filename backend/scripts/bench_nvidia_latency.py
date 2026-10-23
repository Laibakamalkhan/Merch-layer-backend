#!/usr/bin/env python3
"""NVIDIA embedding latency benchmark. Does NOT touch the database.

  python scripts/bench_nvidia_latency.py
  python scripts/bench_nvidia_latency.py --burst 6 --idle 90 --after-idle 2 --timeout 20

Each call uses a single attempt (no retries) so every timeout is visible.
Prints only timings and error type names. Never prints keys or .env content.
"""
from __future__ import annotations

import argparse
import os
import statistics
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--burst", type=int, default=6, help="back-to-back calls in phase A")
    ap.add_argument("--idle", type=int, default=90, help="seconds to stay idle before phase B (0 = skip phase B)")
    ap.add_argument("--after-idle", type=int, default=2, help="calls after the idle pause in phase B")
    ap.add_argument("--timeout", type=float, default=20.0, help="per-call timeout in seconds")
    args = ap.parse_args()
    load_env()

    from commerce_connector.api.config import APISettings
    from commerce_connector.platform.nvidia_embeddings import NvidiaEmbeddingClient

    cfg = APISettings.from_env()
    if not cfg.nvidia_api_key:
        print("[STOP] NVIDIA_API_KEY is not set. Nothing was called.")
        return 2

    client = NvidiaEmbeddingClient(
        cfg.nvidia_api_key,
        base_url=cfg.nvidia_base_url,
        model=cfg.nvidia_embedding_model,
        dimensions=cfg.embedding_dimensions,
        timeout=args.timeout,
        max_attempts=1,
        use_system_proxy=cfg.groq_use_system_proxy,
    )
    print(f"\nModel: {client.model}")
    print(f"Per-call timeout: {args.timeout:.0f}s, retries: off\n")

    ok_ms: list[float] = []
    failures = 0
    counter = 0

    def call(phase: str) -> None:
        nonlocal failures, counter
        counter += 1
        text = f"total revenue in week {counter}"
        started = time.perf_counter()
        try:
            client.embed(text, task="query")
            ms = (time.perf_counter() - started) * 1000
            ok_ms.append(ms)
            print(f"  #{counter} [{phase}] ok      {ms:8.0f} ms")
        except Exception as exc:  # noqa: BLE001
            ms = (time.perf_counter() - started) * 1000
            failures += 1
            print(f"  #{counter} [{phase}] FAILED  {ms:8.0f} ms  {type(exc).__name__}: {exc}")

    print(f"Phase A: {args.burst} calls back-to-back")
    for _ in range(max(0, args.burst)):
        call("A")

    if args.idle > 0 and args.after_idle > 0:
        print(f"\nIdle for {args.idle}s, then Phase B: {args.after_idle} calls")
        time.sleep(args.idle)
        for _ in range(args.after_idle):
            call("B")

    print("\nSummary")
    print(f"  successful calls : {len(ok_ms)}")
    print(f"  failed/timeouts  : {failures}")
    if ok_ms:
        print(f"  median ok        : {statistics.median(ok_ms):.0f} ms")
        print(f"  slowest ok       : {max(ok_ms):.0f} ms")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())