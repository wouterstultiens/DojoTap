#!/usr/bin/env python
"""Download ChessTempo attempts CSV and emit per-day totals as JSON."""

from __future__ import annotations

import argparse
import base64
import contextlib
import csv
import io
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_STATS_URL = "https://chesstempo.com/stats/woutie70/"
DATE_COLUMN = "Date"
TIME_COLUMN_EXACT = 'Used <ct-icon name="timer"></ct-icon>'
DOWNLOAD_BUTTON_SELECTORS = [
    ".ct-stats-attempts-table-download-button",
    "span[title='Download Attempts']",
    "[aria-label='Download Attempts']",
]
USERNAME_SELECTORS = [
    "input[name='username']",
    "input[name='email']",
    "input[type='email']",
    "input[type='text']",
]
PASSWORD_SELECTORS = [
    "input[name='password']",
    "input[type='password']",
]
SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Log In')",
    "button:has-text('Sign In')",
]


def _default_output_path() -> str:
    if os.name == "nt":
        return str(Path.home() / "Downloads" / "download.csv")
    return "/tmp/chesstempo/download.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stats-url",
        default=os.environ.get("CT_STATS_URL", DEFAULT_STATS_URL),
        help="Stats page URL where the attempts table exists.",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("CT_OUTPUT", _default_output_path()),
        help="Path for saved CSV (default: CT_OUTPUT or platform default).",
    )
    parser.add_argument(
        "--summary-output",
        default=os.environ.get("CT_SUMMARY_OUTPUT"),
        help="Optional path to write JSON summary output.",
    )
    parser.add_argument(
        "--timezone",
        default=os.environ.get("CT_TIMEZONE", "Europe/Amsterdam"),
        help="IANA timezone name used for day grouping.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(Path(".ct_browser_profile")),
        help="Playwright user-data dir for persistent login sessions (local).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("CT_USERNAME"),
        help="ChessTempo username/email (or set CT_USERNAME).",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("CT_PASSWORD"),
        help="ChessTempo password (or set CT_PASSWORD).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless.",
    )
    parser.add_argument(
        "--storage-state-b64",
        default=os.environ.get("CT_STORAGE_STATE_B64"),
        help=(
            "Base64-encoded Playwright storage_state JSON. "
            "Use this for headless/Render when persistent profile is unavailable."
        ),
    )
    parser.add_argument(
        "--print-storage-state",
        action="store_true",
        help="Print CT_STORAGE_STATE_B64 after a successful run.",
    )
    parser.add_argument(
        "--init-session",
        action="store_true",
        help="Open headed browser, login manually once, then print CT_STORAGE_STATE_B64.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for page actions.",
    )
    return parser.parse_args()


def _require_playwright():
    try:
        from playwright.sync_api import TimeoutError as playwright_timeout_error
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install with:\n"
            "  pip install -r backend/integrations/chesstempo/requirements.txt\n"
            "  python -m playwright install chromium"
        ) from exc
    return sync_playwright, playwright_timeout_error


def first_visible(page, selectors: list[str], timeout_ms: int, timeout_error):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except timeout_error:
            continue
    return None


def looks_like_bot_challenge(page) -> bool:
    title = page.title().lower()
    if "just a moment" in title or "attention required" in title:
        return True
    body = page.content().lower()
    return "verify you are human" in body or "cf-challenge" in body


