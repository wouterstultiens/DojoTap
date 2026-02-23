## [2026-02-23]
- Done: Pulled Render `dojotap-api` logs and traced login failure to Postgres FK violation (`browser_session.user_key` -> missing `user_auth_state` row) during `POST /api/auth/login`.
- Done: Fixed backend login transaction ordering by flushing `UserAuthState` before inserting `BrowserSession` in `backend/app/auth.py`.
- Done: Re-ran auth tests (`pytest backend/tests/test_auth.py`) and confirmed pass.
- Next: Deploy `dojotap-api`, attempt login from the frontend, and verify Render logs no longer show `ForeignKeyViolationError`.

## [2026-02-23]
- Done: Replaced file/in-memory auth with DB-backed session auth (`HttpOnly` cookie) and encrypted refresh-token persistence (`AUTH_STATE_ENCRYPTION_KEY`) using SQLAlchemy async tables.
- Done: Added bootstrap cache fallback path so slow/network bootstrap failures keep cached tasks visible in read-only mode instead of forcing logout.
- Done: Added backend preferences API (`GET/PUT /api/preferences`) and wired frontend pin/task UI preference sync with version-based conflict handling and cross-device persistence.
- Done: Updated frontend auth/bootstrap flow to call `/api/auth/status`, include credentials on API calls, hydrate cached bootstrap, and disable logging while stale cache is displayed.
- Done: Updated deployment/config docs and env examples for DB + cookie + encryption settings.
- Next: Provision Render Postgres + env (`DATABASE_URL`, `AUTH_STATE_ENCRYPTION_KEY`), deploy, and verify two-device sync + stale-bootstrap read-only behavior in production.

## [2026-02-23]
- Done: Added a full favicon set under `frontend/public` (SVG/ICO/PNG) including `apple-touch-icon.png` for iPhone Safari Favorites and web clips.
- Done: Wired favicon, Apple touch icon, manifest, and theme color tags into `frontend/index.html`.
- Done: Added `frontend/scripts/generate-favicons.ps1` so favicon assets can be regenerated consistently.
- Next: Deploy frontend and verify on iPhone Safari (Favorites + Add to Home Screen) after clearing cached website data.

## [2026-02-23]
- Done: Removed manual bearer-token auth override from DojoTap API/UI; login now accepts email + password only (`/api/auth/login` payload uses `email`).
- Done: Removed backend fallback to manual/env bearer tokens in `LocalAuthManager`; auth mode is now session-based only.
- Done: Added frontend bootstrap fetch timeout handling (10 seconds); on timeout DojoTap aborts fetch, logs out local session, and returns to sign-in with a clear retry message.
- Done: Updated docs (`README.md`, `docs/CONTEXT.md`, `docs/API_NOTES.md`, `.env.example`) to reflect email/password-only login.
- Next: Deploy and verify in production that a forced slow `/api/bootstrap` call (>10s) moves UI back to sign-in and that re-login immediately restores tasks.

## [2026-02-23]
- Done: Added ChessTempo storage-state auto-rotation support (`--storage-state-output`, env `CT_STORAGE_STATE_OUTPUT`) in `fetch_attempts_csv.py` and threaded it through `log_unlogged_days.py`.
- Done: Updated login-trigger auto-backfill to read storage-state from file first (`CT_STORAGE_STATE_PATH`), fallback to env `CT_STORAGE_STATE_B64`, and persist refreshed state back to file after successful runs.
- Done: Wired `CT_STORAGE_STATE_PATH` and `CT_STORAGE_STATE_OUTPUT` into both Render web and cron services, and updated docs/.env examples.
- Done: Added tests for storage-state source resolution in `backend/tests/test_ct_auto_backfill.py`.
- Next: Deploy, login once in DojoTap, and confirm logs show `ct_auto_backfill` with `storage_state_source` plus successful backfill submission.

