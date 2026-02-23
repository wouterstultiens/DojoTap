# ChessTempo Automation

This integration is intentionally separate from the DojoTap app flow.

## Install

```powershell
pip install -r backend/integrations/chesstempo/requirements.txt
python -m playwright install chromium
```

## One-time local session bootstrap

```powershell
python -m backend.integrations.chesstempo.fetch_attempts_csv `
  --stats-url "https://chesstempo.com/stats/woutie70/" `
  --init-session `
  --print-storage-state
```

Copy `CT_STORAGE_STATE_B64=...` from terminal output into Render env vars.

## Local run (headless)

```powershell
$env:CT_STORAGE_STATE_B64="<value>"
python -m backend.integrations.chesstempo.fetch_attempts_csv --headless
```

## Backfill unlogged ChessDojo days

Logs missing historical days for task `ChessTempo Simple Tactics` by combining:
- ChessTempo daily CSV summary
- ChessDojo task timeline (`/public/user/{user_id}/timeline`)
- ChessDojo progress submit (`POST /user/progress/v3`)

Current day is skipped by default.
Lookback window is 30 days by default.

```powershell
python -m backend.integrations.chesstempo.log_unlogged_days `
  --headless `
  --stats-url "$CT_STATS_URL" `
  --dry-run
```

Real submit:

```powershell
python -m backend.integrations.chesstempo.log_unlogged_days `
  --headless `
  --stats-url "$CT_STATS_URL" `
  --lookback-days 30
```

## Render env vars

- `CT_STORAGE_STATE_B64` (primary auth path)
- `CT_STORAGE_STATE_PATH` (file path for persisted/refreshed storage-state b64; defaults to `/tmp/chesstempo/storage_state.b64` on Render)
- `CT_STATS_URL` (stats page URL)
- Optional fallback: `CT_USERNAME`, `CT_PASSWORD`
- Optional ChessDojo login: `CHESSDOJO_USERNAME`, `CHESSDOJO_PASSWORD`
- Optional file targets: `CT_OUTPUT`, `CT_SUMMARY_OUTPUT`
- Optional timezone: `CT_TIMEZONE` (default `Europe/Amsterdam`)

For API login-triggered daily runs (`/api/auth/login` first login of day):
- `CT_AUTO_BACKFILL_ON_LOGIN=true`
- Optional state/summary targets:
  - `CT_AUTO_BACKFILL_STATE_PATH` (default `/tmp/dojotap-ct-auto-backfill-state.json`)
  - `CT_AUTO_BACKFILL_SUMMARY_PATH` (default `/tmp/chesstempo/backfill-on-login.json`)
- Login-triggered runs auto-refresh storage state into `CT_STORAGE_STATE_PATH` so expired session state can self-heal.

## Render cron command

```bash
python -m backend.integrations.chesstempo.log_unlogged_days \
  --headless \
  --stats-url "$CT_STATS_URL" \
  --summary-output /tmp/chesstempo/backfill.json \
  --storage-state-output "$CT_STORAGE_STATE_PATH" \
  --no-prompt
```

`/tmp/chesstempo/backfill.json` is written on both success and failure.
On failure it contains `ok: false`, `error`, and `traceback` for diagnostics.

## JSON output contract

The script prints one JSON object to stdout on success:

```json
{
  "ok": true,
  "source_csv": "/tmp/chesstempo/download.csv",
  "timezone": "Europe/Amsterdam",
  "rows_total": 0,
  "rows_used": 0,
  "rows_skipped": 0,
  "daily": [
    {
      "date": "2026-02-20",
      "exercises": 0,
      "adjusted_minutes": 0
    }
  ]
}
```

## Session expiry behavior

If runs start failing later, the saved web session likely expired:
1. rerun `--init-session --print-storage-state` locally,
2. rotate `CT_STORAGE_STATE_B64` in Render.