def decode_storage_state(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        raw = base64.b64decode(value.encode("utf-8"), validate=True).decode("utf-8")
        data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError("Invalid --storage-state-b64 / CT_STORAGE_STATE_B64 value.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Decoded storage state is not a JSON object.")
    return data


def encode_storage_state(value: dict[str, Any]) -> str:
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.b64encode(payload).decode("utf-8")


def maybe_login(page, args: argparse.Namespace, timeout_ms: int, timeout_error) -> None:
    if first_visible(page, DOWNLOAD_BUTTON_SELECTORS, 2_000, timeout_error) is not None:
        return

    if looks_like_bot_challenge(page):
        raise RuntimeError(
            "Blocked by anti-bot challenge page. "
            "Run once with --init-session locally and reuse CT_STORAGE_STATE_B64."
        )

    password_field = first_visible(page, PASSWORD_SELECTORS, 3_000, timeout_error)
    if password_field is None:
        return

    if args.username and args.password:
        username_field = first_visible(page, USERNAME_SELECTORS, 2_000, timeout_error)
        if username_field is not None:
            username_field.fill(args.username)
        password_field.fill(args.password)
        submit = first_visible(page, SUBMIT_SELECTORS, 2_000, timeout_error)
        if submit is not None:
            submit.click()
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except timeout_error:
                pass
            return

    if args.init_session or not args.headless:
        print(
            "Manual login required. Complete login in the browser window, then press Enter.",
            file=sys.stderr,
        )
        input()
        return

    raise RuntimeError(
        "Login is required but no credentials were provided. "
        "Use --username/--password (or CT_USERNAME/CT_PASSWORD), "
        "or run with --init-session locally and store CT_STORAGE_STATE_B64."
    )


def ensure_download_button(page, timeout_ms: int, timeout_error):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        button = first_visible(page, DOWNLOAD_BUTTON_SELECTORS, 1_500, timeout_error)
        if button is not None:
            return button
        if looks_like_bot_challenge(page):
            raise RuntimeError(
                "Bot challenge detected. "
                "This is common on fresh headless sessions from cloud IPs."
            )
        if first_visible(page, PASSWORD_SELECTORS, 500, timeout_error) is not None:
            raise RuntimeError("Still on login page; session/cookies are not authenticated.")
        page.wait_for_timeout(400)
    raise RuntimeError(
        "Could not find download button within timeout. "
        "Confirm stats URL, login state, and that attempts table is visible."
    )


def _parse_timestamp(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result


def resolve_time_column(fieldnames: list[str]) -> str:
    if TIME_COLUMN_EXACT in fieldnames:
        return TIME_COLUMN_EXACT
    for name in fieldnames:
        if "used" in name.lower():
            return name
    raise RuntimeError("CSV does not contain an attempts time column.")


def summarize_csv(csv_bytes: bytes, timezone_name: str) -> dict[str, Any]:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:
        raise RuntimeError(
            f"Invalid timezone or missing tzdata for: {timezone_name}. "
            "Install tzdata if running on Windows."
        ) from exc

    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    if DATE_COLUMN not in fieldnames:
        raise RuntimeError(f"CSV missing required column: {DATE_COLUMN}")
    time_column = resolve_time_column(fieldnames)

    exercises_by_day: dict[str, int] = defaultdict(int)
    adjusted_minutes_by_day: dict[str, int] = defaultdict(int)
    rows_total = 0
    rows_used = 0
    rows_skipped = 0

    for row in reader:
        rows_total += 1
        try:
            stamp = _parse_timestamp(str(row[DATE_COLUMN]))
            day = stamp.astimezone(tz).date().isoformat()
            seconds = float(str(row[time_column]))
            adjusted_minutes = int(round((min(seconds, 30.0) * 1.2) / 60.0, 0))
        except Exception:
            rows_skipped += 1
            continue

        exercises_by_day[day] += 1
        adjusted_minutes_by_day[day] += adjusted_minutes
        rows_used += 1

    daily = [
        {
            "date": day,
            "exercises": exercises_by_day[day],
            "adjusted_minutes": adjusted_minutes_by_day[day],
        }
        for day in sorted(exercises_by_day.keys(), reverse=True)
    ]

    return {
        "rows_total": rows_total,
        "rows_used": rows_used,
        "rows_skipped": rows_skipped,
        "daily": daily,
    }


def fetch_csv_bytes(args: argparse.Namespace) -> tuple[bytes, str]:
    if args.init_session:
        args.headless = False

    timeout_ms = args.timeout * 1000
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    storage_state = decode_storage_state(args.storage_state_b64)

    sync_playwright, timeout_error = _require_playwright()
    with sync_playwright() as playwright:
        use_persistent = (not args.headless) and (not storage_state)
        browser = None
        if use_persistent:
            profile_dir = Path(args.profile_dir).expanduser().resolve()
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                accept_downloads=True,
                channel="chromium",
                args=["--disable-dev-shm-usage"],
            )
        else:
            launch_args = ["--disable-dev-shm-usage"]
            if args.headless:
                launch_args.append("--no-sandbox")
            browser = playwright.chromium.launch(
                headless=args.headless,
                channel="chromium",
                args=launch_args,
            )
            context = browser.new_context(accept_downloads=True, storage_state=storage_state)

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(args.stats_url, wait_until="domcontentloaded", timeout=timeout_ms)

            maybe_login(page, args, timeout_ms, timeout_error)
            page.goto(args.stats_url, wait_until="domcontentloaded", timeout=timeout_ms)

            button = ensure_download_button(page, timeout_ms, timeout_error)
            with page.expect_download(timeout=timeout_ms) as download_info:
                button.click()
            download = download_info.value
            download.save_as(str(output_path))
            csv_bytes = output_path.read_bytes()

            if args.init_session or args.print_storage_state:
                print(
                    f"CT_STORAGE_STATE_B64={encode_storage_state(context.storage_state())}",
                    file=sys.stderr,
                )
            return csv_bytes, str(output_path)
        finally:
            with contextlib.suppress(Exception):
                context.close()
            if browser is not None:
                with contextlib.suppress(Exception):
                    browser.close()


def run(args: argparse.Namespace) -> int:
    csv_bytes, output_path = fetch_csv_bytes(args)
    summary = summarize_csv(csv_bytes, args.timezone)
    payload: dict[str, Any] = {
        "ok": True,
        "source_csv": output_path,
        "timezone": args.timezone,
        **summary,
    }

    if args.summary_output:
        summary_path = Path(args.summary_output).expanduser().resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(f"Wrote summary: {summary_path}", file=sys.stderr)

    print(f"Saved CSV: {output_path}", file=sys.stderr)
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
