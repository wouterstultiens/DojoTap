from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException

from backend.app.chessdojo import ChessDojoClient, build_progress_payload, merge_requirements
from backend.integrations.chessdojo._cli_common import (
    match_requirement_by_name,
    resolve_bearer_token,
    resolve_credentials,
    unwrap_error,
)

from .fetch_attempts_csv import DEFAULT_STATS_URL, fetch_csv_bytes, summarize_csv

DEFAULT_TASK_NAME = "ChessTempo Simple Tactics"


def _default_output_path() -> str:
    if os.name == "nt":
        return str(Path.home() / "Downloads" / "download.csv")
    return "/tmp/chesstempo/download.csv"


def _to_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _write_summary(path_value: str | None, payload: dict[str, Any]) -> None:
    if not path_value:
        return
    try:
        summary_path = Path(path_value).expanduser().resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def parse_timestamp(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result


def to_local_day(value: str, tz: ZoneInfo) -> str | None:
    text = value.strip()
    if not text:
        return None
    try:
        return parse_timestamp(text).astimezone(tz).date().isoformat()
    except ValueError:
        return None


def extract_logged_days(entries: list[dict[str, Any]], tz: ZoneInfo) -> set[str]:
    days: set[str] = set()
    for entry in entries:
        for field in ("date", "createdAt"):
            day = to_local_day(str(entry.get(field, "")), tz)
            if day:
                days.add(day)
                break
    return days


def build_backfill_date(day_iso: str, tz: ZoneInfo) -> str:
    target_day = date.fromisoformat(day_iso)
    local_noon = datetime.combine(target_day, time(hour=12, minute=0), tzinfo=tz)
    return local_noon.astimezone(UTC).isoformat().replace("+00:00", "Z")


def select_unlogged_days(
    *,
    daily_rows: list[dict[str, Any]],
    logged_days: set[str],
    today_iso: str,
    skip_current_day: bool,
    earliest_day_iso: str | None,
    max_days: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    earliest_day: date | None = None
    if earliest_day_iso:
        earliest_day = date.fromisoformat(earliest_day_iso)

    for row in daily_rows:
        day_iso = str(row.get("date", "")).strip()
        if not day_iso:
            continue
        try:
            day_value = date.fromisoformat(day_iso)
        except ValueError:
            continue

        minutes = _to_int(row.get("adjusted_minutes"), fallback=0)
        if minutes <= 0:
            continue
        if earliest_day is not None and day_value < earliest_day:
            continue
        if skip_current_day and day_iso == today_iso:
            continue
        if day_iso in logged_days:
            continue

        selected.append(
            {
                "date": day_iso,
                "adjusted_minutes": minutes,
                "exercises": _to_int(row.get("exercises"), fallback=0),
            }
        )

    selected.sort(key=lambda item: item["date"])
    if max_days > 0:
        return selected[:max_days]
    return selected


def _extract_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        raise ValueError("Timeline payload missing list field 'entries'.")
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    raise ValueError("Unexpected timeline payload type.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill ChessDojo logs for unlogged ChessTempo day totals "
            "(default task: ChessTempo Simple Tactics)."
        ),
    )
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK_NAME,
        help=f"ChessDojo task name. Default: {DEFAULT_TASK_NAME!r}.",
    )
    parser.add_argument(
        "--timezone",
        default=os.environ.get("CT_TIMEZONE", "Europe/Amsterdam"),
        help="IANA timezone used for day matching and current-day skip.",
    )
    parser.add_argument(
        "--skip-current-day",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip logging for today's date in selected timezone (default: true).",
    )
    parser.add_argument(
        "--max-days",
        default=0,
        type=int,
        help="Limit number of backfilled days per run (0 = no limit).",
    )
    parser.add_argument(
        "--lookback-days",
        default=int(os.environ.get("CT_LOOKBACK_DAYS", "30")),
        type=int,
        help="Only consider days within this many days back from today (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and print planned submissions without posting.",
    )

    parser.add_argument(
        "--stats-url",
        default=os.environ.get("CT_STATS_URL", DEFAULT_STATS_URL),
        help="ChessTempo stats URL containing the attempts table.",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("CT_OUTPUT", _default_output_path()),
        help="Path where downloaded CSV is saved.",
    )
    parser.add_argument(
        "--summary-output",
        default=os.environ.get("CT_SUMMARY_OUTPUT"),
        help="Optional path to write run JSON summary output.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(Path(".ct_browser_profile")),
        help="Playwright profile dir (for local persistent login sessions).",
    )
    parser.add_argument(
        "--ct-username",
        default=os.environ.get("CT_USERNAME"),
        help="ChessTempo username/email.",
    )
    parser.add_argument(
        "--ct-password",
        default=os.environ.get("CT_PASSWORD"),
        help="ChessTempo password.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run ChessTempo browser flow headless.",
    )
    parser.add_argument(
        "--storage-state-b64",
        default=os.environ.get("CT_STORAGE_STATE_B64"),
        help="Base64 Playwright storage_state JSON for headless/cloud runs.",
    )
    parser.add_argument(
        "--print-storage-state",
        action="store_true",
        help="Print CT_STORAGE_STATE_B64 after successful ChessTempo fetch.",
    )
    parser.add_argument(
        "--init-session",
        action="store_true",
        help="Open headed browser for manual ChessTempo login bootstrap.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for ChessTempo browser actions.",
    )

    parser.add_argument("--dojo-username", type=str, default=None, help="ChessDojo username/email.")
    parser.add_argument("--dojo-password", type=str, default=None, help="ChessDojo password.")
    parser.add_argument(
        "--persist-refresh-token",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist ChessDojo refresh token to local auth state (default: true).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force ChessDojo refresh grant before token use.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Never prompt for missing ChessDojo credential field.",
    )
    return parser