## [2026-02-23]
- Done: Set explicit `CT_STATS_URL` values in `render.yaml` for both `dojotap-api` and `dojotap-chesstempo-csv` so stats URL is guaranteed without manual secret entry.
- Next: Ensure `dojotap-api` has either `CT_STORAGE_STATE_B64` or both `CT_USERNAME` + `CT_PASSWORD` set in Render dashboard, then login once and verify `ct_auto_backfill` success logs.

## [2026-02-23]
- Done: Added login-triggered ChessTempo backfill scheduler (`backend/app/ct_auto_backfill.py`) that runs `log_unlogged_days` on first `POST /api/auth/login` per day in `CT_TIMEZONE`.
- Done: Wired `/api/auth/login` to schedule the background backfill job after successful ChessDojo login.
- Done: Added persistent auto-backfill state/summary config in `Settings` (`CT_AUTO_BACKFILL_*`) and Render web-service env vars for `CT_*` integration data.
- Done: Updated Render web-service build to install Playwright + Chromium so login-triggered backfill can run inside `dojotap-api`.
- Done: Added scheduler tests in `backend/tests/test_ct_auto_backfill.py` and updated docs (`README.md`, `docs/CONTEXT.md`, `backend/integrations/chesstempo/README.md`, `.env.example`).
- Next: Deploy web-service changes, login once in production, then verify Render web logs show `ct_auto_backfill` scheduling + `status: success` and that the removed day is recreated.

## [2026-02-23]
- Done: Inspected production Render cron logs via CLI and confirmed latest manual run failed before submission due to missing Playwright Chromium executable at runtime (`/opt/render/.cache/ms-playwright/...`).
- Done: Updated `render.yaml` cron build/runtime to pin `PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/.playwright` so installed browsers are available during cron execution.
- Next: Push the Playwright path fix, rerun Render cron once, and verify logs show `ok: true` with `submitted_entries >= 1` for the intentionally removed day.

## [2026-02-23]
- Done: Switched Render cron service `dojotap-chesstempo-csv` to run `backend.integrations.chesstempo.log_unlogged_days` daily instead of CSV-only fetch.
- Done: Updated cron build deps to include backend app requirements needed by `log_unlogged_days` (`fastapi`, `httpx`, `pydantic-settings`, `tzdata`) plus Playwright.
- Done: Added failure-summary persistence in `log_unlogged_days.py` so `--summary-output` is written on both success and failure (includes `error_type` + `traceback` on failure).
- Done: Updated `README.md`, `docs/CONTEXT.md`, and `backend/integrations/chesstempo/README.md` for the new daily backfill + diagnostics flow.
- Next: Trigger one production cron run and verify the intentionally removed latest day is recreated; confirm Render logs and `/tmp/chesstempo/backfill.json` show `ok: true`.

## [2026-02-23]
- Done: Updated `backend/integrations/chesstempo/log_unlogged_days.py` to only consider the most recent 30 days by default (`--lookback-days`, env `CT_LOOKBACK_DAYS`) before backfilling missing logs.
- Done: Added lookback-window test coverage in `backend/tests/test_chesstempo_log_unlogged_days.py`.
- Done: Updated `README.md`, `docs/CONTEXT.md`, and `backend/integrations/chesstempo/README.md` to document 30-day default backfill behavior.
- Next: Run one live `log_unlogged_days --headless --dry-run` and verify returned `earliest_day_included` before real submit.

## [2026-02-23]
- Done: Added `backend/integrations/chesstempo/log_unlogged_days.py` to auto-backfill unlogged days from ChessTempo CSV into ChessDojo task logging (`ChessTempo Simple Tactics` by default), skipping current day.
- Done: Added tests in `backend/tests/test_chesstempo_log_unlogged_days.py` for timeline-day extraction, day filtering, max-day limiting, and backfill timestamp generation.
- Done: Documented backfill usage in `README.md`, `docs/CONTEXT.md`, and `backend/integrations/chesstempo/README.md`.
- Next: Run one live `log_unlogged_days --dry-run` followed by a real submit run to verify historical day matching against your actual timeline entries.

