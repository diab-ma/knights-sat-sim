"""HTTP contracts with the real engine/Sim; Docker and listener are substituted."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api import progress
from api.main import app
from api.runtime import RuntimeFailure
from api.script_bridge import ScriptBridge
from api.session import ChallengeFiles, SessionService
from sim.clock import ManualTime
from sim.service import CATCH, HELLO, READY, SimService


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("DEV_UNLOCK_ALL", raising=False)
    controller = SimpleNamespace(
        storage=SimpleNamespace(paths={"bridge": tmp_path}),
        create=AsyncMock(),
        destroy=AsyncMock(),
    )
    bridge = ScriptBridge()
    monkeypatch.setattr(bridge, "start", AsyncMock())
    clock = ManualTime()
    engine = SessionService(
        controller,
        bridge,
        SimService(clock, clock),
        {HELLO: ChallengeFiles({}, {}), CATCH: ChallengeFiles({}, {})},
    )
    monkeypatch.setattr(app.state, "session_service", engine, raising=False)
    with TestClient(app) as http:
        yield http, engine
        http.delete("/api/session")


@pytest.mark.parametrize("challenge", [HELLO, CATCH])
def test_start_stop_and_restart(client, challenge):
    http, engine = client
    if challenge == CATCH:
        progress.save_completion(READY)
    response = http.post("/api/session", json={"challenge_id": challenge})
    assert response.status_code == 201
    view = response.json()
    assert view["challenge_id"] == challenge
    assert view["status"] == "running"
    assert view["history"] == []
    assert view["completion"] == "not_yet"
    assert not view["goal_reached"]
    assert "pass" in view and "pass_view" not in view
    assert (view["pass"] is None) == (challenge == HELLO)
    assert "credential" not in response.text
    assert progress.read_completed() == ({READY} if challenge == CATCH else set())
    assert (
        http.post("/api/session", json={"challenge_id": challenge}).json()["error"][
            "code"
        ]
        == "SESSION_ACTIVE"
    )
    assert engine.read().session_id == view["session_id"]
    for _ in range(2):
        stopped = http.delete("/api/session")
        assert stopped.status_code == 204 and stopped.content == b""
    engine.controller.destroy.assert_awaited_once_with(clear_workspace=False)
    assert engine.read() is None
    restarted = http.post("/api/session", json={"challenge_id": challenge})
    assert restarted.status_code == 201
    assert restarted.json()["session_id"] != view["session_id"]


@pytest.mark.parametrize(
    "challenge,code",
    [
        (CATCH, "CHALLENGE_LOCKED"),
        (READY, "WRONG_CHALLENGE"),
        ("unknown", "WRONG_CHALLENGE"),
    ],
)
def test_admission_failure_keeps_slot_free(client, challenge, code):
    http, engine = client
    response = http.post("/api/session", json={"challenge_id": challenge})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert engine.read() is None
    engine.controller.create.assert_not_awaited()


@pytest.mark.parametrize(
    "body", [{}, None, [], {"challenge_id": 1}, {"challenge_id": ""}]
)
def test_invalid_input(client, body):
    http, engine = client
    response = http.post("/api/session", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert engine.read() is None


def test_malformed_json(client):
    http, _ = client
    response = http.post(
        "/api/session", content="{", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_foreign_origin_cannot_change_session(client, method):
    http, engine = client
    started = http.post("/api/session", json={"challenge_id": HELLO})
    response = http.request(
        method, "/api/session", content="{", headers={"Origin": "https://other.test"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"
    assert engine.read().session_id == started.json()["session_id"]


def test_same_origin_is_allowed(client):
    http, _ = client
    headers = {"Origin": "http://testserver"}
    assert (
        http.post(
            "/api/session", json={"challenge_id": HELLO}, headers=headers
        ).status_code
        == 201
    )
    assert http.delete("/api/session", headers=headers).status_code == 204


def test_runtime_and_cleanup_failure_keep_slot_until_retry(client):
    http, engine = client
    engine.controller.create.side_effect = RuntimeFailure(
        "RUNTIME_UNAVAILABLE", "Preparation failed; retry cleanup"
    )
    response = http.post("/api/session", json={"challenge_id": HELLO})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RUNTIME_UNAVAILABLE"
    assert engine.read().status == "failed"
    engine.controller.destroy.side_effect = OSError("private Docker error")
    response = http.delete("/api/session")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CLEANUP_FAILED"
    assert "private Docker error" not in response.text
    assert http.post("/api/session", json={"challenge_id": HELLO}).status_code == 409
    engine.controller.destroy.side_effect = None
    assert http.delete("/api/session").status_code == 204
    assert engine.read() is None


def test_storage_failure(client, monkeypatch):
    http, engine = client
    monkeypatch.setenv("SQLITE_PATH", "/dev/null/progress.db")
    response = http.post("/api/session", json={"challenge_id": HELLO})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert engine.read() is None


def test_unconfigured_runtime(client, monkeypatch):
    http, _ = client
    monkeypatch.delattr(app.state, "session_service")
    for method in ("POST", "DELETE"):
        response = http.request(method, "/api/session", json={"challenge_id": HELLO})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "RUNTIME_UNAVAILABLE"
