# Universal Commerce V6 - Backend corrected package

This package is the original project with the targeted backend fixes from backend_fixes.zip applied.

IMPORTANT:
- The AI endpoint fix improves error handling and prevents opaque connection/500 failures.
- A real AI answer still requires GEMINI_API_KEY.
- A workspace must have synced data and a non-empty RAG index.
- Do not send Supabase service-role key, DATABASE_URL, or GEMINI_API_KEY to the frontend.

Suggested verification:
1. Activate the project's .venv.
2. Install/update dependencies: python -m pip install -e .
3. Start: uvicorn api_main:app --reload --host 0.0.0.0 --port 8000
4. Run:
   python scripts/smoke_test.py --email 'YOUR_EMAIL' --password 'YOUR_PASSWORD' --create-workspace
5. Diagnose AI:
   python scripts/diagnose_ai.py --tenant-id YOUR_TENANT_ID
6. After the diagnose script passes, run:
   python scripts/smoke_test.py --email 'YOUR_EMAIL' --password 'YOUR_PASSWORD' --ask

The frontend contract is in docs/FRONTEND_API_GUIDE.md.