## [2026-02-23]
- Done: Added standalone ChessDojo integration CLIs under `backend/integrations/chessdojo` for bearer token fetch and progress logging by task name.
- Done: Added `backend/integrations/chessdojo/get_progress.py` for full per-task timeline retrieval using `GET /public/user/{user_id}/timeline` (Bruno `Get Progress` flow).
- Done: Reused existing backend auth/token refresh + payload logic so local/Render behavior matches FastAPI flow.
- Done: Hardened settings env parsing to support UTF-8 BOM `.env` files and ignore unrelated extra env keys so auth scripts/bootstrap do not fail on local `.env` noise.
- Done: Documented CLI usage in `README.md`, `docs/CONTEXT.md`, and `backend/integrations/chessdojo/README.md`.
- Next: Run a live end-to-end smoke on Render/local automation flow (`fetch_bearer_token` -> `get_progress` -> `log_progress --dry-run` -> real submit) and capture canonical task-name examples.

## [2026-02-20]
- Done: Added isolated ChessTempo integration under `backend/integrations/chesstempo` with Playwright CSV fetch, storage-state-first auth flow, and JSON per-day aggregation output.
- Done: Added parser tests (`backend/tests/test_chesstempo_csv_parser.py`) for aggregation, skipped rows, column fallback, and Europe/Amsterdam day-boundary grouping.
- Done: Added Render cron service blueprint (`dojotap-chesstempo-csv`) and documented local bootstrap + Render env/runbook in `README.md` and `backend/integrations/chesstempo/README.md`.
- Next: Run one live local `--init-session` + headless verification, then set Render cron env vars and confirm first scheduled run output.

## [2026-02-20]
- Done: Reworked mobile-first pinned layout so task tiles start near the top; moved usage copy into a compact `Quick help` disclosure and tightened topbar density.
- Done: Expanded per-task tile size choices to `Large`, `Medium`, `Small`, and `Very small` (with denser mobile grid behavior).
- Done: Added stage auto-scroll-to-top behavior and Playwright smoke coverage for iPhone SE viewport density + scroll reset flow.
- Next: Run one live-device sanity pass on iPhone SE/mini Safari and tune `very-small` tap targets if any accidental taps show up.

## [2026-02-20]
- Done: Added root `render.yaml` Blueprint for free Render backend deployment (`dojotap-api`) with health check and env defaults.
- Done: Documented Render deploy flow and Pages/backend wiring commands in `README.md` and `docs/CONTEXT.md`.
- Next: Create Render service via Blueprint, copy live backend URL, set repo variable `VITE_API_BASE_URL`, then redeploy Pages and validate login/progress end-to-end.

## [2026-02-20]
- Done: Added GitHub Pages workflow (`.github/workflows/deploy-pages.yml`) to build `frontend/` and deploy with Actions.
- Done: Made frontend deployment-safe by adding `VITE_BASE_PATH` support in Vite and `VITE_API_BASE_URL` support in frontend API calls.
- Done: Documented `gh` setup for repo creation, Pages deployment, and backend URL variable in `README.md` and `docs/CONTEXT.md`.
- Next: Create/set a hosted backend URL, save it as repository variable `VITE_API_BASE_URL`, and validate auth/progress flow from the live Pages URL.

## [2026-02-20]
- Done: Investigated custom task mode detection using live `/user/access/v2` payload and confirmed custom tasks arrive with zeroed `counts` and no explicit time/count mode flags.
- Done: Fixed custom-task `timeOnly` inference to use explicit flags first, then `progressBarSuffix` (e.g. `Minutes`) as a timer-only hint, and default ambiguous tasks to count+time.
- Done: Added regression tests for `Minutes` suffix detection and ambiguous zero-count custom-task fallback behavior (`backend/tests/test_payloads.py`).
- Next: Reload frontend and validate that `Study Preventing Blunders in Chess` now shows count + time while `ChessTempo Simple Tactics` remains time-only.

