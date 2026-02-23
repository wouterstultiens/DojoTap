from __future__ import annotations

import asyncio
import html
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Settings
from .crypto import TokenCipher
from .db import BrowserSession, BootstrapCache, PreferencesPayload, UserAuthState, UserPreferences


@dataclass
class SessionTokens:
    access_token: str
    id_token: str
    refresh_token: str | None
    expires_at_epoch: float
    username: str | None = None

    @property
    def bearer_token(self) -> str:
        return self.id_token or self.access_token


class LocalAuthManager:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        token_cipher: TokenCipher,
    ):
        self._settings = settings
        self._session_factory = session_factory
        self._token_cipher = token_cipher
        self._lock = asyncio.Lock()

    async def get_user_key_for_session(self, session_id: str | None) -> str | None:
        normalized_session_id = (session_id or "").strip()
        if not normalized_session_id:
            return None
        async with self._session_factory() as db:
            session_record = await db.get(BrowserSession, normalized_session_id)
            if not session_record or session_record.revoked:
                return None
            return session_record.user_key

    async def get_bearer_token(
        self, session_id: str | None, force_refresh: bool = False
    ) -> tuple[str, str]:
        normalized_session_id = (session_id or "").strip()
        if not normalized_session_id:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Authentication required. Sign in with your ChessDojo email and password."
                ),
            )

        async with self._lock:
            async with self._session_factory() as db:
                session_record = await db.get(BrowserSession, normalized_session_id)
                if not session_record or session_record.revoked:
                    raise HTTPException(
                        status_code=401,
                        detail=(
                            "Authentication required. Sign in with your ChessDojo email and password."
                        ),
                    )

                user_state = await db.get(UserAuthState, session_record.user_key)
                if not user_state:
                    session_record.revoked = True
                    await db.commit()
                    raise HTTPException(
                        status_code=401,
                        detail=(
                            "Authentication required. Sign in with your ChessDojo email and password."
                        ),
                    )

                if not force_refresh and self._has_valid_session_token(session_record):
                    session_record.last_seen_epoch = time.time()
                    await db.commit()
                    return self._resolve_bearer_token(session_record), session_record.user_key

                refresh_token = self._token_cipher.decrypt(user_state.refresh_token_encrypted)
                if not refresh_token:
                    session_record.revoked = True
                    await db.commit()
                    raise HTTPException(
                        status_code=401,
                        detail=(
                            "Session expired. Please sign in again with your ChessDojo email and password."
                        ),
                    )

                try:
                    token_payload = await self._oauth_refresh_tokens(refresh_token=refresh_token)
                except HTTPException as exc:
                    if exc.status_code in {400, 401, 403}:
                        session_record.revoked = True
                        user_state.refresh_token_encrypted = None
                        user_state.updated_at_epoch = int(time.time())
                        await db.commit()
                        raise HTTPException(
                            status_code=401,
                            detail=(
                                "Session expired. Please sign in again with your ChessDojo email and password."
                            ),
                        ) from exc
                    raise

                tokens = self._session_tokens_from_payload(
                    token_payload=token_payload,
                    username=user_state.username,
                    fallback_refresh_token=refresh_token,
                )
                self._apply_tokens_to_session(session_record=session_record, tokens=tokens)
                encrypted_refresh = self._token_cipher.encrypt(tokens.refresh_token)
                user_state.refresh_token_encrypted = encrypted_refresh
                user_state.updated_at_epoch = int(time.time())
                await db.commit()
                return tokens.bearer_token, session_record.user_key

    async def login(
        self,
        email: str,
        password: str,
        persist_refresh_token: bool = True,
    ) -> tuple[dict[str, Any], str]:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise HTTPException(status_code=422, detail="Email is required.")
        if not password:
            raise HTTPException(status_code=422, detail="Password is required.")

        token_payload = await self._oauth_login_with_credentials(
            username=normalized_email,
            password=password,
        )
        tokens = self._session_tokens_from_payload(
            token_payload=token_payload,
            username=normalized_email,
            fallback_refresh_token=None,
        )
        session_id = secrets.token_urlsafe(48)
        user_key = normalized_email
        now_epoch = int(time.time())

        async with self._lock:
            async with self._session_factory() as db:
                user_state = await db.get(UserAuthState, user_key)
                if not user_state:
                    user_state = UserAuthState(
                        user_key=user_key,
                        refresh_token_encrypted=None,
                        username=normalized_email,
                        updated_at_epoch=now_epoch,
                    )
                    db.add(user_state)

                user_state.username = normalized_email
                user_state.updated_at_epoch = now_epoch
                if persist_refresh_token:
                    user_state.refresh_token_encrypted = self._token_cipher.encrypt(tokens.refresh_token)
                else:
                    user_state.refresh_token_encrypted = None

                session_record = BrowserSession(
                    session_id=session_id,
                    user_key=user_key,
                    access_token=tokens.access_token,
                    id_token=tokens.id_token,
                    expires_at_epoch=tokens.expires_at_epoch,
                    last_seen_epoch=time.time(),
                    created_at_epoch=time.time(),
                    revoked=False,
                )
                db.add(session_record)
                await db.commit()

        status = await self.status(session_id=session_id)
        return status, session_id

    async def logout(self, session_id: str | None, all_devices: bool = False) -> dict[str, Any]:
        normalized_session_id = (session_id or "").strip()
        if not normalized_session_id:
            return self._anonymous_status()

        async with self._lock:
            async with self._session_factory() as db:
                session_record = await db.get(BrowserSession, normalized_session_id)
                if not session_record:
                    return self._anonymous_status()

                if all_devices:
                    user_key = session_record.user_key
                    user_state = await db.get(UserAuthState, user_key)
                    if user_state:
                        user_state.refresh_token_encrypted = None
                        user_state.updated_at_epoch = int(time.time())

                    query = select(BrowserSession).where(BrowserSession.user_key == user_key)
                    rows = (await db.execute(query)).scalars().all()
                    for row in rows:
                        row.revoked = True
                else:
                    session_record.revoked = True

                await db.commit()
                return self._anonymous_status()

    async def status(self, session_id: str | None) -> dict[str, Any]:
        normalized_session_id = (session_id or "").strip()
        if not normalized_session_id:
            return self._anonymous_status()

        async with self._lock:
            async with self._session_factory() as db:
                session_record = await db.get(BrowserSession, normalized_session_id)
                if not session_record or session_record.revoked:
                    return self._anonymous_status()

                user_state = await db.get(UserAuthState, session_record.user_key)
                if not user_state:
                    session_record.revoked = True
                    await db.commit()
                    return self._anonymous_status()

                has_refresh_token = bool(self._token_cipher.decrypt(user_state.refresh_token_encrypted))
                username = user_state.username

                if self._has_valid_session_token(session_record):
                    session_record.last_seen_epoch = time.time()
                    await db.commit()
                    return {
                        "authenticated": True,
                        "auth_mode": "session",
                        "has_refresh_token": has_refresh_token,
                        "username": username,
                        "auth_state": "ok",
                        "needs_relogin": False,
                    }

                refresh_token = self._token_cipher.decrypt(user_state.refresh_token_encrypted)
                if not refresh_token:
                    session_record.revoked = True
                    await db.commit()
                    return {
                        "authenticated": False,
                        "auth_mode": "session",
                        "has_refresh_token": False,
                        "username": username,
                        "auth_state": "expired",
                        "needs_relogin": True,
                    }

                try:
                    token_payload = await self._oauth_refresh_tokens(refresh_token=refresh_token)
                except HTTPException as exc:
                    if exc.status_code in {400, 401, 403}:
                        session_record.revoked = True
                        user_state.refresh_token_encrypted = None
                        user_state.updated_at_epoch = int(time.time())
                        await db.commit()
                        return {
                            "authenticated": False,
                            "auth_mode": "session",
                            "has_refresh_token": False,
                            "username": username,
                            "auth_state": "expired",
                            "needs_relogin": True,
                        }
                    return {
                        "authenticated": False,
                        "auth_mode": "session",
                        "has_refresh_token": True,
                        "username": username,
                        "auth_state": "network_error",
                        "needs_relogin": False,
                    }

                tokens = self._session_tokens_from_payload(
                    token_payload=token_payload,
                    username=username,
                    fallback_refresh_token=refresh_token,
                )
                self._apply_tokens_to_session(session_record=session_record, tokens=tokens)
                user_state.refresh_token_encrypted = self._token_cipher.encrypt(tokens.refresh_token)
                user_state.updated_at_epoch = int(time.time())
                await db.commit()
                return {
                    "authenticated": True,
                    "auth_mode": "session",
                    "has_refresh_token": bool(tokens.refresh_token),
                    "username": username,
                    "auth_state": "ok",
                    "needs_relogin": False,
                }

    async def get_preferences(
        self,
        user_key: str,
        *,
        fallback_pinned_task_ids: list[str] | None = None,
    ) -> PreferencesPayload:
        normalized_user_key = user_key.strip().lower()
        if not normalized_user_key:
            raise HTTPException(status_code=422, detail="Missing user key.")
        now_epoch = int(time.time())
        fallback_pins = [str(item) for item in (fallback_pinned_task_ids or [])]

        async with self._session_factory() as db:
            row = await db.get(UserPreferences, normalized_user_key)
            if not row:
                row = UserPreferences(
                    user_key=normalized_user_key,
                    pinned_task_ids_json=json.dumps(fallback_pins),
                    task_ui_preferences_json=json.dumps({}),
                    version=1,
                    updated_at_epoch=now_epoch,
                )
                db.add(row)
                await db.commit()
            return PreferencesPayload(
                pinned_task_ids=row.pinned_task_ids(),
                task_ui_preferences=row.task_ui_preferences(),
                version=int(row.version),
                updated_at_epoch=int(row.updated_at_epoch),
            )

    async def update_preferences(
        self,
        user_key: str,
        *,
        pinned_task_ids: list[str],
        task_ui_preferences: dict[str, Any],
        expected_version: int | None,
    ) -> PreferencesPayload:
        normalized_user_key = user_key.strip().lower()
        if not normalized_user_key:
            raise HTTPException(status_code=422, detail="Missing user key.")

        normalized_pins = [str(item) for item in pinned_task_ids]
        normalized_task_ui_preferences = {
            str(key): value for key, value in (task_ui_preferences or {}).items()
        }
        now_epoch = int(time.time())

        async with self._session_factory() as db:
            row = await db.get(UserPreferences, normalized_user_key)
            base_version = 0
            if row:
                base_version = int(row.version)
            if expected_version is not None and expected_version != base_version:
                raise HTTPException(
                    status_code=409,
                    detail="Preferences update conflict. Reload latest preferences and retry.",
                )

            next_version = base_version + 1
            if not row:
                row = UserPreferences(
                    user_key=normalized_user_key,
                    pinned_task_ids_json="[]",
                    task_ui_preferences_json="{}",
                    version=next_version,
                    updated_at_epoch=now_epoch,
                )
                db.add(row)

            row.pinned_task_ids_json = json.dumps(normalized_pins)
            row.task_ui_preferences_json = json.dumps(normalized_task_ui_preferences)
            row.version = next_version
            row.updated_at_epoch = now_epoch
            await db.commit()

            return PreferencesPayload(
                pinned_task_ids=normalized_pins,
                task_ui_preferences=normalized_task_ui_preferences,
                version=next_version,
                updated_at_epoch=now_epoch,
            )

    async def save_bootstrap_cache(
        self,
        user_key: str,
        payload: dict[str, Any],
        *,
        fetched_at_epoch: int,
    ) -> None:
        normalized_user_key = user_key.strip().lower()
        if not normalized_user_key:
            return
        async with self._session_factory() as db:
            row = await db.get(BootstrapCache, normalized_user_key)
            serialized_payload = json.dumps(payload)
            if not row:
                row = BootstrapCache(
                    user_key=normalized_user_key,
                    payload_json=serialized_payload,
                    fetched_at_epoch=fetched_at_epoch,
                )
                db.add(row)
            else:
                row.payload_json = serialized_payload
                row.fetched_at_epoch = fetched_at_epoch
            await db.commit()

    async def load_bootstrap_cache(self, user_key: str) -> tuple[dict[str, Any], int] | None:
        normalized_user_key = user_key.strip().lower()
        if not normalized_user_key:
            return None
        max_age_seconds = max(0, int(self._settings.bootstrap_cache_max_age_seconds))
        now_epoch = int(time.time())
        async with self._session_factory() as db:
            row = await db.get(BootstrapCache, normalized_user_key)
            if not row:
                return None
            if max_age_seconds > 0 and (now_epoch - int(row.fetched_at_epoch)) > max_age_seconds:
                return None
            payload = row.payload()
            if not payload:
                return None
            return payload, int(row.fetched_at_epoch)

    def _has_valid_session_token(self, session_record: BrowserSession) -> bool:
        return (
            float(session_record.expires_at_epoch) - self._settings.auth_refresh_skew_seconds
        ) > time.time()

    def _resolve_bearer_token(self, session_record: BrowserSession) -> str:
        bearer = (session_record.id_token or "").strip() or (session_record.access_token or "").strip()
        if not bearer:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Authentication required. Sign in with your ChessDojo email and password."
                ),
            )
        return bearer

    def _apply_tokens_to_session(self, session_record: BrowserSession, tokens: SessionTokens) -> None:
        session_record.access_token = tokens.access_token
        session_record.id_token = tokens.id_token
        session_record.expires_at_epoch = tokens.expires_at_epoch
        session_record.last_seen_epoch = time.time()
        session_record.revoked = False

    def _session_tokens_from_payload(
        self,
        *,
        token_payload: dict[str, Any],
        username: str | None,
        fallback_refresh_token: str | None,
    ) -> SessionTokens:
        id_token = str(token_payload.get("id_token", "")).strip()
        access_token = str(token_payload.get("access_token", "")).strip()
        if not id_token and not access_token:
            raise HTTPException(status_code=502, detail="Missing OAuth bearer token.")
        raw_refresh_token = str(token_payload.get("refresh_token", "")).strip()
        refresh_token = raw_refresh_token or (fallback_refresh_token or "").strip() or None
        expires_in_seconds = max(_to_int(token_payload.get("expires_in"), fallback=3600), 60)
        return SessionTokens(
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh_token,
            expires_at_epoch=time.time() + expires_in_seconds,
            username=username,
        )

    def _anonymous_status(self) -> dict[str, Any]:
        return {
            "authenticated": False,
            "auth_mode": "none",
            "has_refresh_token": False,
            "username": None,
            "auth_state": "expired",
            "needs_relogin": True,
        }

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
