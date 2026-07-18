"""Tests for Phase 6: settings, scheduler, credentials repositories + engine methods."""

from __future__ import annotations

import time

import pytest

from mediahub_engine.database import (
    CredentialsRepository,
    Database,
    SchedulerRepository,
    SettingsRepository,
)
from mediahub_engine.database.scheduler_repository import ScheduledTask, ScheduleType
from mediahub_engine.providers.base import Credential


@pytest.fixture
def repos(tmp_path: pytest.TempPathFactory):
    db = Database(tmp_path / "test.db")
    yield (
        SettingsRepository(db),
        SchedulerRepository(db),
        CredentialsRepository(db),
        db,
    )
    db.close()


# ---------------------------------------------------------------------------
# SettingsRepository
# ---------------------------------------------------------------------------


def test_settings_get_returns_default(repos) -> None:
    settings, _, _, _ = repos
    assert settings.get("download.maxConcurrent") == 4
    assert settings.get("nonexistent", "fallback") == "fallback"


def test_settings_set_and_get(repos) -> None:
    settings, _, _, _ = repos
    settings.set("download.maxConcurrent", 8)
    assert settings.get("download.maxConcurrent") == 8


def test_settings_set_many(repos) -> None:
    settings, _, _, _ = repos
    settings.set_many({"download.maxConcurrent": 2, "appearance.themeMode": "dark"})
    assert settings.get("download.maxConcurrent") == 2
    assert settings.get("appearance.themeMode") == "dark"


def test_settings_get_all_merges_defaults(repos) -> None:
    settings, _, _, _ = repos
    settings.set("download.maxConcurrent", 16)
    all_settings = settings.get_all()
    assert all_settings["download.maxConcurrent"] == 16
    assert all_settings["appearance.themeMode"] == "system"  # default


def test_settings_delete(repos) -> None:
    settings, _, _, _ = repos
    settings.set("custom.key", "value")
    assert settings.delete("custom.key") is True
    assert settings.get("custom.key") is None


def test_settings_reset(repos) -> None:
    settings, _, _, _ = repos
    settings.set("download.maxConcurrent", 99)
    settings.reset()
    assert settings.get("download.maxConcurrent") == 4  # back to default


# ---------------------------------------------------------------------------
# SchedulerRepository
# ---------------------------------------------------------------------------


def test_scheduler_create_one_time(repos) -> None:
    _, scheduler, _, _ = repos
    task = ScheduledTask(
        url="https://example.com/a.mp4",
        schedule_type=ScheduleType.ONE_TIME,
        scheduled_at=time.time() + 3600,
    )
    scheduler.create(task)
    fetched = scheduler.get(task.schedule_id)
    assert fetched is not None
    assert fetched.url == "https://example.com/a.mp4"
    assert fetched.next_run_at is not None


def test_scheduler_create_interval(repos) -> None:
    _, scheduler, _, _ = repos
    task = ScheduledTask(
        url="https://example.com/a.mp4",
        schedule_type=ScheduleType.INTERVAL,
        interval_seconds=600,
    )
    scheduler.create(task)
    fetched = scheduler.get(task.schedule_id)
    assert fetched is not None
    assert fetched.next_run_at is not None
    assert fetched.next_run_at > time.time()


def test_scheduler_list(repos) -> None:
    _, scheduler, _, _ = repos
    scheduler.create(
        ScheduledTask(
            url="https://a", schedule_type=ScheduleType.ONE_TIME, scheduled_at=time.time() + 100
        )
    )
    scheduler.create(
        ScheduledTask(
            url="https://b", schedule_type=ScheduleType.ONE_TIME, scheduled_at=time.time() + 200
        )
    )
    assert len(scheduler.list()) == 2


def test_scheduler_list_enabled_only(repos) -> None:
    _, scheduler, _, _ = repos
    t1 = ScheduledTask(
        url="https://a", schedule_type=ScheduleType.ONE_TIME, scheduled_at=time.time() + 100
    )
    scheduler.create(t1)
    t2 = ScheduledTask(
        url="https://b",
        schedule_type=ScheduleType.ONE_TIME,
        scheduled_at=time.time() + 200,
        enabled=False,
    )
    scheduler.create(t2)
    enabled = scheduler.list(enabled_only=True)
    assert len(enabled) == 1
    assert enabled[0].url == "https://a"


def test_scheduler_set_enabled(repos) -> None:
    _, scheduler, _, _ = repos
    task = ScheduledTask(
        url="https://a",
        schedule_type=ScheduleType.ONE_TIME,
        scheduled_at=time.time() + 100,
        enabled=True,
    )
    scheduler.create(task)
    assert scheduler.set_enabled(task.schedule_id, False) is True
    assert scheduler.get(task.schedule_id).enabled is False  # type: ignore[union-attr]


def test_scheduler_delete(repos) -> None:
    _, scheduler, _, _ = repos
    task = ScheduledTask(
        url="https://a", schedule_type=ScheduleType.ONE_TIME, scheduled_at=time.time() + 100
    )
    scheduler.create(task)
    assert scheduler.delete(task.schedule_id) is True
    assert scheduler.get(task.schedule_id) is None


def test_scheduler_due_returns_past_schedules(repos) -> None:
    _, scheduler, _, _ = repos
    # A one-time schedule in the past.
    past = ScheduledTask(
        url="https://past",
        schedule_type=ScheduleType.ONE_TIME,
        scheduled_at=time.time() - 60,
    )
    scheduler.create(past)
    # A one-time schedule in the future.
    future = ScheduledTask(
        url="https://future",
        schedule_type=ScheduleType.ONE_TIME,
        scheduled_at=time.time() + 3600,
    )
    scheduler.create(future)

    due = scheduler.due_schedules()
    assert len(due) == 1
    assert due[0].url == "https://past"


