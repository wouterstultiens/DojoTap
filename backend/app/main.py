from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .chessdojo import ChessDojoClient, build_progress_payload, format_bootstrap, merge_requirements
from .config import get_settings
from .models import HealthResponse, SubmitProgressRequest, SubmitProgressResponse

app = FastAPI(title="DojoTap API", version="0.1.0")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allow_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_token() -> None:
    if not settings.normalized_bearer_token():
        raise HTTPException(
            status_code=500,
            detail=(
                "CHESSDOJO_BEARER_TOKEN is missing. "
                "Set it in a local .env file before calling the API."
            ),
        )


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    token_configured = bool(settings.normalized_bearer_token())
    if not token_configured:
        return HealthResponse(ok=False, token_configured=False, upstream_reachable=False)

    client = ChessDojoClient(settings)
    try:
        await client.fetch_user()
    except HTTPException:
        return HealthResponse(ok=False, token_configured=True, upstream_reachable=False)
    return HealthResponse(ok=True, token_configured=True, upstream_reachable=True)


@app.get("/api/bootstrap")
async def bootstrap() -> Any:
    _require_token()
    client = ChessDojoClient(settings)
    user_payload = await client.fetch_user()
    requirements_payload = await client.fetch_requirements(scoreboard_only=False)
    custom_access_payload: Any = {}
    try:
        custom_access_payload = await client.fetch_custom_access()
    except HTTPException as exc:
        if exc.status_code not in {403, 404}:
            raise
    return format_bootstrap(user_payload, requirements_payload, custom_access_payload)


@app.post("/api/progress", response_model=SubmitProgressResponse)
async def submit_progress(payload: SubmitProgressRequest) -> SubmitProgressResponse:
    _require_token()
    client = ChessDojoClient(settings)

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
