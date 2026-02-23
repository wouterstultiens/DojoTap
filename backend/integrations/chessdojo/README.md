# ChessDojo CLI Automation

Standalone scripts for automation flows outside the FastAPI web app.

## Scripts

- `fetch_bearer_token.py`: resolve a usable bearer token
- `log_progress.py`: submit time-only or count+time progress by task name
- `get_progress.py`: fetch full progress timeline entries for a task (Bruno `Get Progress` endpoint)

## Fetch bearer token

```powershell
python -m backend.integrations.chessdojo.fetch_bearer_token --format bearer
```

Optional login (persists refresh token by default):

```powershell
python -m backend.integrations.chessdojo.fetch_bearer_token `
  --username "you@example.com" `
  --password "your-password" `
  --format json
```

Credential env vars are supported:
- `CHESSDOJO_USERNAME`
- `CHESSDOJO_PASSWORD`

## Log progress by task name

Time-only example (`count=0`):

```powershell
python -m backend.integrations.chessdojo.log_progress `
  --task "ChessTempo Simple Tactics" `
  --minutes 20
```

Count + time example:

```powershell
python -m backend.integrations.chessdojo.log_progress `
  --task "Polgar 5334 Problems, 1100-1200, all by themes" `
  --count 12 `
  --minutes 45
```

Dry-run payload preview:

```powershell
python -m backend.integrations.chessdojo.log_progress `
  --task "Study Preventing Blunders in Chess" `
  --count 4 `
  --minutes 30 `
  --dry-run
```

## Get full progress for a task

Uses:
- `GET /public/user/{user_id}/timeline` (same endpoint as `bruno/ChessDojo/Get Progress.yml`)

By task name:

```powershell
python -m backend.integrations.chessdojo.get_progress `
  --task "ChessTempo Simple Tactics"
```

By task id:

```powershell
python -m backend.integrations.chessdojo.get_progress `
  --task-id "7d1d3478-7b9b-4155-9896-a2b1408357e8"
```

Optional:
- `--limit 20` to cap returned entries
- `--user-id <id>` to inspect another public profile timeline
- `--include-unfiltered` to include total raw timeline entry count
