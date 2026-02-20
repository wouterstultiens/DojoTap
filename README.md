# DojoTap
Dark-first, tile-only web app to log ChessDojo progress fast (task tile -> count tile -> minutes tile).

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

## Agent Visual Loop (Codex + Playwright MCP)
`frontend/npm install` auto-runs `npm run setup:codex-mcp`, which ensures `.codex/config.toml` has a Playwright MCP server entry so Codex can inspect UI flows.

Local loop:
```powershell
cd frontend
npm run dev:host
codex
```

Optional direct MCP launch:
```powershell
cd frontend
npm run mcp:playwright
```

If needed, re-run config setup manually:
```powershell
cd frontend
npm run setup:codex-mcp
```

## Tile Controls
- DojoTap now merges standard requirements with custom tasks (`/user/access/v2`), so custom tasks appear in the same pin/settings flow.
- Count tiles always increment by `1` (`+1` to `+N`), with cap configurable per task from `1..200` in each Settings task card.
- Timer tiles are fixed to `5, 10, 15, ... , 180`.
- Per task card in `Settings`, you can directly choose:
  - count label mode: `+N` or `Absolute` (shows `current + N`)
  - tile size mode: `Large` or `Small`
  - count cap: `1..200` (scrollable select)
- Hardcoded defaults for tasks without an override are fixed and not user-editable:
  - count cap: `10`
  - count label mode: `+N`
  - tile size: `Large`
- Time-only custom tasks skip the count step and go directly to timer selection.

## Tech Stack
- Python 3.13
- FastAPI + httpx (backend API proxy and payload logic)
- Vue 3 + Vite + TypeScript (frontend tile UI)
- Pytest + API smoke script for backend validation
- Playwright smoke test for frontend flow validation
