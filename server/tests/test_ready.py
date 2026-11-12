import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from api import progress
from api.main import app
from api.ready import CHALLENGE_ID

BASE = "/api/challenges/ready-for-the-pass"
CORRECT = {
    "satellite_id": "KNIGHTSAT",
    "pass_start_utc": "2026-09-21T18:00:00Z",
    "receive_frequency_hz": 145825000,
    "receive_mode": "FM",
    "tracking_enabled": True,
}


@pytest.fixture(autouse=True)
def disable_unlock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEV_UNLOCK_ALL", raising=False)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def unlock() -> None:
    progress.save_completion("hello-satellite")


def test_locked_routes(client: TestClient) -> None:
    for response in (
        client.get(f"{BASE}/brief"),
        client.post(f"{BASE}/check", json=CORRECT),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CHALLENGE_LOCKED"
    assert progress.read_completed() == set()


def test_brief_and_starting_mistakes(client: TestClient) -> None:
    unlock()
    brief = client.get(f"{BASE}/brief").json()
    assert brief == {
        "scenario_id": "knightsat-training-v1",
        "brief": CORRECT,
        "starting_setup": {
            **CORRECT,
            "receive_frequency_hz": 145800000,
            "tracking_enabled": False,
        },
    }
    result = client.post(f"{BASE}/check", json=brief["starting_setup"])
    assert result.status_code == 200
    assert result.json()["completion"] == "not_yet"
    assert {
        item["field"] for item in result.json()["checks"] if not item["passed"]
    } == {"receive_frequency_hz", "tracking_enabled"}
    assert progress.read_completed() == {"hello-satellite"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("satellite_id", "PRACTICE-B"),
        ("pass_start_utc", "2026-09-21T19:00:00Z"),
        ("receive_frequency_hz", 145800000),
        ("receive_mode", "AM"),
        ("tracking_enabled", False),
    ],
)
def test_each_wrong_setting(client: TestClient, field: str, value: object) -> None:
    unlock()
    response = client.post(f"{BASE}/check", json={**CORRECT, field: value})
    assert response.status_code == 200
    data = response.json()
    assert data["completion"] == "not_yet"
    assert len(data["checks"]) == 5
    failed = [check for check in data["checks"] if not check["passed"]]
    assert len(failed) == 1 and failed[0]["field"] == field
    assert failed[0]["message"]
    assert CHALLENGE_ID not in progress.read_completed()


def test_success_repeats_and_later_failure_preserve_progress(
    client: TestClient,
) -> None:
    unlock()
    for _ in range(2):
        response = client.post(f"{BASE}/check", json=CORRECT)
        assert response.status_code == 200
        assert response.json()["completion"] == "saved"
        assert all(check["passed"] for check in response.json()["checks"])
    assert (
        client.get("/api/challenges").json()["challenges"][2]["availability"]
        == "available"
    )
    client.post(f"{BASE}/check", json={**CORRECT, "tracking_enabled": False})
    assert CHALLENGE_ID in progress.read_completed()
    assert (
        client.get(f"{BASE}/brief").json()["starting_setup"]["tracking_enabled"]
        is False
    )


def test_dev_unlock_does_not_complete_hello(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEV_UNLOCK_ALL", "1")
    assert client.get(f"{BASE}/brief").status_code == 200
    assert progress.read_completed() == set()
    assert client.post(f"{BASE}/check", json=CORRECT).json()["completion"] == "saved"
    assert progress.read_completed() == {CHALLENGE_ID}


def test_real_sqlite_save_failure(client: TestClient) -> None:
    unlock()
    with closing(progress.connect()) as connection, connection:
        connection.execute(
            "CREATE TRIGGER reject_completion BEFORE INSERT ON challenge_completion "
            "BEGIN SELECT RAISE(ABORT, 'storage failure'); END"
        )
    response = client.post(f"{BASE}/check", json=CORRECT)
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert data["completion"] == "save_failed"
    assert all(check["passed"] for check in data["checks"])
    assert progress.read_completed() == {"hello-satellite"}
    assert (
        client.get("/api/challenges").json()["challenges"][2]["availability"]
        == "locked"
    )


def test_read_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> set[str]:
        raise sqlite3.OperationalError("unavailable")

    monkeypatch.setattr(progress, "read_completed", fail)
    assert client.get(f"{BASE}/brief").status_code == 503
    assert client.post(f"{BASE}/check", json=CORRECT).status_code == 503


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receive_frequency_hz", 0),
        ("receive_frequency_hz", -1),
        ("receive_frequency_hz", 145825000.5),
        ("receive_frequency_hz", "145825000"),
        ("receive_frequency_hz", True),
        ("tracking_enabled", "true"),
        ("satellite_id", 1),
        ("receive_mode", None),
        ("pass_start_utc", 123),
    ],
)
def test_invalid_input(client: TestClient, field: str, value: object) -> None:
    unlock()
    response = client.post(f"{BASE}/check", json={**CORRECT, field: value})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert CHALLENGE_ID not in progress.read_completed()


def test_missing_and_malformed_input(client: TestClient) -> None:
    unlock()
    for kwargs in ({"json": {}}, {"content": "{"}):
        response = client.post(f"{BASE}/check", **kwargs)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_origin_enforcement(client: TestClient) -> None:
    unlock()
    response = client.post(
        f"{BASE}/check", json=CORRECT, headers={"Origin": "https://other.test"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"
    assert CHALLENGE_ID not in progress.read_completed()
    assert (
        client.post(
            f"{BASE}/check", json=CORRECT, headers={"Origin": "http://testserver"}
        ).status_code
        == 200
    )
