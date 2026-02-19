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
- Task count/timer setups are profile-driven and task-specific.
- Profile persistence is local browser storage only in v1 (no backend sync).

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
      smoke.spec.ts    # mocked API smoke test
    playwright.config.ts
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
  - Two tabs: `Pinned` (main) and `Settings`
  - `Pinned` tab is full-screen staged flow:
    - task title tile -> count tile -> minutes tile -> submit
  - After minutes select: return to task stage and show toast state (`Processing...`, then `Done` on success)
- `Settings` tab owns filters/search and pin management (inline pin/unpin actions).
- `Settings` tab also owns per-task setup assignment:
  - task-specific `Count setup` selector
  - task-specific `Timer setup` selector
  - reusable custom setup creation (`count`/`timer`, comma-separated values)
- Pinned task state is local (`localStorage`) and initialized from server pins.
- Setup assignments and custom setups are persisted in localStorage.
- Document new API discoveries in `docs/API_NOTES.md`.
- Update `docs/JOURNAL.md` at end of each working session.
