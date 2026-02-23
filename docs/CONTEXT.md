# DojoTap Context

## Tech Details
- Python: `3.13+`
- Backend:
  - `fastapi`
  - `httpx`
  - `pydantic-settings`
  - `tzdata`
  - `uvicorn`
  - `playwright` (only for `backend/integrations/chesstempo` automation)
- Frontend:
  - Vue `3`
  - Vite `6`
  - TypeScript `5`
  - Playwright `@playwright/test`
  - Frontend `postinstall` runs `npm run setup:codex-mcp` to auto-ensure `.codex/config.toml` has Playwright MCP config
- Testing:
  - `pytest` for backend unit logic
  - `backend/scripts/api_smoke.py` for repeated non-destructive API validation
  - `npm run build` (Vue type-check + production build) for frontend validation
  - `npm run e2e:smoke` (Playwright mocked API smoke test for frontend tile flow)
- Deployment:
  - GitHub Pages via `.github/workflows/deploy-pages.yml` (frontend static build only)
  - Render Blueprint via `render.yaml`:
    - `dojotap-api` web service (free tier)
    - `dojotap-chesstempo-csv` cron service (starter tier; scheduled CSV fetch)

## Strict Constraints
- Do not store bearer tokens in repo files.
- Use private/local auth only (no multi-user hosted auth in v1).
- Preferred auth flow is local ChessDojo credential login via Cognito Hosted UI OAuth (code + refresh grant) and backend session refresh token storage.
- `.env` token (`CHESSDOJO_BEARER_TOKEN`) remains a fallback/manual override path only.
- v1 supports adding progress only via `POST /user/progress/v3`.
- No delete automation in v1.
- Keep tile-first UX: no typing for count/minutes in normal flow.
- Count tiles are always contiguous increments (`+1..+N`, step `1`).
- Count cap is configurable per task (`1..200`), with hardcoded fallback default `10`.
- Timer tiles are fixed to `5..180` in steps of `5`.
- Hardcoded fallback defaults are fixed and not user-editable:
  - count cap: `10`
  - count label mode: `+N`
  - tile size: `large`
- UI preference persistence is local browser storage only in v1 (no backend sync).

## Project Structure
```text
DojoTap/
  .github/
    workflows/
      deploy-pages.yml # GitHub Actions Pages deployment for frontend/
  render.yaml          # Render Blueprint for backend web service
  backend/
    app/
      main.py          # FastAPI routes incl. /api/auth/*, /api/health, /api/bootstrap, /api/progress
      auth.py          # local Cognito login + refresh-token persistence + manual token override
      chessdojo.py     # Upstream client + payload math + bootstrap formatting
      config.py        # Environment settings
      models.py        # API models
    scripts/
      api_smoke.py     # Repeat GET checks against ChessDojo API
    integrations/
      chessdojo/
        fetch_bearer_token.py # CLI token fetch via local auth flow
        log_progress.py       # CLI progress submit by task name
        get_progress.py       # CLI full task timeline fetch via /public/user/{id}/timeline
        README.md             # automation usage for token/progress scripts
      chesstempo/
        fetch_attempts_csv.py # Playwright-based CSV fetch + parse summary JSON
        log_unlogged_days.py  # Backfill unlogged ChessTempo days into ChessDojo task logs
        requirements.txt      # Integration-only dependency list
        README.md             # Local bootstrap + Render runbook
    tests/
      test_auth.py     # auth manager token precedence + refresh tests
      test_payloads.py # count math and payload tests
      test_chesstempo_csv_parser.py # CSV parser and day aggregation tests
      test_chesstempo_log_unlogged_days.py # backfill day selection/date mapping tests
  frontend/
    e2e/
      smoke.spec.ts         # mocked API smoke test
      visual-audit.spec.ts  # desktop visual capture flow (mocked API)
      mobile-audit.spec.ts  # mobile visual capture flow (mocked API)
    playwright.config.ts
    scripts/
      ensure-codex-playwright-mcp.mjs # auto-provisions Codex Playwright MCP config
    src/
      App.vue
      api.ts
      constants.ts
      types.ts
      components/
        FilterBar.vue
        TaskTile.vue
        TilePicker.vue
      styles/main.css
  docs/
    CONTEXT.md
    JOURNAL.md
    API_NOTES.md
  .codex/
    config.toml        # Playwright MCP server config for Codex
  README.md
```

