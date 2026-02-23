from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from fastapi import HTTPException

from backend.app.chessdojo import (
    ChessDojoClient,
    build_progress_payload,
    merge_requirements,
)

from ._cli_common import (
    match_requirement_by_name,
    resolve_bearer_token,
    resolve_credentials,
    unwrap_error,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Submit ChessDojo progress by task name. "
            "Use --count 0 for time-only logs."
        ),
    )
    parser.add_argument("--task", required=True, help="Task name (exact or unique partial).")
    parser.add_argument(
        "--minutes",
        required=True,
        type=int,
        help="Minutes spent (>=1).",
    )
    parser.add_argument(
        "--count",
        default=0,
        type=int,
        help="Count increment (>=0). Default: 0 (time-only).",
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
        "--dry-run",
        action="store_true",
        help="Print resolved payload without sending it upstream.",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.minutes < 1:
        raise ValueError("--minutes must be >= 1.")
    if args.count < 0:
        raise ValueError("--count must be >= 0.")


async def _load_requirements(client: ChessDojoClient) -> list[dict[str, Any]]:
    requirements_payload = await client.fetch_requirements(scoreboard_only=False)
    custom_access_payload: Any = {}
    try:
        custom_access_payload = await client.fetch_custom_access()
    except HTTPException as exc:
        if exc.status_code not in {403, 404}:
            raise
    return merge_requirements(requirements_payload, custom_access_payload)


async def _run(args: argparse.Namespace) -> int:
    _validate_args(args)

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
    merged_requirements = await _load_requirements(client)
    requirement, matched_by = match_requirement_by_name(merged_requirements, args.task)

    payload = build_progress_payload(
        user_payload=user_payload,
        requirement=requirement,
        count_increment=args.count,
        minutes_spent=args.minutes,
    )

    if args.dry_run:
        result: dict[str, Any] = {
            "ok": True,
            "submitted": False,
            "matched_by": matched_by,
            "task": {
                "id": str(requirement.get("id", "")),
                "name": str(requirement.get("name", "")),
                "category": str(requirement.get("category", "")),
            },
            "submitted_payload": payload,
        }
        print(json.dumps(result, ensure_ascii=True))
        return 0

    upstream_response = await client.post_progress(payload)
    result = {
        "ok": True,
        "submitted": True,
        "matched_by": matched_by,
        "task": {
            "id": str(requirement.get("id", "")),
            "name": str(requirement.get("name", "")),
            "category": str(requirement.get("category", "")),
        },
        "submitted_payload": payload,
        "upstream_response": upstream_response,
    }
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

