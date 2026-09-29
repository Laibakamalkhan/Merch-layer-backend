# MerchLayer - Integration Guide (Roman Urdu)

## Run karne ke steps
1. Backend:  `cd backend` -> `python -m venv .venv` -> activate -> `pip install -e .`
2. `backend/.env.example` ko copy karke `backend/.env` banao aur apni values bharo.
3. `uvicorn api_main:app --reload --port 8000`   (http://localhost:8000/docs khol ke check karo)
4. Frontend (naya terminal): root folder mein `copy .env.example .env` -> `npm install` -> `npm run dev`
5. Browser: http://localhost:5173/#workspace -> Sign up -> Store connect -> Sync -> AI se sawal.

## Kya kya fix / add hua
Backend:
- config.py: ab `backend/.env` khud load hoti hai (python-dotenv). Pehle load hi nahi hoti thi.
- CORS: default mein 5173 (Vite) add. Pehle sirf 3000 tha -> browser sab requests block karta tha.
- requirements.txt / pyproject.toml: python-dotenv add.
Frontend (naya):
- src/lib/api.js            : saari backend calls + token refresh + error handling
- src/context/AuthContext   : login/signup/logout + tenant_id (workspace) management
- src/components/auth/AuthPage : login/signup screen
- ConnectStoreModal         : store connect (create -> test -> sync)
Frontend (badla hua):
- WorkspaceChat: fake MOCK responses hata kar real /conversations API
- StoreConnectorsTab / LibraryTab / FilesTab: fake data hata kar real API
- Sidebar / Header / App / WorkspaceView: real user, real plan, login gate

## Abhi bhi baaki (next steps)
- Library se purani chat "Resume" (messages history load)
- Charts (dashboard.charts) render karna
- Upgrade button -> /subscription/upgrade-intent (billing provider chahiye)
- File download (backend mein endpoint nahi hai)
- Store chips (Amazon/Shopify...) filter abhi sirf UI hain, backend ko nahi bheje jate

## Shopify connect karne ka sahi tareeqa (2026+)
- Shopify ne 1 Jan 2026 se naye custom apps ke liye `shpat_` token dena band kar diya.
- Naya rasta: Shopify Dev Dashboard > apna app > Settings se **Client ID** aur **Client Secret** lo, app ko store par install karo.
  MerchLayer form mein yahi dono bharo; backend khud 24 ghante ka token banata aur refresh karta hai.
- Purani app (1 Jan 2026 se pehle bani) ho to sirf purana `shpat_` access token bharo.
- Credentials app se alag check karne ke liye: `cd backend` -> `python scripts/test_shopify_credentials.py`
