import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import progress
from api.main import app


def test_migrating_twice_preserves_completion() -> None:
    progress.migrate()
    progress.save_completion("hello-satellite")
    progress.migrate()
    with closing(progress.connect()) as connection:
        assert connection.execute("SELECT * FROM schema_migrations").fetchall() == [
            (1,)
        ]
    assert progress.read_completed() == {"hello-satellite"}


def test_duplicate_save_preserves_first_timestamp() -> None:
    progress.migrate()
    progress.save_completion("hello-satellite")
    with closing(progress.connect()) as connection:
        first = connection.execute("SELECT * FROM challenge_completion").fetchall()
    progress.save_completion("hello-satellite")
    with closing(progress.connect()) as connection:
        assert (
            connection.execute("SELECT * FROM challenge_completion").fetchall() == first
        )
    assert datetime.fromisoformat(first[0][1]).utcoffset() == timedelta(0)


def test_saved_progress_survives_application_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEV_UNLOCK_ALL", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/challenges").json()["progress"] == {
            "completed_challenge_ids": []
        }
        progress.save_completion("hello-satellite")
    with TestClient(app) as client:
        response = client.get("/api/challenges")
    assert response.status_code == 200
    data = response.json()
    assert data["progress"] == {"completed_challenge_ids": ["hello-satellite"]}
    assert data["challenges"][0]["completed"] is True
    assert data["challenges"][1]["availability"] == "available"
    assert data["challenges"][2]["availability"] == "locked"


def test_failed_migration_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(progress, "MIGRATIONS", ((1, "INVALID SQL"),))
    with pytest.raises(sqlite3.OperationalError):
        progress.migrate()
    with closing(progress.connect()) as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            == []
        )


def test_migration_failure_stops_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path))
    with pytest.raises(sqlite3.OperationalError), TestClient(app):
        pytest.fail("Startup should fail when the database cannot be opened")


def test_default_path_creates_data_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SQLITE_PATH")
    progress.migrate()
    assert (tmp_path / "data" / "progress.db").is_file()


def test_failed_save_does_not_record_completion() -> None:
    progress.migrate()
    with closing(progress.connect()) as connection, connection:
        connection.execute(
            "CREATE TRIGGER reject_completion BEFORE INSERT ON challenge_completion "
            "BEGIN SELECT RAISE(ABORT, 'storage failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="storage failure"):
        progress.save_completion("hello-satellite")
    assert progress.read_completed() == set()
