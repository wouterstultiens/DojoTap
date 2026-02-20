# DojoTap Context

## Tech Details
- Python: `3.13+`
- Backend:
  - `fastapi`
  - `httpx`
  - `pydantic-settings`
  - `uvicorn`
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

## Strict Constraints
- Do not store bearer tokens in repo files.
- Token must be read from local `.env` (`CHESSDOJO_BEARER_TOKEN`).
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
  backend/
    app/
      main.py          # FastAPI routes: /api/health, /api/bootstrap, /api/progress
      chessdojo.py     # Upstream client + payload math + bootstrap formatting
      config.py        # Environment settings
      models.py        # API models
    scripts/
      api_smoke.py     # Repeat GET checks against ChessDojo API
    tests/
      test_payloads.py # count math and payload tests
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
- Settings task cards own per-task overrides:
  - count label mode (`+N` or absolute current+increment)
  - tile size (`small` or `large`)
- count cap (`1..200`) as the third task-card setting
- Settings filters include `Pinned` and `Hide completed` toggles.
- Pinned task state is local (`localStorage`) and initialized from server pins.
- Per-task UI preferences are persisted in localStorage.
- Frontend dependency install should auto-provision Playwright MCP config via `frontend/scripts/ensure-codex-playwright-mcp.mjs` (idempotent).
- Document new API discoveries in `docs/API_NOTES.md`.
- Update `docs/JOURNAL.md` at end of each working session.
