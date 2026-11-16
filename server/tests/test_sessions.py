"""Public session admission checks that do not require a Docker engine."""

import asyncio
from pathlib import Path

import docker
import pytest

from api import progress
from api.runtime import RuntimeController, RuntimeStorage
from api.script_bridge import ScriptBridge
from api.session import ChallengeFiles, SessionFailure, SessionService
from sim.clock import ManualTime
from sim.service import CATCH, HELLO, READY, SimService


@pytest.fixture
def service(tmp_path: Path):
    # Explicit version avoids daemon discovery. Admission must not contact Docker.
    client = docker.DockerClient(base_url="unix:///no-docker.sock", version="1.45")
    controller = RuntimeController(
        client, RuntimeStorage("unit", {}, {"bridge": tmp_path}), image="unused"
    )
    time = ManualTime()
    service = SessionService(
        controller,
        ScriptBridge(),
        SimService(time, time),
        {HELLO: ChallengeFiles({}, {}), CATCH: ChallengeFiles({}, {})},
    )
    yield service
    client.close()


def test_admission_refuses_ready_and_locked_catch_without_reserving_slot(service):
    progress.migrate()

    async def check():
        for challenge, code in (
            (READY, "WRONG_CHALLENGE"),
            (CATCH, "CHALLENGE_LOCKED"),
        ):
            with pytest.raises(SessionFailure) as error:
                await service.start(challenge)
            assert error.value.code == code
            assert service.read() is None
        await service.stop()
        await service.stop()
        with pytest.raises(SessionFailure) as error:
            await service.save_completion("stale")
        assert error.value.code == "NO_SESSION"

    asyncio.run(check())


def test_progress_failure_is_reported_without_taking_the_slot(service):
    async def check():
        with pytest.raises(SessionFailure) as error:
            await service.start(HELLO)
        assert error.value.code == "STORAGE_UNAVAILABLE"
        assert service.read() is None

    asyncio.run(check())


def test_missing_challenge_assets_are_unavailable_without_taking_the_slot(service):
    from api.runtime import RuntimeFailure

    progress.migrate()
    service.files = {}

    async def check():
        with pytest.raises(RuntimeFailure) as error:
            await service.start(HELLO)
        assert error.value.code == "RUNTIME_UNAVAILABLE"
        assert service.read() is None

    asyncio.run(check())


def test_progress_parent_filesystem_failure_is_storage_unavailable(
    service,
    tmp_path,
    monkeypatch,
):
    parent = tmp_path / "not-a-directory"
    parent.write_text("sentinel")
    monkeypatch.setenv("SQLITE_PATH", str(parent / "progress.db"))

    async def check():
        with pytest.raises(SessionFailure) as error:
            await service.start(HELLO)
        assert error.value.code == "STORAGE_UNAVAILABLE"
        assert service.read() is None

    asyncio.run(check())
