from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ._cli_common import resolve_bearer_token, resolve_credentials, unwrap_error


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch a ChessDojo bearer token using DojoTap local auth flow.",
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
        help="Force refresh grant before returning token.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Never prompt for missing credential field.",
    )
    parser.add_argument(
        "--format",
        choices=("raw", "bearer", "json"),
        default="raw",
        help="Output format (default: raw).",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    username, password = resolve_credentials(
        username_arg=args.username,
        password_arg=args.password,
        no_prompt=args.no_prompt,
    )
    _, auth_manager, token = await resolve_bearer_token(
        username=username,
        password=password,
        persist_refresh_token=bool(args.persist_refresh_token),
        force_refresh=bool(args.force_refresh),
    )

    if args.format == "raw":
        print(token)
    elif args.format == "bearer":
        print(f"Bearer {token}")
    else:
        print(
            json.dumps(
                {
                    "ok": True,
                    "token": token,
                    "authorization_header": f"Bearer {token}",
                    "status": auth_manager.status(),
                },
                ensure_ascii=True,
            )
        )
    return 0


def main() -> None:
    args = _build_parser().parse_args()
    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        message = unwrap_error(exc)
        if args.format == "json":
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=True), file=sys.stderr)
        else:
            print(f"Error: {message}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

