import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.auth import LocalAuthManager
from backend.app.config import Settings
from backend.app.crypto import TokenCipher
from backend.app.db import Database


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'dojotap-test.db'}",
        auth_state_encryption_key="unit-test-key",
    )


def _make_manager(tmp_path: Path) -> tuple[Database, LocalAuthManager]:
    settings = _make_settings(tmp_path)
    database = Database(settings.database_url)
    manager = LocalAuthManager(
        settings=settings,
        session_factory=database.session_factory,
        token_cipher=TokenCipher(settings.auth_state_encryption_key),
    )
    return database, manager


def test_requires_login_when_session_cookie_missing(tmp_path: Path) -> None:
    database, manager = _make_manager(tmp_path)
    asyncio.run(database.init())
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(manager.get_bearer_token(session_id=None))
    assert exc_info.value.status_code == 401
    assert "email and password" in str(exc_info.value.detail)
    asyncio.run(database.dispose())


def test_login_uses_id_token_and_persists_refresh_token(tmp_path: Path, monkeypatch) -> None:
    database, manager = _make_manager(tmp_path)
    asyncio.run(database.init())

    async def _fake_oauth_login_with_credentials(username: str, password: str) -> dict:
        assert username == "user@example.com"
        assert password == "secret-password"
        return {
            "id_token": "id-token-1",
            "access_token": "access-token-1",
            "refresh_token": "refresh-token-1",
            "expires_in": 3600,
        }

    monkeypatch.setattr(
        manager, "_oauth_login_with_credentials", _fake_oauth_login_with_credentials
    )

    status, session_id = asyncio.run(
        manager.login(
            email="user@example.com",
            password="secret-password",
            persist_refresh_token=True,
        )
    )

    assert status["authenticated"] is True
    assert status["auth_mode"] == "session"
    assert status["has_refresh_token"] is True
    token, user_key = asyncio.run(manager.get_bearer_token(session_id=session_id))
    assert token == "id-token-1"
    assert user_key == "user@example.com"
    asyncio.run(database.dispose())


def test_refresh_flow_renews_expired_session(tmp_path: Path, monkeypatch) -> None:
    database, manager = _make_manager(tmp_path)
    asyncio.run(database.init())
    calls: list[str] = []

    async def _fake_oauth_login_with_credentials(username: str, password: str) -> dict:
        calls.append("login")
        assert username == "user@example.com"
        assert password == "secret-password"
        return {
            "id_token": "id-token-login",
            "access_token": "access-token-login",
            "refresh_token": "refresh-token-login",
            "expires_in": 3600,
        }

    async def _fake_oauth_refresh_tokens(refresh_token: str) -> dict:
        calls.append("refresh")
        assert refresh_token == "refresh-token-login"
        return {
            "id_token": "id-token-refresh",
            "access_token": "access-token-refresh",
            "expires_in": 3600,
        }

    monkeypatch.setattr(
        manager, "_oauth_login_with_credentials", _fake_oauth_login_with_credentials
    )
    monkeypatch.setattr(manager, "_oauth_refresh_tokens", _fake_oauth_refresh_tokens)

    _, session_id = asyncio.run(
        manager.login(
            email="user@example.com",
            password="secret-password",
            persist_refresh_token=True,
        )
    )

    token, _ = asyncio.run(manager.get_bearer_token(session_id=session_id, force_refresh=True))
    assert token == "id-token-refresh"
    assert calls == ["login", "refresh"]
    asyncio.run(database.dispose())
