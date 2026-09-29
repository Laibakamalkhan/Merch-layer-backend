#!/usr/bin/env python3
"""End-to-end smoke test for a RUNNING backend.

Examples
--------
  # 1) server + database only (no login needed)
  python scripts/smoke_test.py

  # 2) full check with a Supabase user (does NOT call the AI)
  python scripts/smoke_test.py --email you@example.com --password 'Secret123'

  # 3) full check including a real AI question + streaming
  python scripts/smoke_test.py --email you@example.com --password 'Secret123' --ask

Only needs `httpx` (already in requirements.txt). Exit code is 0 when every
check passed, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys

import httpx

API = "/api/v1"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--token", help="Use an existing Supabase access token instead of email/password")
    ap.add_argument("--tenant-id", help="Workspace to test with (default: your first workspace)")
    ap.add_argument("--create-workspace", action="store_true", help="Create a workspace if you have none")
    ap.add_argument("--ask", action="store_true", help="Also send a real AI question (uses 1-2 of your AI queries)")
    ap.add_argument("--keep", action="store_true", help="Do not delete the test conversation at the end")
    args = ap.parse_args()

    c = httpx.Client(base_url=args.base_url, timeout=120)

    print("\n1) Server & database")
    try:
        r = c.get(f"{API}/health")
    except httpx.ConnectError:
        print(f"\n  Cannot reach {args.base_url}. Is uvicorn running? (see Step 4 of the guide)")
        return 1
    check("GET /health -> server is up", r.status_code == 200 and r.json().get("status") == "ok", r.text[:200])
    r = c.get(f"{API}/health/ready")
    check("GET /health/ready -> database reachable", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    if not (args.token or (args.email and args.password)):
        print("\n(No login given, so only the server checks ran. Add --email/--password for the rest.)")
        return _summary()

    print("\n2) Login")
    token = args.token
    if not token:
        r = c.post(f"{API}/auth/login", json={"email": args.email, "password": args.password})
        token = r.json().get("access_token") if r.status_code == 200 else None
        check("POST /auth/login -> got access_token", bool(token), f"{r.status_code} {r.text[:200]}")
    if not token:
        return _summary()
    c.headers["Authorization"] = f"Bearer {token}"

    r = c.get(f"{API}/me")
    check("GET /me", r.status_code == 200 and bool(r.json().get("id")), f"{r.status_code} {r.text[:200]}")
    workspaces = r.json().get("workspaces", []) if r.status_code == 200 else []

    tenant_id = args.tenant_id or (workspaces[0]["id"] if workspaces else None)
    if not tenant_id and args.create_workspace:
        r = c.post(f"{API}/me/workspaces", json={"name": "My Workspace", "slug": f"my-workspace-{secrets.token_hex(3)}"})
        if check("POST /me/workspaces -> created workspace", r.status_code == 201, r.text[:200]):
            tenant_id = r.json()["id"]
    if not check("Have a workspace (tenant_id) to test with", bool(tenant_id), "none found - rerun with --create-workspace"):
        return _summary()
    print(f"     using tenant_id = {tenant_id}")
    q = {"tenant_id": tenant_id}

    print("\n3) Read-only endpoints")
    r = c.get(f"{API}/platforms")
    check("GET /platforms", r.status_code == 200 and "items" in r.json(), f"{r.status_code} {r.text[:200]}")
    if r.status_code == 200:
        n = len(r.json()["items"])
        check("  platforms list is not empty (control.platforms seeded)", n > 0, "0 platforms - seed control.platforms")
    r = c.get(f"{API}/models")
    check("GET /models", r.status_code == 200 and r.json().get("items"), f"{r.status_code} {r.text[:200]}")
    if r.status_code == 200:
        check("  AI model available (GEMINI_API_KEY set)", bool(r.json()["items"][0].get("available")), "available=false -> set GEMINI_API_KEY")
    r = c.get(f"{API}/prompts", params=q)
    check("GET /prompts", r.status_code == 200 and len(r.json().get("items", [])) > 0, f"{r.status_code} {r.text[:200]}")
    r = c.get(f"{API}/subscription", params=q)
    check("GET /subscription", r.status_code == 200 and "plan" in r.json(), f"{r.status_code} {r.text[:200]}")
    r = c.get(f"{API}/usage", params={**q, "days": 30})
    check("GET /usage", r.status_code == 200 and "ai_queries" in r.json(), f"{r.status_code} {r.text[:200]}")
    for path in ("connections", "library", "files"):
        r = c.get(f"{API}/{path}", params=q)
        check(f"GET /{path}", r.status_code == 200 and "items" in r.json(), f"{r.status_code} {r.text[:200]}")
    r = c.get(f"{API}/conversations", params={"tenant_id": "00000000-0000-0000-0000-000000000000"})
    check("Foreign workspace is blocked (403)", r.status_code == 403, f"got {r.status_code}")

    print("\n4) Conversations")
    r = c.post(f"{API}/conversations", json={"tenant_id": tenant_id, "title": "Smoke test"})
    created = check("POST /conversations", r.status_code == 201 and bool(r.json().get("id")), f"{r.status_code} {r.text[:200]}")
    if not created:
        return _summary()
    cid = r.json()["id"]
    r = c.get(f"{API}/conversations", params=q)
    check("GET /conversations lists it", r.status_code == 200 and cid in [x["id"] for x in r.json()["items"]], r.text[:200])
    r = c.get(f"{API}/conversations/{cid}", params=q)
    check("GET /conversations/{id}", r.status_code == 200 and r.json().get("id") == cid, f"{r.status_code} {r.text[:200]}")

    if args.ask:
        print("\n5) AI (real question - needs synced data + GEMINI_API_KEY)")
        r = c.post(f"{API}/conversations/{cid}/messages", json={"tenant_id": tenant_id, "content": "Give me a summary of my total sales for the last 30 days."})
        ok = check("POST /conversations/{id}/messages -> AI answer", r.status_code == 201 and bool(r.json().get("answer")), f"{r.status_code} {r.text[:300]}")
        if ok:
            print(f"     answer: {r.json()['answer'][:160]!r}")
        r = c.get(f"{API}/conversations/{cid}/messages", params=q)
        roles = [m["role"] for m in r.json().get("items", [])] if r.status_code == 200 else []
        check("Saved exactly once: [user, assistant]", roles == ["user", "assistant"], f"roles={roles}")
        names: list[str] = []
        with c.stream("POST", f"{API}/conversations/{cid}/stream", json={"tenant_id": tenant_id, "content": "Which product sold the most?"}) as s:
            for line in s.iter_lines():
                if line.startswith("event: "):
                    names.append(line[7:])
        check("POST /conversations/{id}/stream -> events", names[:2] == ["started", "status"] and names[-1] == "done", f"events={names}")
    else:
        print("\n5) AI: skipped (add --ask to test a real question)")

    if not args.keep:
        r = c.delete(f"{API}/conversations/{cid}", params=q)
        check("DELETE /conversations/{id} (cleanup)", r.status_code == 204, f"{r.status_code}")
    return _summary()


def _summary() -> int:
    failed = [r for r in results if not r[1]]
    print(f"\n{'=' * 50}\n{len(results) - len(failed)} passed, {len(failed)} failed")
    if failed:
        print("Failed checks:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.TransportError as exc:
        # e.g. WinError 10054: the server dropped the connection mid-request.
        print(f"\n  Connection to the server broke: {type(exc).__name__}: {exc}")
        print("  -> Look at the uvicorn terminal: the real Python traceback is printed THERE.")
        print("  -> Then run: python scripts/diagnose_ai.py --tenant-id <your tenant id>")
        sys.exit(1)