def _to_ct_fetch_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        stats_url=args.stats_url,
        output=args.output,
        summary_output=None,
        timezone=args.timezone,
        profile_dir=args.profile_dir,
        username=args.ct_username,
        password=args.ct_password,
        headless=bool(args.headless),
        storage_state_b64=args.storage_state_b64,
        print_storage_state=bool(args.print_storage_state),
        init_session=bool(args.init_session),
        timeout=args.timeout,
    )


async def _load_requirements(client: ChessDojoClient) -> list[dict[str, Any]]:
    requirements_payload = await client.fetch_requirements(scoreboard_only=False)
    custom_access_payload: Any = {}
    try:
        custom_access_payload = await client.fetch_custom_access()
    except HTTPException as exc:
        if exc.status_code not in {403, 404}:
            raise
    return merge_requirements(requirements_payload, custom_access_payload)


async def _fetch_timeline_entries(
    *,
    base_url: str,
    timeout_seconds: float,
    bearer_token: str,
    user_id: str,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout_seconds,
    ) as raw_client:
        response = await raw_client.get(
            f"/public/user/{user_id}/timeline",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"ChessDojo GET /public/user/{user_id}/timeline failed: {exc.response.text[:300]}",
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Timeline endpoint returned non-JSON payload.") from exc
    return _extract_entries(payload)


async def _run(args: argparse.Namespace) -> int:
    if args.max_days < 0:
        raise ValueError("--max-days must be >= 0.")
    if args.lookback_days < 1:
        raise ValueError("--lookback-days must be >= 1.")
    try:
        tz = ZoneInfo(args.timezone)
    except Exception as exc:
        raise ValueError(
            f"Invalid timezone or missing tzdata for: {args.timezone}. Install tzdata if needed."
        ) from exc

    csv_bytes, source_csv = await asyncio.to_thread(
        fetch_csv_bytes,
        _to_ct_fetch_args(args),
    )
    ct_summary = summarize_csv(csv_bytes, args.timezone)
    daily_rows = [
        row for row in ct_summary.get("daily", []) if isinstance(row, dict)
    ]

    dojo_username, dojo_password = resolve_credentials(
        username_arg=args.dojo_username,
        password_arg=args.dojo_password,
        no_prompt=args.no_prompt,
    )
    settings, _, token = await resolve_bearer_token(
        username=dojo_username,
        password=dojo_password,
        persist_refresh_token=bool(args.persist_refresh_token),
        force_refresh=bool(args.force_refresh),
    )
    client = ChessDojoClient(settings=settings, bearer_token=token)
    user_payload = await client.fetch_user()

    user_id = str(user_payload.get("username", "")).strip()
    if not user_id:
        raise ValueError("Could not resolve ChessDojo user id from /user payload.")

    requirements = await _load_requirements(client)
    requirement, matched_by = match_requirement_by_name(requirements, args.task)
    requirement_id = str(requirement.get("id", "")).strip()
    if not requirement_id:
        raise ValueError("Resolved task is missing requirement id.")

    timeline_entries = await _fetch_timeline_entries(
        base_url=settings.chessdojo_base_url,
        timeout_seconds=settings.request_timeout_seconds,
        bearer_token=token,
        user_id=user_id,
    )
    task_entries = [
        entry
        for entry in timeline_entries
        if str(entry.get("requirementId", "")).strip() == requirement_id
    ]
    logged_days = extract_logged_days(task_entries, tz)
    today_local = datetime.now(tz).date()
    today_iso = today_local.isoformat()
    earliest_day_iso = (today_local - timedelta(days=args.lookback_days)).isoformat()
    missing_rows = select_unlogged_days(
        daily_rows=daily_rows,
        logged_days=logged_days,
        today_iso=today_iso,
        skip_current_day=bool(args.skip_current_day),
        earliest_day_iso=earliest_day_iso,
        max_days=args.max_days,
    )

    submissions: list[dict[str, Any]] = []
    for row in missing_rows:
        day_iso = str(row["date"])
        minutes = _to_int(row["adjusted_minutes"], fallback=0)
        payload = build_progress_payload(
            user_payload=user_payload,
            requirement=requirement,
            count_increment=0,
            minutes_spent=minutes,
        )
        payload["date"] = build_backfill_date(day_iso, tz)

        submission: dict[str, Any] = {
            "date": day_iso,
            "minutes": minutes,
            "exercises": _to_int(row.get("exercises"), fallback=0),
            "payload_date": payload["date"],
            "submitted": not args.dry_run,
        }
        if not args.dry_run:
            submission["upstream_response"] = await client.post_progress(payload)
        submissions.append(submission)

    result: dict[str, Any] = {
        "ok": True,
        "task": {
            "id": requirement_id,
            "name": str(requirement.get("name", "")),
            "category": str(requirement.get("category", "")),
            "matched_by": matched_by,
        },
        "timezone": args.timezone,
        "source_csv": source_csv,
        "rows_total": ct_summary.get("rows_total", 0),
        "rows_used": ct_summary.get("rows_used", 0),
        "rows_skipped": ct_summary.get("rows_skipped", 0),
        "days_with_chesstempo_activity": len(
            [row for row in daily_rows if _to_int(row.get("adjusted_minutes"), 0) > 0]
        ),
        "days_already_logged": len(logged_days),
        "skip_current_day": bool(args.skip_current_day),
        "today": today_iso,
        "lookback_days": args.lookback_days,
        "earliest_day_included": earliest_day_iso,
        "backfill_candidates": len(missing_rows),
        "submitted_entries": len(submissions),
        "dry_run": bool(args.dry_run),
        "submissions": submissions,
    }

    if args.summary_output:
        _write_summary(args.summary_output, result)

    print(json.dumps(result, ensure_ascii=True))
    return 0


def main() -> None:
    args = _build_parser().parse_args()
    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        message = unwrap_error(exc)
        error_payload: dict[str, Any] = {
            "ok": False,
            "error": message,
            "error_type": type(exc).__name__,
            "task": args.task,
            "timezone": args.timezone,
            "dry_run": bool(args.dry_run),
            "lookback_days": args.lookback_days,
            "traceback": "".join(traceback.format_exception(exc)),
        }
        _write_summary(args.summary_output, error_payload)
        print(json.dumps(error_payload, ensure_ascii=True), file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
