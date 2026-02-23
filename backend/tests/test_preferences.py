import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.auth import LocalAuthManager
from backend.app.config import Settings
from backend.app.crypto import TokenCipher
from backend.app.db import Database


def _make_manager(tmp_path: Path) -> tuple[Database, LocalAuthManager]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'dojotap-preferences-test.db'}",
        auth_state_encryption_key="unit-test-key",
    )
    database = Database(settings.database_url)
    manager = LocalAuthManager(
        settings=settings,
        session_factory=database.session_factory,
        token_cipher=TokenCipher(settings.auth_state_encryption_key),
    )
    return database, manager


def test_preferences_upsert_and_conflict(tmp_path: Path) -> None:
    database, manager = _make_manager(tmp_path)
    asyncio.run(database.init())

    initial = asyncio.run(
        manager.get_preferences("user@example.com", fallback_pinned_task_ids=["a", "b"])
    )
    assert initial.pinned_task_ids == ["a", "b"]
    assert initial.version == 1

    updated = asyncio.run(
        manager.update_preferences(
            "user@example.com",
            pinned_task_ids=["x"],
            task_ui_preferences={"x": {"count_label_mode": "increment", "tile_size": "small", "count_cap": 10}},
            expected_version=1,
        )
    )
    assert updated.pinned_task_ids == ["x"]
    assert updated.version == 2

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            manager.update_preferences(
                "user@example.com",
                pinned_task_ids=["y"],
                task_ui_preferences={},
                expected_version=1,
            )
        )
    assert exc_info.value.status_code == 409
    asyncio.run(database.dispose())
