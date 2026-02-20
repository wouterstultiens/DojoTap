# DojoTap
Dark-first, tile-only web app to log ChessDojo progress fast (task tile -> count tile -> minutes tile).

## Quick Start
```powershell
# 1) Python backend deps
.\.venv\Scripts\python -m ensurepip --upgrade
.\.venv\Scripts\python -m pip install fastapi httpx pydantic-settings tzdata uvicorn pytest

# 2) Frontend deps
cd frontend
npm install
cd ..

# 3) Configure environment
Copy-Item .env.example .env
# CHESSDOJO_BEARER_TOKEN is now optional (manual fallback token mode)

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

At first load, if no valid token is available, DojoTap shows a local sign-in screen:
- preferred: sign in with ChessDojo credentials (backend stores refresh token locally on your machine)
- fallback: paste a manual bearer token

## GitHub Pages
The repo includes `.github/workflows/deploy-pages.yml` to deploy the Vue frontend from `frontend/` to GitHub Pages.

Setup:
```powershell
# Create and push repo once
gh repo create DojoTap --public --source . --remote origin --push

# Set backend URL used by the deployed frontend
gh variable set VITE_API_BASE_URL --body "https://<your-backend-host>"
```

Then push to `master` or `main`. The workflow publishes the frontend to:
- `https://<github-user>.github.io/DojoTap/` (project Pages path)

Note: GitHub Pages does not run the FastAPI backend. Deploy backend separately (Render/Railway/Fly/etc.) and set `VITE_API_BASE_URL`.

## Render Backend (Free)
This repo includes `render.yaml` to deploy the FastAPI backend on Render free tier.

Steps:
```powershell
# 1) Push latest code (render.yaml is in repo root)
git push

# 2) In Render dashboard:
#    New -> Blueprint
#    Select this repository
#    Render reads render.yaml and creates `dojotap-api`

# 3) After first deploy, point frontend at backend
gh variable set VITE_API_BASE_URL --repo wouterstultiens/DojoTap --body "https://<your-render-service>.onrender.com"
gh workflow run deploy-pages.yml --repo wouterstultiens/DojoTap
```

Notes:
- `ALLOW_ORIGIN` is set to `https://wouterstultiens.github.io` in `render.yaml` (GitHub Pages origin).
- Free tier has cold starts and ephemeral disk, so persisted login refresh state can be lost between restarts.

## ChessTempo CSV Automation (Separate Integration)
ChessTempo fetch/parsing lives in `backend/integrations/chesstempo/` so it stays isolated from DojoTap app code.

Setup:
```powershell
pip install -r backend/integrations/chesstempo/requirements.txt
python -m playwright install chromium
```

One-time local bootstrap:
```powershell
python -m backend.integrations.chesstempo.fetch_attempts_csv `
  --stats-url "https://chesstempo.com/stats/woutie70/" `
  --init-session `
  --print-storage-state
```

Copy `CT_STORAGE_STATE_B64=...` from output into Render env vars.

Headless run (local or Render):
```powershell
python -m backend.integrations.chesstempo.fetch_attempts_csv --headless --stats-url "$CT_STATS_URL"
```

Render notes:
- `render.yaml` includes a separate cron service: `dojotap-chesstempo-csv`.
- Render cron services require a paid plan (`starter`), not free tier.
- Set at least: `CT_STATS_URL`, `CT_STORAGE_STATE_B64`.
- Optional fallback: `CT_USERNAME`, `CT_PASSWORD`.

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
- Cognito Hosted UI OAuth login + refresh-token flow for private local token management
