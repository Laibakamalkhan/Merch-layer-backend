# Project rules (read first, keep answers short)
- Stack: FastAPI + Supabase Postgres. Pipeline: Bronze -> Silver -> Gold.
- Code lives in backend/src/commerce_connector/. Do NOT touch the frontend.
- The LLM never creates numbers. All numbers come from SQL results.
- Every silver/gold query must filter by tenant_id. Never weaken sql_guard.py.
- Files db.py (2000+ lines) and ai_analyst.py (1100+ lines) are huge:
  use grep and read only needed line ranges. Never open them fully.
- Work on ONE task per chat. Show a 5-line plan first, wait for my "go".
- Run only the specific test file for the task, not the whole suite.
- Do not commit or push. Windows PowerShell commands only.