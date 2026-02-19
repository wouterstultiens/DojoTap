from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Iterable

import httpx

BASE_URL = "https://g4shdaq6ug.execute-api.us-east-1.amazonaws.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Non-destructive ChessDojo API smoke checks."
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=20,
        help="How many repeated GET loops to run for stability testing.",
    )
    return parser.parse_args()


def _require_token() -> str:
    token = os.getenv("CHESSDOJO_BEARER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CHESSDOJO_BEARER_TOKEN is missing.")
    return token


def _validate_requirements_shape(payload: dict) -> None:
    reqs = payload.get("requirements")
    if not isinstance(reqs, list):
        raise RuntimeError("requirements payload missing requirements[]")
    if not reqs:
        raise RuntimeError("requirements list is empty")
    first = reqs[0]
    required_keys = {"id", "name", "category", "counts", "startCount"}
    missing = required_keys.difference(first.keys())
    if missing:
        raise RuntimeError(f"requirements item missing keys: {sorted(missing)}")


def _validate_user_shape(payload: dict) -> None:
    required_keys = {"dojoCohort", "progress", "pinnedTasks", "displayName"}
    missing = required_keys.difference(payload.keys())
    if missing:
        raise RuntimeError(f"user payload missing keys: {sorted(missing)}")
    if not isinstance(payload.get("progress"), dict):
        raise RuntimeError("user.progress is not a dict")
    if not isinstance(payload.get("pinnedTasks"), Iterable):
        raise RuntimeError("user.pinnedTasks is not iterable")


async def main() -> int:
    args = parse_args()
    token = _require_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as client:
        for index in range(args.loops):
            user_res = await client.get("/user", headers=headers)
            user_res.raise_for_status()
            user_json = user_res.json()
            _validate_user_shape(user_json)

            req_res = await client.get(
                "/requirements/ALL_COHORTS",
                params={"scoreboardOnly": "false"},
                headers=headers,
            )
            req_res.raise_for_status()
            req_json = req_res.json()
            _validate_requirements_shape(req_json)

            print(
                f"loop {index + 1:02d}/{args.loops}: "
                f"cohort={user_json['dojoCohort']} "
                f"requirements={len(req_json['requirements'])}"
            )

    print("smoke checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:  # pragma: no cover
        print(f"smoke check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

