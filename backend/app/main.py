from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .auth import LocalAuthManager
from .chessdojo import ChessDojoClient, build_progress_payload, format_bootstrap, merge_requirements
from .config import get_settings
from .crypto import TokenCipher
from .ct_auto_backfill import maybe_schedule_on_login
from .db import Database
from .models import (
    AuthStatusResponse,
    HealthResponse,
    LoginRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
    SubmitProgressRequest,
    SubmitProgressResponse,
)

settings = get_settings()
database = Database(settings.database_url)
auth_manager = LocalAuthManager(
    settings=settings,
    session_factory=database.session_factory,
    token_cipher=TokenCipher(settings.auth_state_encryption_key),
)
SESSION_HEADER_NAME = "X-DojoTap-Session"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await database.init()
    try:
        yield
    finally:
        await database.dispose()


app = FastAPI(title="DojoTap API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allow_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[SESSION_HEADER_NAME],
)


def _session_id_from_request(request: Request) -> str | None:
    cookie_session_id = (request.cookies.get(settings.session_cookie_name) or "").strip()
    if cookie_session_id:
        return cookie_session_id
    header_session_id = (request.headers.get(SESSION_HEADER_NAME) or "").strip()
    if header_session_id:
        return header_session_id
    return None


def _set_session_cookie(response: Response, session_id: str) -> None:
    max_age_seconds = max(1, int(settings.session_cookie_max_age_days)) * 24 * 60 * 60
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=max_age_seconds,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite.lower(),
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite.lower(),
        path="/",
    )


async def _build_client(request: Request, force_refresh: bool = False) -> tuple[ChessDojoClient, str]:
    bearer_token, user_key = await auth_manager.get_bearer_token(
        session_id=_session_id_from_request(request),
        force_refresh=force_refresh,
    )
    return ChessDojoClient(settings=settings, bearer_token=bearer_token), user_key


async def _run_with_auth_retry(
    request: Request,
    operation: Callable[[ChessDojoClient, str], Awaitable[Any]],
) -> Any:
    client, user_key = await _build_client(request, force_refresh=False)
    try:
        return await operation(client, user_key)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
    client, user_key = await _build_client(request, force_refresh=True)
    return await operation(client, user_key)


async def _require_user_key(request: Request) -> str:
    _, user_key = await auth_manager.get_bearer_token(
        session_id=_session_id_from_request(request),
        force_refresh=False,
    )
    return user_key


@app.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    session_id = _session_id_from_request(request)
    if not session_id:
        return HealthResponse(ok=True, token_configured=False, upstream_reachable=False)

    try:
        await _run_with_auth_retry(
            request,
            lambda client, _user_key: client.fetch_user(),
        )
    except HTTPException:
        return HealthResponse(ok=False, token_configured=True, upstream_reachable=False)
    return HealthResponse(ok=True, token_configured=True, upstream_reachable=True)


@app.get("/api/bootstrap")
async def bootstrap(request: Request) -> Any:
    user_key = await auth_manager.get_user_key_for_session(_session_id_from_request(request))
    if not user_key:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Sign in with your ChessDojo email and password.",
        )

    async def _load(client: ChessDojoClient, resolved_user_key: str) -> dict[str, Any]:
        user_payload = await client.fetch_user()
        requirements_payload = await client.fetch_requirements(scoreboard_only=False)
        custom_access_payload: Any = {}
        try:
            custom_access_payload = await client.fetch_custom_access()
        except HTTPException as exc:
            if exc.status_code not in {403, 404}:
                raise
        payload = format_bootstrap(
            user_payload,
            requirements_payload,
            custom_access_payload,
        ).model_dump()
        preferences = await auth_manager.get_preferences(
            resolved_user_key,
            fallback_pinned_task_ids=payload.get("pinned_task_ids", []),
        )
        fetched_at_epoch = int(time.time())
        payload["pinned_task_ids"] = preferences.pinned_task_ids
        payload["task_ui_preferences"] = preferences.task_ui_preferences
        payload["preferences_version"] = preferences.version
        payload["stale"] = False
        payload["data_source"] = "live"
        payload["fetched_at_epoch"] = fetched_at_epoch
        await auth_manager.save_bootstrap_cache(
            resolved_user_key,
            payload,
            fetched_at_epoch=fetched_at_epoch,
        )
        return payload

    try:
        return await _run_with_auth_retry(request, _load)
    except HTTPException as exc:
        if exc.status_code not in {502, 503, 504}:
            raise
        cached_payload = await auth_manager.load_bootstrap_cache(user_key)
        if not cached_payload:
            raise
        payload, cached_at_epoch = cached_payload
        preferences = await auth_manager.get_preferences(
            user_key,
            fallback_pinned_task_ids=payload.get("pinned_task_ids", []),
        )
        payload = {**payload}
        payload["pinned_task_ids"] = preferences.pinned_task_ids
        payload["task_ui_preferences"] = preferences.task_ui_preferences
        payload["preferences_version"] = preferences.version
        payload["stale"] = True
        payload["data_source"] = "cache"
        payload["fetched_at_epoch"] = cached_at_epoch
        return payload


