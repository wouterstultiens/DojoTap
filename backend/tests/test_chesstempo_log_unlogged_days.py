import json
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.integrations.chesstempo.log_unlogged_days import (
    _write_summary,
    build_backfill_date,
    extract_logged_days,
    select_unlogged_days,
)


def test_extract_logged_days_uses_timezone_day_conversion() -> None:
    entries = [
        {"date": "2026-02-20T23:30:00Z"},
        {"createdAt": "2026-02-18T11:15:00Z"},
        {"date": "bad-date"},
    ]
    days = extract_logged_days(entries, ZoneInfo("Europe/Amsterdam"))
    assert days == {"2026-02-21", "2026-02-18"}


def test_select_unlogged_days_skips_current_day_and_logged_days() -> None:
    daily_rows = [
        {"date": "2026-02-23", "adjusted_minutes": 5, "exercises": 8},
        {"date": "2026-02-22", "adjusted_minutes": 4, "exercises": 6},
        {"date": "2026-02-21", "adjusted_minutes": 0, "exercises": 3},
        {"date": "2026-02-20", "adjusted_minutes": 3, "exercises": 5},
    ]
    selected = select_unlogged_days(
        daily_rows=daily_rows,
        logged_days={"2026-02-22"},
        today_iso="2026-02-23",
        skip_current_day=True,
        earliest_day_iso=None,
        max_days=0,
    )
    assert selected == [
        {"date": "2026-02-20", "adjusted_minutes": 3, "exercises": 5},
    ]


def test_select_unlogged_days_honors_max_days_oldest_first() -> None:
    daily_rows = [
        {"date": "2026-02-24", "adjusted_minutes": 1, "exercises": 1},
        {"date": "2026-02-23", "adjusted_minutes": 1, "exercises": 1},
        {"date": "2026-02-22", "adjusted_minutes": 1, "exercises": 1},
    ]
    selected = select_unlogged_days(
        daily_rows=daily_rows,
        logged_days=set(),
        today_iso="2026-02-25",
        skip_current_day=True,
        earliest_day_iso=None,
        max_days=2,
    )
    assert selected == [
        {"date": "2026-02-22", "adjusted_minutes": 1, "exercises": 1},
        {"date": "2026-02-23", "adjusted_minutes": 1, "exercises": 1},
    ]


def test_build_backfill_date_uses_local_noon() -> None:
    iso = build_backfill_date("2026-02-20", ZoneInfo("Europe/Amsterdam"))
    assert iso == "2026-02-20T11:00:00Z"


def test_select_unlogged_days_applies_earliest_day_limit() -> None:
    daily_rows = [
        {"date": "2026-02-23", "adjusted_minutes": 2, "exercises": 2},
        {"date": "2026-02-22", "adjusted_minutes": 2, "exercises": 2},
        {"date": "2026-01-20", "adjusted_minutes": 2, "exercises": 2},
    ]
    selected = select_unlogged_days(
        daily_rows=daily_rows,
        logged_days=set(),
        today_iso="2026-02-24",
        skip_current_day=True,
        earliest_day_iso="2026-01-25",
        max_days=0,
    )
    assert selected == [
        {"date": "2026-02-22", "adjusted_minutes": 2, "exercises": 2},
        {"date": "2026-02-23", "adjusted_minutes": 2, "exercises": 2},
    ]


def test_write_summary_writes_json_file(tmp_path: Path) -> None:
    output_path = tmp_path / "result" / "summary.json"
    payload = {"ok": False, "error": "boom"}

    _write_summary(str(output_path), payload)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == payload
