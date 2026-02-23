from __future__ import annotations

import asyncio
import html
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from fastapi import HTTPException

from .config import Settings


@dataclass
class SessionTokens:
    bearer_token: str
    access_token: str
    id_token: str
    refresh_token: str | None
    expires_at_epoch: float
    username: str | None = None


class LocalAuthManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._lock = asyncio.Lock()
        self._auth_state_path = settings.resolved_auth_state_path()

        self._session_tokens: SessionTokens | None = None
        self._persisted_refresh_token: str | None = None
        self._persisted_username: str | None = None
        self._load_refresh_state()

    async def get_bearer_token(self, force_refresh: bool = False) -> str:
        async with self._lock:
            if not force_refresh and self._has_valid_session_token():
                assert self._session_tokens is not None
                return self._session_tokens.bearer_token

            refresh_token = self._resolve_refresh_token()
            if refresh_token:
                try:
                    await self._refresh_session_locked(refresh_token=refresh_token)
                    assert self._session_tokens is not None
                    return self._session_tokens.bearer_token
                except HTTPException as exc:
                    if exc.status_code not in {400, 401, 403}:
                        raise
                    self._clear_session_locked(clear_refresh_state=True)

            raise HTTPException(
                status_code=401,
                detail=(
                    "Authentication required. Sign in with your ChessDojo email and password."
                ),
            )

    async def login(
        self,
        email: str,
        password: str,
        persist_refresh_token: bool = True,
    ) -> dict[str, Any]:
        normalized_email = email.strip()
        if not normalized_email:
            raise HTTPException(status_code=422, detail="Email is required.")
        if not password:
            raise HTTPException(status_code=422, detail="Password is required.")

        async with self._lock:
            token_payload = await self._oauth_login_with_credentials(
                username=normalized_email,
                password=password,
            )
            self._apply_oauth_token_payload_locked(
                token_payload=token_payload,
                username=normalized_email,
                fallback_refresh_token=None,
            )
            if persist_refresh_token and self._session_tokens and self._session_tokens.refresh_token:
                self._persisted_refresh_token = self._session_tokens.refresh_token
                self._persisted_username = normalized_email
                self._persist_refresh_state()
            if not persist_refresh_token:
                self._persisted_refresh_token = None
                self._persist_refresh_state()
            return self.status()

    async def logout(self) -> dict[str, Any]:
        async with self._lock:
            self._clear_session_locked(clear_refresh_state=True)
            return self.status()

    def has_any_auth_configured(self) -> bool:
        return (
            self._has_valid_session_token()
            or bool(self._resolve_refresh_token())
        )

    def status(self) -> dict[str, Any]:
        auth_mode = "none"
        authenticated = False

        if self._has_valid_session_token() or self._resolve_refresh_token():
            auth_mode = "session"
            authenticated = True

        username = None
        if self._session_tokens and self._session_tokens.username:
            username = self._session_tokens.username
        elif self._persisted_username:
            username = self._persisted_username

        return {
            "authenticated": authenticated,
            "auth_mode": auth_mode,
            "has_refresh_token": bool(self._resolve_refresh_token()),
            "username": username,
        }

    def _has_valid_session_token(self) -> bool:
        if not self._session_tokens:
            return False
        now = time.time()
        return (self._session_tokens.expires_at_epoch - self._settings.auth_refresh_skew_seconds) > now

    def _resolve_refresh_token(self) -> str | None:
        if self._session_tokens and self._session_tokens.refresh_token:
            return self._session_tokens.refresh_token
        return self._persisted_refresh_token

    async def _refresh_session_locked(self, refresh_token: str) -> None:
        token_payload = await self._oauth_refresh_tokens(refresh_token=refresh_token)
        self._apply_oauth_token_payload_locked(
            token_payload=token_payload,
            username=self._session_tokens.username if self._session_tokens else self._persisted_username,
            fallback_refresh_token=refresh_token,
        )
        assert self._session_tokens is not None
        self._persisted_refresh_token = self._session_tokens.refresh_token or refresh_token
        self._persist_refresh_state()

    async def _oauth_login_with_credentials(
        self,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        authorize_url = self._build_oauth_authorize_url()
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.request_timeout_seconds,
                follow_redirects=True,
            ) as client:
                authorize_response = await client.get(authorize_url)
                authorize_response.raise_for_status()

                code, oauth_error = _extract_code_or_error_from_url(str(authorize_response.url))
                if oauth_error:
                    raise HTTPException(status_code=401, detail=f"OAuth authorize failed: {oauth_error}")
                if code:
                    return await self._exchange_oauth_code_for_tokens(client=client, code=code)

                login_page = authorize_response.text
                form_action = _extract_login_form_action(login_page)
                csrf_token = _extract_csrf_token(login_page)
                if not form_action or not csrf_token:
                    raise HTTPException(
                        status_code=502,
                        detail="Could not parse Cognito login form. Hosted UI may have changed.",
                    )

                login_url = urljoin(str(authorize_response.url), form_action)
                login_response = await client.post(
                    login_url,
                    data={
                        "_csrf": csrf_token,
                        "username": username,
                        "password": password,
                        "cognitoAsfData": "",
                    },
                    follow_redirects=False,
                )

                if _is_redirect(login_response.status_code):
                    location = login_response.headers.get("Location", "").strip()
                    if not location:
                        raise HTTPException(
                            status_code=502,
                            detail="OAuth login did not return a redirect location.",
                        )
                    redirect_url = urljoin(str(login_response.url), location)
                    code, oauth_error = _extract_code_or_error_from_url(redirect_url)
                    if oauth_error:
                        raise HTTPException(status_code=401, detail=oauth_error)
                    if code:
                        return await self._exchange_oauth_code_for_tokens(client=client, code=code)

                    follow_response = await client.get(redirect_url)
                    code, oauth_error = _extract_code_or_error_from_url(str(follow_response.url))
                    if oauth_error:
                        raise HTTPException(status_code=401, detail=oauth_error)
                    if code:
                        return await self._exchange_oauth_code_for_tokens(client=client, code=code)

                    login_error = _extract_login_error_message(follow_response.text)
                    if login_error:
                        raise HTTPException(status_code=401, detail=login_error)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "OAuth login did not return an authorization code. "
                            "Additional challenge may be required."
                        ),
                    )

                login_error = _extract_login_error_message(login_response.text)
                if login_error:
                    raise HTTPException(status_code=401, detail=login_error)
                if login_response.status_code in {400, 401, 403}:
                    raise HTTPException(status_code=401, detail="Invalid credentials.")
                raise HTTPException(
                    status_code=502,
                    detail=f"OAuth login failed with status {login_response.status_code}.",
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Cognito OAuth network error: {exc}",
            ) from exc

    async def _oauth_refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
                response = await client.post(
                    self._settings.cognito_oauth_token_url(),
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self._settings.chessdojo_cognito_user_pool_client_id,
                        "refresh_token": refresh_token,
                    },
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Cognito OAuth refresh network error: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise _map_oauth_token_error(response, context="refresh")

        try:
            parsed = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="Cognito OAuth refresh returned non-JSON payload.",
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=502, detail="OAuth refresh payload was not an object.")
        return parsed

    async def _exchange_oauth_code_for_tokens(
        self,
        client: httpx.AsyncClient,
        code: str,
    ) -> dict[str, Any]:
        response = await client.post(
            self._settings.cognito_oauth_token_url(),
            data={
                "grant_type": "authorization_code",
                "client_id": self._settings.chessdojo_cognito_user_pool_client_id,
                "code": code,
                "redirect_uri": self._settings.chessdojo_oauth_redirect_uri,
            },
        )

        if response.status_code >= 400:
            raise _map_oauth_token_error(response, context="login")

        try:
            parsed = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="Cognito OAuth token exchange returned non-JSON payload.",
            ) from exc

        if not isinstance(parsed, dict):
            raise HTTPException(status_code=502, detail="OAuth token payload was not an object.")
        return parsed

    def _apply_oauth_token_payload_locked(
        self,
        token_payload: dict[str, Any],
        username: str | None,
        fallback_refresh_token: str | None,
    ) -> None:
        id_token = str(token_payload.get("id_token", "")).strip()
        access_token = str(token_payload.get("access_token", "")).strip()
        bearer_token = id_token or access_token
        if not bearer_token:
            raise HTTPException(status_code=502, detail="Missing OAuth bearer token.")

        raw_refresh_token = str(token_payload.get("refresh_token", "")).strip()
        refresh_token = raw_refresh_token or fallback_refresh_token or self._resolve_refresh_token()
        expires_in_seconds = _to_int(token_payload.get("expires_in"), fallback=3600)
        expires_in_seconds = max(expires_in_seconds, 60)
        self._session_tokens = SessionTokens(
            bearer_token=bearer_token,
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh_token or None,
            expires_at_epoch=time.time() + expires_in_seconds,
            username=username,
        )
        if username:
            self._persisted_username = username

    def _build_oauth_authorize_url(self) -> str:
        query = urlencode(
            {
                "client_id": self._settings.chessdojo_cognito_user_pool_client_id,
                "response_type": "code",
                "scope": self._settings.chessdojo_oauth_scope,
                "redirect_uri": self._settings.chessdojo_oauth_redirect_uri,
            }
        )
        return f"{self._settings.cognito_oauth_authorize_url()}?{query}"

    def _clear_session_locked(self, clear_refresh_state: bool) -> None:
        self._session_tokens = None
        if clear_refresh_state:
            self._persisted_refresh_token = None
            self._persisted_username = None
            self._persist_refresh_state()

    def _load_refresh_state(self) -> None:
        payload = _load_json_file(self._auth_state_path)
        if not payload:
            return
        refresh_token = str(payload.get("refresh_token", "")).strip()
        if refresh_token:
            self._persisted_refresh_token = refresh_token
        username = str(payload.get("username", "")).strip()
        if username:
            self._persisted_username = username

    def _persist_refresh_state(self) -> None:
        if not self._persisted_refresh_token:
            _delete_file(self._auth_state_path)
            return

        payload = {
            "refresh_token": self._persisted_refresh_token,
            "username": self._persisted_username or "",
            "updated_at_epoch": int(time.time()),
        }
        _write_json_file(self._auth_state_path, payload)


