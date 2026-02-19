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
