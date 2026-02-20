import asyncio
from pathlib import Path

from backend.app.auth import LocalAuthManager
from backend.app.config import Settings


def _make_settings(tmp_path: Path, env_token: str = "") -> Settings:
    return Settings(
        chessdojo_bearer_token=env_token,
        local_auth_state_path=str(tmp_path / "auth_state.json"),
    )


def test_manual_token_takes_priority_over_env(tmp_path: Path) -> None:
    manager = LocalAuthManager(_make_settings(tmp_path, env_token="env-token"))

    asyncio.run(manager.set_manual_token("Bearer manual-token"))
    token = asyncio.run(manager.get_bearer_token())

    assert token == "manual-token"


def test_login_uses_id_token_and_persists_refresh_token(tmp_path: Path, monkeypatch) -> None:
    manager = LocalAuthManager(_make_settings(tmp_path))

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

    status = asyncio.run(
        manager.login(
            username="user@example.com",
            password="secret-password",
            persist_refresh_token=True,
        )
    )

    assert status["authenticated"] is True
    assert status["auth_mode"] == "session"
    assert status["has_refresh_token"] is True
    assert asyncio.run(manager.get_bearer_token()) == "id-token-1"


def test_refresh_flow_renews_expired_session(tmp_path: Path, monkeypatch) -> None:
    manager = LocalAuthManager(_make_settings(tmp_path))
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

    asyncio.run(
        manager.login(
            username="user@example.com",
            password="secret-password",
            persist_refresh_token=True,
        )
    )

    assert manager._session_tokens is not None
    manager._session_tokens.expires_at_epoch = 0
    token = asyncio.run(manager.get_bearer_token())

    assert token == "id-token-refresh"
    assert calls == ["login", "refresh"]


def test_env_token_fallback_when_no_session(tmp_path: Path) -> None:
    manager = LocalAuthManager(_make_settings(tmp_path, env_token="Bearer env-token"))
    token = asyncio.run(manager.get_bearer_token())
    assert token == "env-token"