## [2026-02-20]
- Done: Migrated backend website login flow (`POST /api/auth/login`) from Cognito `USER_PASSWORD_AUTH` to Hosted UI OAuth (authorize/login/token exchange).
- Done: Migrated backend refresh path to OAuth `grant_type=refresh_token` token exchange.
- Done: Removed standalone `backend/scripts/fetch_auth_token.py` and folded that behavior into the website auth flow.
- Done: Updated auth tests + docs (`README`, `CONTEXT`, `API_NOTES`) to reflect OAuth-based login/refresh.
- Next: Verify frontend login UX against a real account that requires/does not require MFA and decide if explicit MFA UI messaging is needed.

## [2026-02-20]
- Done: Reworked `backend/scripts/fetch_auth_token.py` to use Cognito Hosted UI OAuth code flow (`auth.chessdojo.club`) instead of direct `USER_PASSWORD_AUTH`.
- Done: Added login-form parsing + explicit Cognito login error extraction so credential failures return actionable messages.
- Done: Kept local refresh-token persistence format compatible with DojoTap (`~/.dojotap/auth_state.json` by default).
- Next: Decide whether backend `/api/auth/login` should be migrated from `USER_PASSWORD_AUTH` to the same Hosted UI flow for consistency.

## [2026-02-20]
- Done: Added `backend/scripts/fetch_auth_token.py` to authenticate with ChessDojo credentials and print a usable bearer token (`raw` or `Bearer ...` format).
- Done: Reused existing local auth manager flow so the script supports refresh-token persistence and existing env/config defaults.
- Done: Documented CLI usage in `README.md` and added the script to `docs/CONTEXT.md`.
- Next: Add focused tests for CLI argument/env resolution in `fetch_auth_token.py` (username/password fallback and no-prompt behavior).

## [2026-02-20]
- Done: Replaced env-only auth with local private auth flow (`/api/auth/login`, `/api/auth/status`, `/api/auth/logout`, manual token override endpoints).
- Done: Added backend local auth manager with Cognito `InitiateAuth` login + refresh (`REFRESH_TOKEN_AUTH`) and persistent local refresh token file support.
- Done: Wired automatic token refresh before expiry and one forced refresh retry after upstream `401` for bootstrap/progress calls.
- Done: Added frontend auth gate UI (credential login + manual token fallback) that appears when bootstrap auth is missing/invalid.
- Done: Added backend auth unit tests and re-verified via `pytest backend/tests`, `npm run build`, and `npm run e2e:smoke`.
- Next: Add per-task override reset controls (single-task reset + reset-all) now that auth flow is stabilized.

## [2026-02-20]
- Done: Added custom task retrieval merge (`GET /user/access/v2`) so bootstrap and submit lookup include user custom tasks.
- Done: Added time-only task flow support (skip count stage, submit with `count_increment: 0`, timer tiles only).
- Done: Replaced global defaults panel with per-task count-cap control (`1..200`) as the third task-card setting.
- Done: Hardcoded immutable fallback defaults for tasks without overrides: count cap `10`, count label `+N`, tile size `Large`.
- Done: Updated backend/frontend tests and re-verified via `pytest`, `npm run build`, and `npm run e2e:smoke`.
- Next: Add explicit per-task override reset controls (single-task reset and reset-all) now that count cap is also per-task persisted state.

## [2026-02-20]
- Done: Kept profile-free tile flow and moved per-task controls (count label mode + tile size) from pinned cards into each task card on the Settings tab.
- Done: Renamed the settings filter checkbox label from `Pinned only` to `Pinned` and added a `Hide completed` filter toggle.
- Done: Added Settings defaults panel for fixed count cap (`70/96/120`), default label mode, and default tile size.
- Done: Locked timer tiles to `5..180` (step `5`) and updated responsive tile grid to auto-fit/fill across devices.
- Done: Updated Playwright smoke/visual tests and refreshed README/CONTEXT docs for the new direct-control model.
- Next: Add rename/delete management for persisted per-task UI preferences (clear single-task override vs clear all overrides).