## Conventions
- Keep backend logic pure/testable:
  - API transport in `chessdojo.py`
  - math and mapping helpers separated from route handlers
- Use `snake_case` in backend payloads returned to frontend.
- Frontend app model:
  - Dark mode only (no light theme toggle in v1).
  - Two tabs: `Pinned` (main) and `Settings`
  - `Pinned` tab flow is staged and tap-only:
    - normal task: task card -> count tile -> minutes tile -> submit
    - time-only custom task: task card -> minutes tile -> submit
  - Submit behavior:
    - success: updates task progress, returns to task stage, toast `Done`
    - failure: remains on minutes stage so the user can retry immediately
- `Settings` tab owns filters/search and pin management (inline pin/unpin actions).
- Backend bootstrap merges standard requirements with custom task access payload (`/user/access/v2`).
- Backend auth model:
  - `POST /api/auth/login` performs Cognito Hosted UI OAuth login (`/oauth2/authorize` + `/login` + `/oauth2/token`)
  - refresh uses OAuth `grant_type=refresh_token` automatically before expiry and once after upstream 401
  - refresh token is persisted locally (`~/.dojotap/auth_state.json` by default)
  - manual token fallback via `/api/auth/manual-token`
- Settings task cards own per-task overrides:
  - count label mode (`+N` or absolute current+increment)
  - tile size (`very-small`, `small`, `medium`, or `large`)
- count cap (`1..200`) as the third task-card setting
- Settings filters include `Pinned` and `Hide completed` toggles.
- Pinned tab keeps task tiles at the top of the screen; guidance is tucked into a compact `Quick help` disclosure.
- Stage transitions (task -> count -> time and back) auto-scroll viewport to top for mobile consistency.
- Pinned task state is local (`localStorage`) and initialized from server pins.
- Per-task UI preferences are persisted in localStorage.
- Frontend dependency install should auto-provision Playwright MCP config via `frontend/scripts/ensure-codex-playwright-mcp.mjs` (idempotent).
- Frontend build/runtime endpoint behavior:
  - `VITE_BASE_PATH` controls Vite `base` (needed for project Pages path deploys)
  - `VITE_API_BASE_URL` optionally points frontend API calls at a deployed backend; default remains relative `/api` for local dev proxy
- Render backend deployment:
  - service name: `dojotap-api`
  - health check: `/api/health`
  - `ALLOW_ORIGIN` must match GitHub Pages origin (`https://wouterstultiens.github.io`)
  - `LOCAL_AUTH_STATE_PATH` uses `/tmp/...` on Render (ephemeral; may require re-login after cold restart)
- ChessTempo automation conventions:
  - Keep ChessTempo logic under `backend/integrations/chesstempo` (no coupling to FastAPI route handlers).
  - Primary auth path is `CT_STORAGE_STATE_B64`; rotate it when sessions expire.
  - CSV summary output contract is JSON with per-day `exercises` and `adjusted_minutes` totals in `Europe/Amsterdam` by default.
  - `log_unlogged_days.py` is the backfill entrypoint: it skips current day by default, only checks the last 30 days by default, and logs only missing day buckets for `ChessTempo Simple Tactics`.
- ChessDojo CLI automation conventions:
  - Keep standalone token/progress scripts under `backend/integrations/chessdojo`.
  - Reuse backend auth and payload helpers (`LocalAuthManager`, `build_progress_payload`) instead of duplicating logic.
  - Full per-task history retrieval uses `GET /public/user/{user_id}/timeline` and filters by `requirementId`.
  - Prefer JSON stdout/stderr outputs for automation chaining.
- Document new API discoveries in `docs/API_NOTES.md`.
- Update `docs/JOURNAL.md` at end of each working session.