def _map_oauth_token_error(response: httpx.Response, context: str) -> HTTPException:
    error_code = ""
    error_description = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error_code = str(payload.get("error", "")).strip()
            error_description = str(payload.get("error_description", "")).strip()
    except ValueError:
        pass

    detail = error_description or f"Cognito OAuth {context} failed with status {response.status_code}."
    normalized = error_code.lower()
    if normalized in {"invalid_grant", "unauthorized_client"}:
        return HTTPException(status_code=401, detail=detail)
    if normalized in {"invalid_request", "unsupported_grant_type"}:
        return HTTPException(status_code=400, detail=detail)
    if response.status_code in {400, 401, 403}:
        return HTTPException(status_code=401, detail=detail)
    return HTTPException(status_code=502, detail=f"Cognito OAuth error: {detail}")


def _extract_login_form_action(page_html: str) -> str:
    patterns = [
        r'<form[^>]*name="cognitoSignInForm"[^>]*action="([^"]+)"',
        r'<form[^>]*action="([^"]+)"[^>]*name="cognitoSignInForm"',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return html.unescape(match.group(1))
    return ""


def _extract_csrf_token(page_html: str) -> str:
    match = re.search(
        r'name="_csrf"\s+value="([^"]+)"',
        page_html,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return html.unescape(match.group(1))


def _extract_login_error_message(page_html: str) -> str:
    match = re.search(
        r'id="loginErrorMessage"[^>]*>(.*?)</p>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    raw = html.unescape(match.group(1))
    return re.sub(r"\s+", " ", raw).strip()


def _extract_code_or_error_from_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    code = (params.get("code") or [""])[0].strip()
    error = (params.get("error_description") or params.get("error") or [""])[0].strip()
    return code, error


def _is_redirect(status_code: int) -> bool:
    return status_code in {301, 302, 303, 307, 308}


def _to_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
            return {}
    except OSError:
        return {}
    except ValueError:
        return {}


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError:
        pass


def _delete_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
