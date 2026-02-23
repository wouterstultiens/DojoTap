import asyncio

from backend.app.config import Settings
from backend.app.ct_auto_backfill import maybe_schedule_on_login, _resolve_storage_state_b64


def _make_settings(tmp_path, enabled: bool = True) -> Settings:
    return Settings(
        ct_auto_backfill_on_login=enabled,
        ct_auto_backfill_state_path=str(tmp_path / "ct_state.json"),
        ct_auto_backfill_summary_path=str(tmp_path / "ct_summary.json"),
    )


def test_maybe_schedule_on_login_only_once_per_day(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path, enabled=True)

    async def _fake_run_backfill_job(*, settings, username, password, today_iso):
        return None

    def _fake_create_task(coro):
        coro.close()
        loop = asyncio.get_running_loop()
        task = loop.create_future()
        task.set_result(None)
        return task

    monkeypatch.setattr(
        "backend.app.ct_auto_backfill._run_backfill_job",
        _fake_run_backfill_job,
    )
    monkeypatch.setattr(
        "backend.app.ct_auto_backfill.asyncio.create_task",
        _fake_create_task,
    )

    first = asyncio.run(
        maybe_schedule_on_login(
            settings=settings,
            username="user@example.com",
            password="secret",
        )
    )
    assert first["scheduled"] is True

    second = asyncio.run(
        maybe_schedule_on_login(
            settings=settings,
            username="user@example.com",
            password="secret",
        )
    )
    assert second["scheduled"] is False
    assert second["reason"] == "already_attempted_today"


def test_maybe_schedule_on_login_disabled(tmp_path) -> None:
    settings = _make_settings(tmp_path, enabled=False)
    result = asyncio.run(
        maybe_schedule_on_login(
            settings=settings,
            username="user@example.com",
            password="secret",
        )
    )
    assert result == {"scheduled": False, "reason": "disabled"}


def test_resolve_storage_state_prefers_file_over_env(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "ct_state.b64"
    state_path.write_text("from-file", encoding="utf-8")
    monkeypatch.setenv("CT_STORAGE_STATE_PATH", str(state_path))
    monkeypatch.setenv("CT_STORAGE_STATE_B64", "from-env")

    value, source = _resolve_storage_state_b64()

    assert value == "from-file"
    assert source == "file"


def test_resolve_storage_state_falls_back_to_env(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "missing.b64"
    monkeypatch.setenv("CT_STORAGE_STATE_PATH", str(state_path))
    monkeypatch.setenv("CT_STORAGE_STATE_B64", "from-env")

    value, source = _resolve_storage_state_b64()

    assert value == "from-env"
    assert source == "env"
