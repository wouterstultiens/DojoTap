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
```

Open `http://localhost:5173`.

## Tech Stack
- Python 3.13
- FastAPI + httpx (backend API proxy and payload logic)
- Vue 3 + Vite + TypeScript (frontend tile UI)
- Pytest + API smoke script for validation

