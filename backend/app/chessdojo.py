from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException

from .config import Settings
from .models import BootstrapResponse, TaskItem, UserInfo


class ChessDojoClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._settings.normalized_bearer_token()}"}

    async def fetch_user(self) -> dict[str, Any]:
        return await self._get_json("/user")

    async def fetch_requirements(self, scoreboard_only: bool = False) -> list[dict[str, Any]]:
        params = {"scoreboardOnly": str(scoreboard_only).lower()}
        payload = await self._get_json("/requirements/ALL_COHORTS", params=params)
        return payload.get("requirements", [])

    async def post_progress(self, payload: dict[str, Any]) -> Any:
        return await self._post_json("/user/progress/v3", payload)

    async def _get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.chessdojo_base_url,
                timeout=self._settings.request_timeout_seconds,
            ) as client:
                response = await client.get(path, headers=self._headers, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail=(
                        "ChessDojo unauthorized. Refresh your bearer token and set "
                        "CHESSDOJO_BEARER_TOKEN in .env (raw token or 'Bearer <token>' "
                        "both supported). Then restart the backend."
                    ),
                ) from exc
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"ChessDojo GET {path} failed: {exc.response.text[:300]}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"ChessDojo GET {path} network error: {exc}",
            ) from exc

    async def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.chessdojo_base_url,
                timeout=self._settings.request_timeout_seconds,
            ) as client:
                response = await client.post(path, headers=self._headers, json=payload)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return response.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail=(
                        "ChessDojo unauthorized. Refresh your bearer token and set "
                        "CHESSDOJO_BEARER_TOKEN in .env (raw token or 'Bearer <token>' "
                        "both supported). Then restart the backend."
                    ),
                ) from exc
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"ChessDojo POST {path} failed: {exc.response.text[:300]}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"ChessDojo POST {path} network error: {exc}",
            ) from exc


def _to_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def normalize_counts(raw_counts: Any) -> dict[str, int]:
    if not isinstance(raw_counts, dict):
        return {}
    return {str(key): _to_int(value) for key, value in raw_counts.items()}


def resolve_previous_count(
    progress_entry: dict[str, Any] | None, cohort: str, start_count: int
) -> int:
    counts = normalize_counts((progress_entry or {}).get("counts", {}))
    if cohort in counts:
        return counts[cohort]
    if "ALL_COHORTS" in counts:
        return counts["ALL_COHORTS"]
    return start_count


def resolve_target_count(requirement: dict[str, Any], cohort: str) -> int | None:
    counts = normalize_counts(requirement.get("counts", {}))
    if cohort in counts:
        return counts[cohort]
    return None


def format_bootstrap(
    user_payload: dict[str, Any], requirements_payload: list[dict[str, Any]]
) -> BootstrapResponse:
    cohort = str(user_payload.get("dojoCohort", ""))
    progress_map = user_payload.get("progress", {})
    if not isinstance(progress_map, dict):
        progress_map = {}

    tasks: list[TaskItem] = []
    cohort_set: set[str] = set()

    for req in requirements_payload:
        req_id = str(req.get("id", ""))
        if not req_id:
            continue

        counts = normalize_counts(req.get("counts", {}))
        cohort_set.update(key for key in counts if key != "ALL_COHORTS")
        start_count = _to_int(req.get("startCount", 0))
        current_count = resolve_previous_count(progress_map.get(req_id), cohort, start_count)
        tasks.append(
            TaskItem(
                id=req_id,
                name=str(req.get("name", "")),
                category=str(req.get("category", "")),
                counts=counts,
                start_count=start_count,
                progress_bar_suffix=str(req.get("progressBarSuffix", "")),
                scoreboard_display=str(req.get("scoreboardDisplay", "")),
                number_of_cohorts=_to_int(req.get("numberOfCohorts", 0)),
                sort_priority=str(req.get("sortPriority", "")),
                current_count=current_count,
                target_count=resolve_target_count(req, cohort),
            )
        )

    if cohort:
        cohort_set.add(cohort)

    return BootstrapResponse(
        user=UserInfo(
            display_name=str(user_payload.get("displayName", "")),
            dojo_cohort=cohort,
        ),
        tasks=sorted(tasks, key=lambda task: (task.category, task.sort_priority, task.name)),
        progress_by_requirement_id={
            str(key): value
            for key, value in progress_map.items()
            if isinstance(value, dict)
        },
        pinned_task_ids=[str(item) for item in user_payload.get("pinnedTasks", [])],
        available_cohorts=sorted(
            cohort_set,
            key=_cohort_sort_key,
        ),
        default_filters={"cohort": cohort, "category": "ALL", "search": ""},
    )


def _cohort_sort_key(cohort: str) -> tuple[int, str]:
    if cohort.endswith("+"):
        return (_to_int(cohort[:-1], fallback=9999), cohort)
    if "-" in cohort:
        left, _ = cohort.split("-", 1)
        return (_to_int(left, fallback=9999), cohort)
    return (9999, cohort)


def build_progress_payload(
    user_payload: dict[str, Any],
    requirement: dict[str, Any],
    count_increment: int,
    minutes_spent: int,
) -> dict[str, Any]:
    cohort = str(user_payload.get("dojoCohort", ""))
    requirement_id = str(requirement.get("id", ""))
    start_count = _to_int(requirement.get("startCount", 0))
    progress_map = user_payload.get("progress", {})
    progress_entry = progress_map.get(requirement_id) if isinstance(progress_map, dict) else {}
    previous_count = resolve_previous_count(progress_entry, cohort, start_count)
    date_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    return {
        "cohort": cohort,
        "requirementId": requirement_id,
        "previousCount": previous_count,
        "newCount": previous_count + count_increment,
        "incrementalMinutesSpent": minutes_spent,
        "date": date_iso,
        "notes": "",
    }