@app.post("/api/progress", response_model=SubmitProgressResponse)
async def submit_progress(request: Request, payload: SubmitProgressRequest) -> SubmitProgressResponse:
    async def _submit(client: ChessDojoClient, _user_key: str) -> SubmitProgressResponse:
        user_payload = await client.fetch_user()
        requirements_payload = await client.fetch_requirements(scoreboard_only=False)
        custom_access_payload: Any = {}
        try:
            custom_access_payload = await client.fetch_custom_access()
        except HTTPException as exc:
            if exc.status_code not in {403, 404}:
                raise
        merged_requirements = merge_requirements(requirements_payload, custom_access_payload)
        req_map = {str(req.get("id", "")): req for req in merged_requirements if req.get("id")}
        requirement = req_map.get(payload.requirement_id)
        if requirement is None:
            raise HTTPException(status_code=404, detail="Requirement not found.")

        upstream_payload = build_progress_payload(
            user_payload=user_payload,
            requirement=requirement,
            count_increment=payload.count_increment,
            minutes_spent=payload.minutes_spent,
        )
        upstream_response = await client.post_progress(upstream_payload)
        return SubmitProgressResponse(
            submitted_payload=upstream_payload,
            upstream_response=upstream_response,
        )

    response = await _run_with_auth_retry(request, _submit)
    if not isinstance(response, SubmitProgressResponse):
        raise HTTPException(status_code=500, detail="Invalid progress response.")
    return response


@app.get("/api/auth/status", response_model=AuthStatusResponse)
async def auth_status(request: Request) -> AuthStatusResponse:
    status = await auth_manager.status(_session_id_from_request(request))
    return AuthStatusResponse(**status)


@app.post("/api/auth/login", response_model=AuthStatusResponse)
async def auth_login(request: Request, response: Response, payload: LoginRequest) -> AuthStatusResponse:
    status, session_id = await auth_manager.login(
        email=payload.email,
        password=payload.password,
        persist_refresh_token=payload.persist_refresh_token,
    )
    _set_session_cookie(response, session_id)
    response.headers[SESSION_HEADER_NAME] = session_id
    await maybe_schedule_on_login(
        settings=settings,
        username=payload.email,
        password=payload.password,
    )
    return AuthStatusResponse(**status)


@app.post("/api/auth/logout", response_model=AuthStatusResponse)
async def auth_logout(request: Request, response: Response) -> AuthStatusResponse:
    status = await auth_manager.logout(_session_id_from_request(request), all_devices=False)
    _clear_session_cookie(response)
    return AuthStatusResponse(**status)


@app.get("/api/preferences", response_model=PreferencesResponse)
async def get_preferences(request: Request) -> PreferencesResponse:
    user_key = await _require_user_key(request)
    preferences = await auth_manager.get_preferences(user_key)
    return PreferencesResponse(
        pinned_task_ids=preferences.pinned_task_ids,
        task_ui_preferences=preferences.task_ui_preferences,
        version=preferences.version,
        updated_at_epoch=preferences.updated_at_epoch,
    )


@app.put("/api/preferences", response_model=PreferencesResponse)
async def put_preferences(request: Request, payload: PreferencesUpdateRequest) -> PreferencesResponse:
    user_key = await _require_user_key(request)
    preferences = await auth_manager.update_preferences(
        user_key,
        pinned_task_ids=payload.pinned_task_ids,
        task_ui_preferences=payload.task_ui_preferences,
        expected_version=payload.version,
    )
    return PreferencesResponse(
        pinned_task_ids=preferences.pinned_task_ids,
        task_ui_preferences=preferences.task_ui_preferences,
        version=preferences.version,
        updated_at_epoch=preferences.updated_at_epoch,
    )
