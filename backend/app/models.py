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
    is_custom: bool = False
    time_only: bool = False


class BootstrapResponse(BaseModel):
    user: UserInfo
    tasks: list[TaskItem]
    progress_by_requirement_id: dict[str, dict[str, Any]]
    pinned_task_ids: list[str]
    task_ui_preferences: dict[str, dict[str, Any]] = Field(default_factory=dict)
    preferences_version: int = 1
    available_cohorts: list[str]
    default_filters: dict[str, str]
    stale: bool = False
    data_source: str = "live"
    fetched_at_epoch: int | None = None


class SubmitProgressRequest(BaseModel):
    requirement_id: str = Field(min_length=1)
    count_increment: int = Field(ge=0)
    minutes_spent: int = Field(ge=1)


class SubmitProgressResponse(BaseModel):
    submitted_payload: dict[str, Any]
    upstream_response: Any


class HealthResponse(BaseModel):
    ok: bool
    token_configured: bool
    upstream_reachable: bool


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_mode: str
    has_refresh_token: bool
    username: str | None = None
    auth_state: str = "ok"
    needs_relogin: bool = False


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    persist_refresh_token: bool = True


class PreferencesResponse(BaseModel):
    pinned_task_ids: list[str]
    task_ui_preferences: dict[str, dict[str, Any]]
    version: int
    updated_at_epoch: int


class PreferencesUpdateRequest(BaseModel):
    pinned_task_ids: list[str]
    task_ui_preferences: dict[str, dict[str, Any]]
    version: int | None = None
