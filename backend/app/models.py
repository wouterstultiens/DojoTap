from typing import Any

from pydantic import BaseModel, Field


class UserInfo(BaseModel):
    display_name: str
    dojo_cohort: str


class TaskItem(BaseModel):
    id: str
    name: str
    category: str
    counts: dict[str, int]
    start_count: int
    progress_bar_suffix: str
    scoreboard_display: str
    number_of_cohorts: int
    sort_priority: str
    current_count: int
    target_count: int | None


class BootstrapResponse(BaseModel):
    user: UserInfo
    tasks: list[TaskItem]
    progress_by_requirement_id: dict[str, dict[str, Any]]
    pinned_task_ids: list[str]
    available_cohorts: list[str]
    default_filters: dict[str, str]


class SubmitProgressRequest(BaseModel):
    requirement_id: str = Field(min_length=1)
    count_increment: int = Field(ge=1)
    minutes_spent: int = Field(ge=1)


class SubmitProgressResponse(BaseModel):
    submitted_payload: dict[str, Any]
    upstream_response: Any


class HealthResponse(BaseModel):
    ok: bool
    token_configured: bool
    upstream_reachable: bool

