# ChessTempo CSV Automation

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

## Render env vars

- `CT_STORAGE_STATE_B64` (primary auth path)
- `CT_STATS_URL` (stats page URL)
- Optional fallback: `CT_USERNAME`, `CT_PASSWORD`
- Optional file targets: `CT_OUTPUT`, `CT_SUMMARY_OUTPUT`
- Optional timezone: `CT_TIMEZONE` (default `Europe/Amsterdam`)

## Render cron command

```bash
python -m backend.integrations.chesstempo.fetch_attempts_csv \
  --headless \
  --stats-url "$CT_STATS_URL" \
  --output /tmp/chesstempo/download.csv \
  --summary-output /tmp/chesstempo/summary.json
```

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