def test_scheduler_mark_run_disables_one_time(repos) -> None:
    _, scheduler, _, _ = repos
    task = ScheduledTask(
        url="https://a",
        schedule_type=ScheduleType.ONE_TIME,
        scheduled_at=time.time() - 10,
    )
    scheduler.create(task)
    scheduler.mark_run(task.schedule_id)

    fetched = scheduler.get(task.schedule_id)
    assert fetched is not None  # type: ignore[union-attr]
    assert fetched.enabled is False  # type: ignore[union-attr]
    assert fetched.run_count == 1  # type: ignore[union-attr]
    assert fetched.last_run_at is not None  # type: ignore[union-attr]


def test_scheduler_mark_run_advances_interval(repos) -> None:
    _, scheduler, _, _ = repos
    task = ScheduledTask(
        url="https://a",
        schedule_type=ScheduleType.INTERVAL,
        interval_seconds=600,
    )
    scheduler.create(task)
    original_next = task.next_run_at
    scheduler.mark_run(task.schedule_id)

    fetched = scheduler.get(task.schedule_id)
    assert fetched is not None  # type: ignore[union-attr]
    assert fetched.run_count == 1  # type: ignore[union-attr]
    assert fetched.next_run_at is not None  # type: ignore[union-attr]
    assert fetched.next_run_at > (original_next or 0)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# CredentialsRepository
# ---------------------------------------------------------------------------


def test_credentials_set_and_get(repos) -> None:
    _, _, creds, _ = repos
    cred = Credential(
        username="user1",
        password="secret123",
        cookies_path="/c.jar",
        token="tok456",
    )
    creds.set("youtube", cred)

    fetched = creds.get("youtube")
    assert fetched is not None
    assert fetched.username == "user1"
    assert fetched.password == "secret123"  # decrypted
    assert fetched.token == "tok456"  # decrypted
    assert fetched.cookies_path == "/c.jar"


def test_credentials_password_is_encrypted_at_rest(repos) -> None:
    _, _, creds, db = repos
    creds.set("instagram", Credential(password="my-secret"))
    # Read the raw DB row — password must NOT be plaintext.
    row = db.query_one("SELECT password FROM credentials WHERE provider = 'instagram'")
    assert row is not None
    assert "my-secret" not in row["password"]  # encrypted


def test_credentials_list_providers(repos) -> None:
    _, _, creds, _ = repos
    creds.set("youtube", Credential(username="u"))
    creds.set("instagram", Credential(username="i"))

    providers = creds.list_providers()
    assert set(providers) == {"youtube", "instagram"}


def test_credentials_has(repos) -> None:
    _, _, creds, _ = repos
    creds.set("youtube", Credential(username="u"))
    assert creds.has("youtube") is True
    assert creds.has("tiktok") is False


def test_credentials_delete(repos) -> None:
    _, _, creds, _ = repos
    creds.set("youtube", Credential(username="u"))
    assert creds.delete("youtube") is True
    assert creds.get("youtube") is None


def test_credentials_update_overwrites(repos) -> None:
    _, _, creds, _ = repos
    creds.set("youtube", Credential(username="old", password="old"))
    creds.set("youtube", Credential(username="new", password="new"))

    fetched = creds.get("youtube")
    assert fetched is not None
    assert fetched.username == "new"
    assert fetched.password == "new"


# ---------------------------------------------------------------------------
# Engine methods (integration)
# ---------------------------------------------------------------------------


def _make_engine(tmp_path):
    from mediahub_engine.config import EngineConfig
    from mediahub_engine.engine import Engine

    return Engine(config=EngineConfig(work_dir=tmp_path / "work", persist_downloads=True))


@pytest.mark.asyncio
async def test_engine_settings_round_trip(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    await engine._settings_set({"key": "download.maxConcurrent", "value": 12})
    result = await engine._settings_get({"key": "download.maxConcurrent"})
    assert result["value"] == 12


@pytest.mark.asyncio
async def test_engine_settings_get_all(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    result = await engine._settings_get_all({})
    assert "settings" in result
    assert result["settings"]["download.maxConcurrent"] == 4  # default


@pytest.mark.asyncio
async def test_engine_scheduler_create_and_list(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    created = await engine._scheduler_create(
        {
            "url": "https://example.com/a.mp4",
            "scheduleType": "interval",
            "intervalSeconds": 300,
        }
    )
    assert created["url"] == "https://example.com/a.mp4"

    listed = await engine._scheduler_list({})
    assert len(listed["schedules"]) == 1


@pytest.mark.asyncio
async def test_engine_credentials_set_and_get(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    await engine._credentials_set(
        {
            "provider": "youtube",
            "username": "user",
            "password": "secret",
        }
    )

    result = await engine._credentials_get({"provider": "youtube"})
    cred = result["credential"]
    assert cred["username"] == "user"
    assert cred["hasPassword"] is True
    # Password must NOT be returned in plaintext.
    assert "password" not in cred or cred.get("password") is None


@pytest.mark.asyncio
async def test_engine_credentials_list(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    await engine._credentials_set({"provider": "youtube", "username": "u"})
    await engine._credentials_set({"provider": "instagram", "username": "i"})

    result = await engine._credentials_list({})
    assert set(result["providers"]) == {"youtube", "instagram"}


@pytest.mark.asyncio
async def test_engine_scheduler_due(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    # Create a one-time schedule in the past.
    await engine._scheduler_create(
        {
            "url": "https://past",
            "scheduleType": "one_time",
            "scheduledAt": time.time() - 100,
        }
    )
    result = await engine._scheduler_due({})
    assert len(result["schedules"]) == 1
