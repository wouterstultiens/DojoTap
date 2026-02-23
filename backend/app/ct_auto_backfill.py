from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.config import Settings
from backend.integrations.chesstempo.fetch_attempts_csv import DEFAULT_STATS_URL
from backend.integrations.chesstempo.log_unlogged_days import (
    DEFAULT_TASK_NAME,
    _default_output_path,
    _run as run_log_unlogged_days,
)

_AUTO_BACKFILL_LOCK = asyncio.Lock()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _iso_now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _today_iso_in_timezone(timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date().isoformat()


def _default_storage_state_path() -> Path:
    if os.name == "nt":
        return Path.home() / ".dojotap" / "ct_storage_state.b64"
    return Path("/tmp/chesstempo/storage_state.b64")


def _resolve_storage_state_path() -> Path:
    raw = os.environ.get("CT_STORAGE_STATE_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _default_storage_state_path()


def _resolve_storage_state_b64() -> tuple[str | None, str]:
    storage_path = _resolve_storage_state_path()
    try:
        value = storage_path.read_text(encoding="utf-8").strip()
        if value:
            return value, "file"
    except OSError:
        pass

    env_value = os.environ.get("CT_STORAGE_STATE_B64", "").strip()
    if env_value:
        return env_value, "env"
    return None, "none"


def _build_args(*, settings: Settings, username: str, password: str) -> argparse.Namespace:
    timezone_name = os.environ.get("CT_TIMEZONE", "Europe/Amsterdam")
    lookback_days = int(os.environ.get("CT_LOOKBACK_DAYS", "30"))
    storage_state_b64, _ = _resolve_storage_state_b64()
    storage_state_path = _resolve_storage_state_path()
    return argparse.Namespace(
        task=DEFAULT_TASK_NAME,
        timezone=timezone_name,
        skip_current_day=True,
        max_days=0,
        lookback_days=lookback_days,
        dry_run=False,
        stats_url=os.environ.get("CT_STATS_URL", DEFAULT_STATS_URL),
        output=os.environ.get("CT_OUTPUT", _default_output_path()),
        summary_output=str(settings.resolved_ct_auto_backfill_summary_path()),
        profile_dir=str(Path(".ct_browser_profile")),
        ct_username=os.environ.get("CT_USERNAME"),
        ct_password=os.environ.get("CT_PASSWORD"),
        headless=True,
        storage_state_b64=storage_state_b64,
        storage_state_output=str(storage_state_path),
        print_storage_state=False,
        init_session=False,
        timeout=60,
        dojo_username=username,
        dojo_password=password,
        persist_refresh_token=True,
        force_refresh=False,
        no_prompt=True,
        emit_result_stdout=False,
    )


async def _run_backfill_job(
    *,
    settings: Settings,
    username: str,
    password: str,
    today_iso: str,
) -> None:
    state_path = settings.resolved_ct_auto_backfill_state_path()
    summary_path = settings.resolved_ct_auto_backfill_summary_path()
    started_at = _iso_now_utc()
    _, storage_state_source = _resolve_storage_state_b64()
    storage_state_path = _resolve_storage_state_path()
    try:
        args = _build_args(settings=settings, username=username, password=password)
        await run_log_unlogged_days(args)
        summary_payload = _load_json(summary_path)
        async with _AUTO_BACKFILL_LOCK:
            state = _load_json(state_path)
            state.update(
                {
                    "last_attempt_day": today_iso,
                    "last_attempt_at": started_at,
                    "last_completed_at": _iso_now_utc(),
                    "last_status": "success" if bool(summary_payload.get("ok")) else "failed",
                    "last_summary_path": str(summary_path),
                }
            )
            _write_json(state_path, state)
        print(
            json.dumps(
                {
                    "ct_auto_backfill": True,
                    "status": "success",
                    "day": today_iso,
                    "summary_path": str(summary_path),
                    "storage_state_source": storage_state_source,
                    "storage_state_path": str(storage_state_path),
                },
                ensure_ascii=True,
            ),
            file=sys.stderr,
        )
    except Exception as exc:
        failure_payload = {
            "ok": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "traceback": "".join(traceback.format_exception(exc)),
            "trigger": "login_auto_backfill",
            "started_at": started_at,
            "failed_at": _iso_now_utc(),
            "storage_state_source": storage_state_source,
            "storage_state_path": str(storage_state_path),
        }
        _write_json(summary_path, failure_payload)
        async with _AUTO_BACKFILL_LOCK:
            state = _load_json(state_path)
            state.update(
                {
                    "last_attempt_day": today_iso,
                    "last_attempt_at": started_at,
                    "last_completed_at": _iso_now_utc(),
                    "last_status": "failed",
                    "last_summary_path": str(summary_path),
                    "last_error": str(exc),
                }
            )
            _write_json(state_path, state)
        print(json.dumps(failure_payload, ensure_ascii=True), file=sys.stderr)


async def maybe_schedule_on_login(
    *,
    settings: Settings,
    username: str,
    password: str,
) -> dict[str, Any]:
    if not settings.ct_auto_backfill_on_login:
        result = {"scheduled": False, "reason": "disabled"}
        print(json.dumps({"ct_auto_backfill": True, **result}, ensure_ascii=True), file=sys.stderr)
        return result

    timezone_name = os.environ.get("CT_TIMEZONE", "Europe/Amsterdam")
    today_iso = _today_iso_in_timezone(timezone_name)
    state_path = settings.resolved_ct_auto_backfill_state_path()

    async with _AUTO_BACKFILL_LOCK:
        state = _load_json(state_path)
        if str(state.get("last_attempt_day", "")).strip() == today_iso:
            result = {"scheduled": False, "reason": "already_attempted_today", "day": today_iso}
            print(
                json.dumps({"ct_auto_backfill": True, **result}, ensure_ascii=True),
                file=sys.stderr,
            )
            return result

        state.update(
            {
                "last_attempt_day": today_iso,
                "last_attempt_at": _iso_now_utc(),
                "last_status": "scheduled",
            }
        )
        _write_json(state_path, state)

    asyncio.create_task(
        _run_backfill_job(
            settings=settings,
            username=username,
            password=password,
            today_iso=today_iso,
        )
    )
    result = {"scheduled": True, "reason": "first_login_today", "day": today_iso}
    print(json.dumps({"ct_auto_backfill": True, **result}, ensure_ascii=True), file=sys.stderr)
    return result
