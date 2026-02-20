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

    async def fetch_custom_access(self) -> dict[str, Any]:
        return await self._get_json("/user/access/v2")

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


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


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


def _first_non_empty_str(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _resolve_requirement_id(payload: dict[str, Any]) -> str:
    return _first_non_empty_str(payload, ["id", "requirementId", "requirement_id"])


def _resolve_requirement_name(payload: dict[str, Any]) -> str:
    return _first_non_empty_str(payload, ["name", "requirementName", "title", "label"])


def _is_explicit_custom_requirement(payload: dict[str, Any]) -> bool:
    for key in ("isCustomRequirement", "isCustomTask", "customRequirement", "customTask"):
        parsed = _to_bool(payload.get(key))
        if parsed is True:
            return True
    return False


def _looks_like_requirement(payload: dict[str, Any]) -> bool:
    return bool(_resolve_requirement_id(payload) and _resolve_requirement_name(payload))


def _resolve_time_only(raw: dict[str, Any], counts: dict[str, int]) -> bool:
    for key in ("timeOnly", "timerOnly", "isTimeOnly", "isTimerOnly", "minutesOnly"):
        parsed = _to_bool(raw.get(key))
        if parsed is not None:
            return parsed

    for key in (
        "hasCount",
        "countEnabled",
        "countRequired",
        "requiresCount",
        "trackCount",
        "enableCount",
    ):
        parsed = _to_bool(raw.get(key))
        if parsed is not None:
            return not parsed

    tracking_mode = _first_non_empty_str(raw, ["trackingMode", "inputMode", "mode"]).lower()
    if tracking_mode in {"time_only", "timer_only", "minutes_only"}:
        return True
    if tracking_mode in {"count_and_time", "count"}:
        return False

    return not any(value > 0 for value in counts.values())


def _build_custom_requirement(raw: dict[str, Any]) -> dict[str, Any] | None:
    requirement_id = _resolve_requirement_id(raw)
    requirement_name = _resolve_requirement_name(raw)
    if not requirement_id or not requirement_name:
        return None

    counts = normalize_counts(raw.get("counts", {}))
    if not counts:
        counts = normalize_counts(raw.get("targetCounts", {}))

    start_count = _to_int(raw.get("startCount", raw.get("start_count", 0)))
    time_only = _resolve_time_only(raw, counts)

    return {
        "id": requirement_id,
        "name": requirement_name,
        "category": _first_non_empty_str(raw, ["category", "requirementCategory"]) or "Custom",
        "counts": counts,
        "startCount": start_count,
        "progressBarSuffix": _first_non_empty_str(
            raw, ["progressBarSuffix", "progress_bar_suffix"]
        ),
        "scoreboardDisplay": _first_non_empty_str(raw, ["scoreboardDisplay", "scoreboard_display"]),
        "numberOfCohorts": _to_int(raw.get("numberOfCohorts", 0)),
        "sortPriority": _first_non_empty_str(raw, ["sortPriority", "sort_priority"])
        or f"zzz_custom_{requirement_id}",
        "isCustomRequirement": True,
        "timeOnly": time_only,
    }


def extract_custom_requirements(custom_access_payload: Any) -> list[dict[str, Any]]:
    if not custom_access_payload:
        return []

    custom_requirements_by_id: dict[str, dict[str, Any]] = {}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            lower_path = path.lower()
            explicit_custom = _is_explicit_custom_requirement(node)
            path_indicates_custom = "custom" in lower_path
            if _looks_like_requirement(node) and (explicit_custom or path_indicates_custom):
                built = _build_custom_requirement(node)
                if built:
                    custom_requirements_by_id[built["id"]] = built

            for key, value in node.items():
                walk(value, f"{path}.{key}")
            return

        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(custom_access_payload, "root")
    return list(custom_requirements_by_id.values())


def merge_requirements(
    requirements_payload: list[dict[str, Any]], custom_access_payload: Any
) -> list[dict[str, Any]]:
    requirements_by_id: dict[str, dict[str, Any]] = {}

    for requirement in requirements_payload:
        requirement_id = str(requirement.get("id", "")).strip()
        if requirement_id:
            requirements_by_id[requirement_id] = requirement

    for custom_requirement in extract_custom_requirements(custom_access_payload):
        requirement_id = str(custom_requirement.get("id", "")).strip()
        if not requirement_id:
            continue
        if requirement_id in requirements_by_id:
            merged = {**requirements_by_id[requirement_id], **custom_requirement}
            requirements_by_id[requirement_id] = merged
            continue
        requirements_by_id[requirement_id] = custom_requirement

    return list(requirements_by_id.values())


def format_bootstrap(
    user_payload: dict[str, Any],
    requirements_payload: list[dict[str, Any]],
    custom_access_payload: Any = None,
) -> BootstrapResponse:
    cohort = str(user_payload.get("dojoCohort", ""))
    progress_map = user_payload.get("progress", {})
    if not isinstance(progress_map, dict):
        progress_map = {}

    merged_requirements = merge_requirements(requirements_payload, custom_access_payload)

    tasks: list[TaskItem] = []
    cohort_set: set[str] = set()

    for req in merged_requirements:
        req_id = str(req.get("id", ""))
        if not req_id:
            continue

        counts = normalize_counts(req.get("counts", {}))
        cohort_set.update(key for key in counts if key != "ALL_COHORTS")
        start_count = _to_int(req.get("startCount", 0))
        current_count = resolve_previous_count(progress_map.get(req_id), cohort, start_count)
        is_custom = _is_explicit_custom_requirement(req)
        time_only = _resolve_time_only(req, counts) if is_custom else False
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
                is_custom=is_custom,
                time_only=time_only,
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
