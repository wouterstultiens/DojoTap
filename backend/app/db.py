from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import BIGINT, BOOLEAN, FLOAT, TEXT, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def normalize_database_url(raw_url: str) -> str:
    value = raw_url.strip()
    if value.startswith("postgres://"):
        return f"postgresql+asyncpg://{value[len('postgres://') :]}"
    if value.startswith("postgresql://"):
        return f"postgresql+asyncpg://{value[len('postgresql://') :]}"
    if value.startswith("sqlite:///"):
        return f"sqlite+aiosqlite:///{value[len('sqlite:///') :]}"
    if value.startswith("sqlite://"):
        return "sqlite+aiosqlite:///:memory:"
    return value


class Base(DeclarativeBase):
    pass


class UserAuthState(Base):
    __tablename__ = "user_auth_state"

    user_key: Mapped[str] = mapped_column(String(320), primary_key=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    username: Mapped[str | None] = mapped_column(String(320), nullable=True)
    updated_at_epoch: Mapped[int] = mapped_column(BIGINT, nullable=False)


class BrowserSession(Base):
    __tablename__ = "browser_session"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_key: Mapped[str] = mapped_column(
        String(320),
        ForeignKey("user_auth_state.user_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_token: Mapped[str] = mapped_column(TEXT, nullable=False, default="")
    id_token: Mapped[str] = mapped_column(TEXT, nullable=False, default="")
    expires_at_epoch: Mapped[float] = mapped_column(FLOAT, nullable=False)
    last_seen_epoch: Mapped[float] = mapped_column(FLOAT, nullable=False)
    created_at_epoch: Mapped[float] = mapped_column(FLOAT, nullable=False)
    revoked: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_key: Mapped[str] = mapped_column(String(320), primary_key=True)
    pinned_task_ids_json: Mapped[str] = mapped_column(TEXT, nullable=False, default="[]")
    task_ui_preferences_json: Mapped[str] = mapped_column(TEXT, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(BIGINT, nullable=False, default=1)
    updated_at_epoch: Mapped[int] = mapped_column(BIGINT, nullable=False)

    def pinned_task_ids(self) -> list[str]:
        parsed = _safe_json(self.pinned_task_ids_json)
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]

    def task_ui_preferences(self) -> dict[str, Any]:
        parsed = _safe_json(self.task_ui_preferences_json)
        if not isinstance(parsed, dict):
            return {}
        return {str(key): value for key, value in parsed.items()}


class BootstrapCache(Base):
    __tablename__ = "bootstrap_cache"

    user_key: Mapped[str] = mapped_column(String(320), primary_key=True)
    payload_json: Mapped[str] = mapped_column(TEXT, nullable=False)
    fetched_at_epoch: Mapped[int] = mapped_column(BIGINT, nullable=False)

    def payload(self) -> dict[str, Any]:
        parsed = _safe_json(self.payload_json)
        if isinstance(parsed, dict):
            return parsed
        return {}


@dataclass(slots=True)
class PreferencesPayload:
    pinned_task_ids: list[str]
    task_ui_preferences: dict[str, Any]
    version: int
    updated_at_epoch: int


class Database:
    def __init__(self, database_url: str):
        self._engine: AsyncEngine = create_async_engine(
            normalize_database_url(database_url),
            pool_pre_ping=True,
            future=True,
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def init(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()


def _safe_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
