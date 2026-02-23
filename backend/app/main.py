from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import LocalAuthManager
from .chessdojo import ChessDojoClient, build_progress_payload, format_bootstrap, merge_requirements
from .ct_auto_backfill import maybe_schedule_on_login
from .config import get_settings
from .models import (
    AuthStatusResponse,
    HealthResponse,
    LoginRequest,
    SubmitProgressRequest,
    SubmitProgressResponse,
)

app = FastAPI(title="DojoTap API", version="0.1.0")
settings = get_settings()
auth_manager = LocalAuthManager(settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allow_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _build_client(force_refresh: bool = False) -> ChessDojoClient:
    bearer_token = await auth_manager.get_bearer_token(force_refresh=force_refresh)
    return ChessDojoClient(settings=settings, bearer_token=bearer_token)


async def _run_with_auth_retry(
    operation: Callable[[ChessDojoClient], Awaitable[Any]],
) -> Any:
    client = await _build_client(force_refresh=False)
    try:
        return await operation(client)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
    client = await _build_client(force_refresh=True)
    return await operation(client)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    token_configured = auth_manager.has_any_auth_configured()
    if not token_configured:
        return HealthResponse(ok=False, token_configured=False, upstream_reachable=False)

    try:
        await _run_with_auth_retry(lambda client: client.fetch_user())
    except HTTPException:
        return HealthResponse(ok=False, token_configured=True, upstream_reachable=False)
    return HealthResponse(ok=True, token_configured=True, upstream_reachable=True)


@app.get("/api/bootstrap")
async def bootstrap() -> Any:
    async def _load(client: ChessDojoClient) -> Any:
        user_payload = await client.fetch_user()
        requirements_payload = await client.fetch_requirements(scoreboard_only=False)
        custom_access_payload: Any = {}
        try:
            custom_access_payload = await client.fetch_custom_access()
        except HTTPException as exc:
            if exc.status_code not in {403, 404}:
                raise
        return format_bootstrap(user_payload, requirements_payload, custom_access_payload)

    return await _run_with_auth_retry(_load)


@app.post("/api/progress", response_model=SubmitProgressResponse)
async def submit_progress(payload: SubmitProgressRequest) -> SubmitProgressResponse:
    async def _submit(client: ChessDojoClient) -> SubmitProgressResponse:
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

    response = await _run_with_auth_retry(_submit)
    if not isinstance(response, SubmitProgressResponse):
        raise HTTPException(status_code=500, detail="Invalid progress response.")
    return response


@app.get("/api/auth/status", response_model=AuthStatusResponse)
async def auth_status() -> AuthStatusResponse:
    return AuthStatusResponse(**auth_manager.status())


@app.post("/api/auth/login", response_model=AuthStatusResponse)
async def auth_login(payload: LoginRequest) -> AuthStatusResponse:
    status = await auth_manager.login(
        email=payload.email,
        password=payload.password,
        persist_refresh_token=payload.persist_refresh_token,
    )
    await maybe_schedule_on_login(
        settings=settings,
        username=payload.email,
        password=payload.password,
    )
    return AuthStatusResponse(**status)


@app.post("/api/auth/logout", response_model=AuthStatusResponse)
async def auth_logout() -> AuthStatusResponse:
    status = await auth_manager.logout()
    return AuthStatusResponse(**status)
