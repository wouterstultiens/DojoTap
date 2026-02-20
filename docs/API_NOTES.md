# ChessDojo API Notes (Reverse Engineered)

## Base URL
- `https://g4shdaq6ug.execute-api.us-east-1.amazonaws.com`

## Auth
- Header: `Authorization: Bearer <token>`
- Token source in this project: local `.env` (`CHESSDOJO_BEARER_TOKEN`)

## Endpoints Used

### 1) `GET /requirements/ALL_COHORTS?scoreboardOnly=false`
- Returns object with `requirements: []`.
- Response currently returned 308 requirements during validation.
- Useful fields per requirement:
  - `id`
  - `name`
  - `category`
  - `counts` (map of cohort -> target count)
  - `startCount`
  - `progressBarSuffix`
  - `scoreboardDisplay`
  - `numberOfCohorts`
  - `sortPriority`

### 2) `GET /user`
- Returns current user profile and progress state.
- Critical fields:
  - `displayName`
  - `dojoCohort`
  - `progress` (map keyed by requirementId)
  - `pinnedTasks`
  - `weeklyPlan`

### 3) `POST /user/progress/v3`
- Adds progress for a requirement.
- Payload shape used:
```json
{
  "cohort": "1100-1200",
  "requirementId": "uuid",
  "previousCount": 438,
  "newCount": 440,
  "incrementalMinutesSpent": 40,
  "date": "2026-02-19T19:09:04.568Z",
  "notes": ""
}
```

### 4) `GET /user/access/v2`
- Used to retrieve user-specific custom tasks.
- DojoTap merges these custom tasks with the standard requirements list for bootstrap and submit lookup.
- Some custom tasks are timer-only (no count increment); for these, DojoTap submits `previousCount == newCount` with minutes only.

## Previous Count Resolution Rule
When posting progress in DojoTap:
1. Prefer `user.progress[requirementId].counts[dojoCohort]`
2. Else use `user.progress[requirementId].counts.ALL_COHORTS`
3. Else use `requirement.startCount`

`newCount = previousCount + countIncrement`

## CORS
- `OPTIONS /user/progress/v3` returns allow-origin `*` and includes authorization/content-type.
- Browser direct calls are possible, but DojoTap uses backend proxy to keep token out of frontend storage.

## Non-v1 Endpoint (Observed, Not Used)
- `POST /user/progress/timeline/v2` supports deletion workflows (seen in Bruno examples).
- Explicitly out of scope for v1.

## API Testing Volume Performed (2026-02-19)
- Repeated smoke checks: `20` loops, each loop called:
  - `GET /user`
  - `GET /requirements/ALL_COHORTS?scoreboardOnly=false`
- Total smoke GET calls: `40`
- Additional manual endpoint probes and contract checks were performed during implementation.
