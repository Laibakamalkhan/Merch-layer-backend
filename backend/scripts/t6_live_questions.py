#!/usr/bin/env python3
"""T6 live check: asks 4 questions to a RUNNING backend and prints a SHORT summary.

Run (PowerShell, from D:\\Internship-Proj2\\backend):
  ..\\.venv\\Scripts\\python.exe scripts\\t6_live_questions.py --email you@example.com --tenant-id <id> [--q "question" --q "question2"]

Password is asked in the terminal (hidden). Token is never printed.
Each question uses 1 AI query from your limit.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

import httpx

API = "/api/v1"

QUESTIONS = [
    ("1 overview", "generate me a dashboard for my data"),
    ("2 overview 30d", "dashboard for last 30 days"),
    ("3 specific", "what is the total revenue?"),
    ("4 empty period", "what is the total revenue in January 2020?"),
]


def short(v, n=220):
    s = str(v)
    return s if len(s) <= n else s[:n] + "..."


def summarize(label: str, r: httpx.Response) -> None:
    print(f"\n=== {label} ===")
    print(f"HTTP {r.status_code}")
    try:
        d = r.json()
    except Exception:
        print("non-JSON body:", short(r.text, 300))
        return
    if r.status_code >= 400:
        print("ERROR body:", short(json.dumps(d), 400))
        return
    print("top-level keys:", sorted(d.keys()))
    print("status:", d.get("status"), "| row_count:", d.get("row_count"), "| result_shape:", d.get("result_shape"))
    print("answer:", short(d.get("answer"), 350))
    rows = d.get("rows") or d.get("data") or []
    if isinstance(rows, list):
        print("rows:", len(rows), "| first row:", short(rows[0] if rows else None, 200))
    dash = d.get("dashboard")
    if isinstance(dash, dict):
        kpis = dash.get("kpis") or dash.get("kpi_cards") or []
        charts = dash.get("charts") or []
        print(
            "dashboard: kpis=%s charts=%s | window_days=%s currency=%s partial=%s no_data=%s"
            % (len(kpis), len(charts), dash.get("window_days"), dash.get("currency"), dash.get("partial"), dash.get("no_data"))
        )
        print("data_range:", dash.get("data_range"), "| previous_data_range:", dash.get("previous_data_range"))
        if kpis and isinstance(kpis[0], dict):
            print("first KPI:", short(json.dumps(kpis[0], default=str), 300))
    else:
        print("dashboard: none")
    sql = d.get("sql")
    if sql:
        print("sql (first 300 chars):", short(sql, 300))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--tenant-id", required=True)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--q", action="append", help="Your own question (repeat --q for several). Replaces the default 4.")
    args = ap.parse_args()
    questions = [(f"custom {i + 1}", q) for i, q in enumerate(args.q)] if args.q else QUESTIONS

    pw = getpass.getpass("Password (hidden): ")
    c = httpx.Client(base_url=args.base_url, timeout=180)

    r = c.post(f"{API}/auth/login", json={"email": args.email, "password": pw})
    token = r.json().get("access_token") if r.status_code == 200 else None
    if not token:
        print("Login failed:", r.status_code, short(r.text, 200))
        return 1
    c.headers["Authorization"] = f"Bearer {token}"
    print("Login OK")

    tid = args.tenant_id
    r = c.post(f"{API}/conversations", json={"tenant_id": tid, "title": "T6 live check"})
    if r.status_code != 201:
        print("Create conversation failed:", r.status_code, short(r.text, 200))
        return 1
    cid = r.json()["id"]

    for label, q in questions:
        r = c.post(f"{API}/conversations/{cid}/messages", json={"tenant_id": tid, "content": q})
        summarize(f"{label}: {q!r}", r)

    if not args.keep:
        c.delete(f"{API}/conversations/{cid}", params={"tenant_id": tid})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.TransportError as exc:
        print(f"\nConnection broke: {type(exc).__name__}: {exc}")
        print("Look at the uvicorn terminal: the real Python traceback is there.")
        sys.exit(1)