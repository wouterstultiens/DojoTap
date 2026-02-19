# DojoTap
Tile-first web app to log ChessDojo progress fast using taps only (task tile -> count tile -> minutes tile).

## Quick Start
```powershell
# 1) Python backend deps
.\.venv\Scripts\python -m ensurepip --upgrade
.\.venv\Scripts\python -m pip install fastapi httpx pydantic-settings uvicorn pytest

# 2) Frontend deps
cd frontend
npm install
cd ..

# 3) Configure token
Copy-Item .env.example .env
# Then set CHESSDOJO_BEARER_TOKEN in .env

# 4) Run backend
.\.venv\Scripts\python -m uvicorn backend.app.main:app --reload

# 5) In another terminal run frontend
cd frontend
npm run dev

# 6) (Optional) Playwright smoke setup
# In the frontend folder
npx playwright install chromium
npm run e2e:smoke
```

Open `http://localhost:5173`.

## Tile Setup Profiles
- Every task can have its own `Count setup` and `Timer setup` (configure in the `Settings` tab).
- Built-in setups include:
  - `Polgar M2 Next 30` for count (`current + 1 ... current + 30`)
  - `Study Chapters 1-30`
  - `Classical 1-7 + 60-180`
  - Timer options including `Every 5m to 180` and `Classical 60-180`
- You can create reusable custom count/timer setups in `Settings` with a manual list, for example `1,2,3,5,8` or `60,65,70`.

## Tech Stack
- Python 3.13
- FastAPI + httpx (backend API proxy and payload logic)
- Vue 3 + Vite + TypeScript (frontend tile UI)
- Pytest + API smoke script for backend validation
- Playwright smoke test for frontend flow validation