## [2026-02-20]
- Done: Fixed frontend task-name interpolation for `{{count}}` placeholders using cohort-aware values (user cohort by default, selected cohort in Settings when set).
- Done: Applied interpolation across Settings task rows, Pinned task cards, and count/time picker subtitles to prevent raw template text from appearing.
- Done: Added Playwright smoke coverage for cohort switching (`ALL` -> specific cohort) and verified count text updates correctly.
- Done: Re-verified frontend via `npm run build` and `npm run e2e:smoke` (2/2 passing).
- Next: Add rename/delete controls for custom tile setups and assert localStorage migration/persistence paths with Playwright.

## [2026-02-20]
- Done: Ran Playwright visual audits (`e2e/visual-audit.spec.ts`, `e2e/mobile-audit.spec.ts`) to identify UX issues in pinned density, stage clarity, and settings layout.
- Done: Redesigned frontend to a dark-only visual system with richer pinned task cards (category + progress), improved top status strip, and clearer tile-picker headers.
- Done: Reworked Settings into a split desktop layout with sticky controls and fixed overflow behavior; mobile layout validated via Playwright capture.
- Done: Improved logging flow resilience by keeping the user in the time stage on submit failure (retry without restarting) and storing a last-log summary.
- Done: Re-verified frontend via `npm run build` and `npm run e2e:smoke`.
- Next: Add rename/delete controls for custom tile setups and assert localStorage migration/persistence paths with Playwright.

## [2026-02-19]
- Done: Added automatic Codex Playwright MCP bootstrap script (`frontend/scripts/ensure-codex-playwright-mcp.mjs`) with idempotent `.codex/config.toml` upsert logic.
- Done: Wired frontend `postinstall` to `npm run setup:codex-mcp` so MCP config is auto-added on `npm install`.
- Done: Updated README and CONTEXT docs to document automatic setup and manual rerun command.
- Next: Use the MCP loop to run one guided visual review pass of the Settings tab and log any concrete UI issues.

## [2026-02-19]
- Done: Added per-task profile system for count and timer tiles with built-in setups (Polgar next 30, Study 1-30, Classical pattern, every-5 timers) and fallback to legacy defaults.
- Done: Added Settings UI selectors per task plus reusable custom setup creation (manual values input) with localStorage persistence.
- Done: Added Playwright tooling (`playwright.config.ts`, `e2e/smoke.spec.ts`) and repo-level `.codex/config.toml` for Playwright MCP.
- Done: Updated README and CONTEXT docs for profile setup behavior and frontend smoke testing commands.
- Next: Add profile deletion/rename management for custom setups and cover persistence edge cases with frontend unit/e2e assertions.

## [2026-02-19]
- Done: Refactored frontend into two-tab UX (`Pinned` + `Settings`) with minimalist main screen and no filter clutter on the primary flow.
- Done: Replaced drawer logging with full-screen staged interaction (task -> count -> time), and added toast status flow (`Processing...` then `Done`).
- Done: Kept persistence browser-local using `localStorage` for pinned tasks and active tab preference.
- Done: Updated settings screen to filter tasks and inline pin/unpin, and refreshed layout/spacing/animations for smoother interaction.
- Done: Verified frontend via `npm run build`.
- Next: Add per-task count/minute preset profiles while preserving the same full-screen tile flow.

## [2026-02-19]
- Done: Implemented DojoTap v1 with Vue frontend tile flow (task -> count -> minutes -> submit), cohort/category/search filters, and local pinning.
- Done: Implemented FastAPI backend (`/api/health`, `/api/bootstrap`, `/api/progress`) with token-from-env and count math based on live user progress.
- Done: Added backend unit tests and a non-destructive API smoke script (`backend/scripts/api_smoke.py`) and ran 20-loop live API validation.
- Done: Documented reverse-engineered ChessDojo API behavior in `docs/API_NOTES.md`.
- Next: Add per-task input presets (for long-game tasks) while keeping the same tile UX.
