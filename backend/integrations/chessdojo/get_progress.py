from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx
from fastapi import HTTPException

from backend.app.chessdojo import ChessDojoClient, merge_requirements

from ._cli_common import (
    match_requirement_by_name,
    resolve_bearer_token,
    resolve_credentials,
    unwrap_error,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Get full task progress entries from "
            "/public/user/{user_id}/timeline."
        ),
    )
    parser.add_argument("--task", type=str, default=None, help="Task name (exact or unique partial).")
    parser.add_argument("--task-id", type=str, default=None, help="Requirement/task id.")
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="ChessDojo user id (defaults to current auth user username).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit returned entries after filtering (0 = all).",
    )
    parser.add_argument("--username", type=str, default=None, help="ChessDojo username/email.")
    parser.add_argument("--password", type=str, default=None, help="ChessDojo password.")
    parser.add_argument(
        "--persist-refresh-token",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist refresh token to local auth state (default: true).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh grant before using token.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Never prompt for missing credential field.",
    )
    parser.add_argument(
        "--include-unfiltered",
        action="store_true",
        help="Include `total_entries_unfiltered` in output.",
    )
    return parser


def _to_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _extract_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        raise ValueError("Timeline payload missing list field 'entries'.")
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    raise ValueError("Unexpected timeline payload type.")


def _summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not entries:
        return {
            "entries_count": 0,
            "total_minutes_logged": 0,
            "total_count_increment": 0,
            "first_date": None,
            "last_date": None,
            "latest_total_minutes_spent": None,
            "latest_new_count": None,
        }

    total_minutes = sum(_to_int(entry.get("minutesSpent")) for entry in entries)
    total_count_increment = sum(
        _to_int(entry.get("newCount")) - _to_int(entry.get("previousCount"))
        for entry in entries
    )
    dates = [str(entry.get("date", "")).strip() for entry in entries if str(entry.get("date", "")).strip()]
    first_date = min(dates) if dates else None
    last_date = max(dates) if dates else None

    latest = entries[0]
    return {
        "entries_count": len(entries),
        "total_minutes_logged": total_minutes,
        "total_count_increment": total_count_increment,
        "first_date": first_date,
        "last_date": last_date,
        "latest_total_minutes_spent": latest.get("totalMinutesSpent"),
        "latest_new_count": latest.get("newCount"),
    }


async def _load_requirements(client: ChessDojoClient) -> list[dict[str, Any]]:
    requirements_payload = await client.fetch_requirements(scoreboard_only=False)
    custom_access_payload: Any = {}
    try:
        custom_access_payload = await client.fetch_custom_access()
    except HTTPException as exc:
        if exc.status_code not in {403, 404}:
            raise
    return merge_requirements(requirements_payload, custom_access_payload)


async def _fetch_timeline(
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
    if args.limit < 0:
        raise ValueError("--limit must be >= 0.")
    if not args.task and not args.task_id:
        raise ValueError("Provide either --task or --task-id.")

    username, password = resolve_credentials(
        username_arg=args.username,
        password_arg=args.password,
        no_prompt=args.no_prompt,
    )
    settings, _, token = await resolve_bearer_token(
        username=username,
        password=password,
        persist_refresh_token=bool(args.persist_refresh_token),
        force_refresh=bool(args.force_refresh),
    )
    client = ChessDojoClient(settings=settings, bearer_token=token)
    user_payload = await client.fetch_user()

    user_id = str(args.user_id or user_payload.get("username") or "").strip()
    if not user_id:
        raise ValueError("Could not determine user id. Provide --user-id explicitly.")

    requirement: dict[str, Any] | None = None
    target_requirement_id = str(args.task_id or "").strip()
    if not target_requirement_id:
        requirements = await _load_requirements(client)
        requirement, _ = match_requirement_by_name(requirements, str(args.task))
        target_requirement_id = str(requirement.get("id", "")).strip()

    if not target_requirement_id:
        raise ValueError("Could not resolve requirement id.")

    all_entries = await _fetch_timeline(
        base_url=settings.chessdojo_base_url,
        timeout_seconds=settings.request_timeout_seconds,
        bearer_token=token,
        user_id=user_id,
    )
    filtered_entries_all = [
        entry
        for entry in all_entries
        if str(entry.get("requirementId", "")).strip() == target_requirement_id
    ]
    filtered_entries = filtered_entries_all
    if args.limit > 0:
        filtered_entries = filtered_entries[: args.limit]

    if requirement is None and filtered_entries:
        sample = filtered_entries[0]
        requirement = {
            "id": sample.get("requirementId", target_requirement_id),
            "name": sample.get("requirementName", ""),
            "category": sample.get("requirementCategory", ""),
            "isCustomRequirement": bool(sample.get("isCustomRequirement", False)),
        }
    elif requirement is None:
        requirement = {
            "id": target_requirement_id,
            "name": "",
            "category": "",
            "isCustomRequirement": False,
        }

    result: dict[str, Any] = {
        "ok": True,
        "source": "/public/user/{user_id}/timeline",
        "user_id": user_id,
        "task": {
            "id": str(requirement.get("id", "")),
            "name": str(requirement.get("name", "")),
            "category": str(requirement.get("category", "")),
            "is_custom_requirement": bool(requirement.get("isCustomRequirement", False)),
        },
        "summary": _summarize(filtered_entries_all),
        "entries_returned": len(filtered_entries),
        "entries": filtered_entries,
    }
    if args.include_unfiltered:
        result["total_entries_unfiltered"] = len(all_entries)

    print(json.dumps(result, ensure_ascii=True))
    return 0


def main() -> None:
    args = _build_parser().parse_args()
    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        message = unwrap_error(exc)
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=True), file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
