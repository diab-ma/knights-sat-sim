"""HTTP polling with the real session engine and Sim.

Container creation and the bridge listener are substituted; these tests do not
claim real Docker startup, terminal operation, or container cleanup coverage.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api import progress
from api.main import app
from api.script_bridge import ScriptBridge
from api.session import ChallengeFiles, SessionService
from sim.clock import ManualTime
from sim.service import HELLO, SimService


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def manual_time():
    return ManualTime()


@pytest.fixture
def engine(client, tmp_path, monkeypatch, manual_time):
    controller = SimpleNamespace(
        storage=SimpleNamespace(paths={"bridge": tmp_path}),
        create=AsyncMock(),
        destroy=AsyncMock(),
    )
    bridge = ScriptBridge()
    monkeypatch.setattr(bridge, "start", AsyncMock())
    service = SessionService(
        controller,
        bridge,
        SimService(manual_time, manual_time),
        {HELLO: ChallengeFiles({}, {})},
    )
    monkeypatch.setattr(app.state, "session_service", service, raising=False)
    yield service
    client.portal.call(service.stop)


def test_no_engine_means_no_session(client):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {"session": None}


def test_idle_engine(client, engine):
    assert client.get("/api/session").json() == {"session": None}
    engine.controller.create.assert_not_awaited()
    assert progress.read_completed() == set()


def test_running_hello_and_stop(client, engine, manual_time):
    started = client.portal.call(engine.start, HELLO)
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {
        "session": started.model_dump(mode="json", by_alias=True)
    }
    session = response.json()["session"]
    assert session["challenge_id"] == HELLO
    assert session["status"] == "running"
    assert session["pass"] is None
    assert "pass_view" not in session
    assert session["completion"] == "not_yet"
    assert progress.read_completed() == set()

    # A poll reads fresh Sim state instead of caching the start response.
    client.portal.call(manual_time.advance, 3)
    updated = client.get("/api/session").json()["session"]
    assert updated["state"]["uptime_s"] == 3
    assert updated["session_id"] == session["session_id"]
    engine.controller.create.assert_awaited_once()

    resources = engine.controller.create.call_args.kwargs["resources"]
    secret = json.loads(resources["connection.json"])["credential"]
    assert secret not in response.text
    assert "connection.json" not in response.text
    assert progress.read_completed() == set()

    client.portal.call(engine.stop)
    assert client.get("/api/session").json() == {"session": None}


def test_session_contract_in_openapi_and_docs(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/session"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SessionResponse"
    }
    models = schema["components"]["schemas"]
    assert models["SessionResponse"]["properties"]["session"]["anyOf"] == [
        {"$ref": "#/components/schemas/Session"},
        {"type": "null"},
    ]
    assert "pass" in models["Session"]["properties"]
    assert "pass_view" not in models["Session"]["properties"]
    assert client.get("/docs").status_code == 200
