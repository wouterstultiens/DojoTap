from __future__ import annotations

import getpass
import os
import re
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException

from backend.app.auth import LocalAuthManager
from backend.app.config import Settings, get_settings
from backend.app.crypto import TokenCipher
from backend.app.db import Database


def resolve_settings() -> Settings:
    return get_settings()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def resolve_credentials(
    *,
    username_arg: str | None,
    password_arg: str | None,
    no_prompt: bool,
) -> tuple[str | None, str | None]:
    username = (username_arg or os.getenv("CHESSDOJO_USERNAME", "")).strip() or None
    password = (password_arg or os.getenv("CHESSDOJO_PASSWORD", "")).strip() or None

    if no_prompt:
        return username, password

    if username and not password and sys.stdin.isatty():
        password = getpass.getpass("ChessDojo password: ").strip() or None
    if password and not username and sys.stdin.isatty():
        entered = input("ChessDojo username/email: ").strip()
        username = entered or None

    return username, password


async def resolve_bearer_token(
    *,
    username: str | None,
    password: str | None,
    persist_refresh_token: bool,
    force_refresh: bool,
) -> tuple[Settings, LocalAuthManager, str]:
    settings = resolve_settings()
    database = Database(settings.database_url)
    await database.init()
    auth_manager = LocalAuthManager(
        settings=settings,
        session_factory=database.session_factory,
        token_cipher=TokenCipher(settings.auth_state_encryption_key),
    )
    session_id = _load_cli_session_id(settings)

    if username or password:
        if not username or not password:
            raise ValueError(
                "When using credentials, provide both username and password "
                "(or CHESSDOJO_USERNAME and CHESSDOJO_PASSWORD)."
            )
        _, session_id = await auth_manager.login(
            email=username,
            password=password,
            persist_refresh_token=persist_refresh_token,
        )
        _save_cli_session_id(settings, session_id)

    if not session_id:
        raise ValueError(
            "No active CLI session found. Provide username/password once to create one."
        )

    token, _ = await auth_manager.get_bearer_token(
        session_id=session_id,
        force_refresh=force_refresh,
    )
    return settings, auth_manager, token


def _default_cli_session_path() -> Path:
    return Path.home() / ".dojotap" / "cli_session_id.txt"


def _load_cli_session_id(settings: Settings) -> str | None:
    if settings.local_auth_state_path.strip():
        path = Path(settings.local_auth_state_path).expanduser().with_suffix(".session")
    else:
        path = _default_cli_session_path()
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _save_cli_session_id(settings: Settings, session_id: str) -> None:
    if settings.local_auth_state_path.strip():
        path = Path(settings.local_auth_state_path).expanduser().with_suffix(".session")
    else:
        path = _default_cli_session_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(session_id, encoding="utf-8")
    except OSError:
        pass


def match_requirement_by_name(
    requirements: Sequence[dict[str, Any]],
    task_name: str,
) -> tuple[dict[str, Any], str]:
    query = _normalize_name(task_name)
    if not query:
        raise ValueError("Task name is empty.")

    exact_matches = [
        req
        for req in requirements
        if _normalize_name(str(req.get("name", ""))) == query
    ]
    if len(exact_matches) == 1:
        return exact_matches[0], "exact"
    if len(exact_matches) > 1:
        raise ValueError(
            "Task name is ambiguous. Multiple exact-name matches found: "
            + ", ".join(_requirement_label(req) for req in exact_matches[:8])
        )

    contains_matches = [
        req
        for req in requirements
        if query in _normalize_name(str(req.get("name", "")))
    ]
    if len(contains_matches) == 1:
        return contains_matches[0], "contains"
    if len(contains_matches) > 1:
        raise ValueError(
            "Task name is ambiguous. Multiple partial matches found: "
            + ", ".join(_requirement_label(req) for req in contains_matches[:8])
        )

    raise ValueError(f"Task '{task_name}' not found.")


def _requirement_label(requirement: dict[str, Any]) -> str:
    task_id = str(requirement.get("id", "")).strip() or "unknown-id"
    name = str(requirement.get("name", "")).strip() or "unnamed"
    category = str(requirement.get("category", "")).strip() or "uncategorized"
    return f"{name} [{task_id}] ({category})"


def unwrap_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)
