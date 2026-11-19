import asyncio
from contextlib import closing
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import progress
from api.main import app

BODY = {"confirm": "RESET DEMO PROGRESS"}


@pytest.fixture
def client():
    with TestClient(app) as client:
        for challenge in ("hello-satellite", "ready-for-the-pass", "catch-and-log"):
            progress.save_completion(challenge)
        yield client


def test_reset_deletes_only_completion_and_is_repeatable(client):
    with closing(progress.connect()) as connection, connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('keep')")
    for _ in range(2):
        response = client.post("/api/progress/reset", json=BODY)
        assert response.status_code == 200
        assert response.json() == {"completed_challenge_ids": []}
    with closing(progress.connect()) as connection:
        assert connection.execute("SELECT * FROM schema_migrations").fetchall() == [
            (1,)
        ]
        assert connection.execute("SELECT * FROM sentinel").fetchall() == [("keep",)]
    challenges = client.get("/api/challenges").json()["challenges"]
    assert [item["availability"] for item in challenges] == [
        "available",
        "locked",
        "locked",
    ]
    assert not any(item["completed"] for item in challenges)


@pytest.mark.parametrize("body", [{}, {"confirm": "reset"}, {"confirm": True}])
def test_confirmation_required(client, body):
    response = client.post("/api/progress/reset", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert len(progress.read_completed()) == 3


@pytest.mark.parametrize("status", ["starting", "running", "failed"])
def test_session_blocks_reset(client, monkeypatch, status):
    service = SimpleNamespace(
        lock=asyncio.Lock(), read=lambda: SimpleNamespace(status=status)
    )
    monkeypatch.setattr(app.state, "session_service", service, raising=False)
    response = client.post("/api/progress/reset", json=BODY)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_ACTIVE"
    assert len(progress.read_completed()) == 3


def test_storage_failure_rolls_back(client):
    with closing(progress.connect()) as connection, connection:
        connection.execute(
            "CREATE TRIGGER reject_reset BEFORE DELETE ON challenge_completion "
            "BEGIN SELECT RAISE(ABORT, 'private error'); END"
        )
    response = client.post("/api/progress/reset", json=BODY)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert "private error" not in response.text
    assert len(progress.read_completed()) == 3


def test_origin_and_malformed_input(client):
    response = client.post(
        "/api/progress/reset", json=BODY, headers={"Origin": "https://other.test"}
    )
    assert response.status_code == 403
    assert len(progress.read_completed()) == 3
    assert client.post("/api/progress/reset", content="{").status_code == 422
    assert (
        client.post(
            "/api/progress/reset", json=BODY, headers={"Origin": "http://testserver"}
        ).status_code
        == 200
    )


def test_reset_waits_for_session_lifecycle_lock(client, monkeypatch):
    import httpx

    async def exercise():
        lock = asyncio.Lock()
        active = False
        service = SimpleNamespace(lock=lock, read=lambda: object() if active else None)
        monkeypatch.setattr(app.state, "session_service", service, raising=False)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as session:
            await lock.acquire()
            reset = asyncio.create_task(session.post("/api/progress/reset", json=BODY))
            await asyncio.sleep(0)
            assert not reset.done()
            # Session startup wins the lock; reset must recheck after acquiring it.
            active = True
            lock.release()
            response = await reset
            assert response.status_code == 409
            assert len(progress.read_completed()) == 3

    asyncio.run(exercise())
