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
