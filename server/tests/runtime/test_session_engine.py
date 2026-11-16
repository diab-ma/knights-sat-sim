"""KSAT-12 engine acceptance against real Docker, Sim, SQLite and bridge."""

import asyncio
import json
import os

import docker
import pytest

from api import progress
from api.runtime import RuntimeController, RuntimeStorage
from api.script_bridge import ScriptBridge
from api.session import ChallengeFiles, SessionService
from sim.clock import ManualTime
from sim.service import CATCH, HELLO, SimService


@pytest.fixture
def engine():
    if "RUNTIME_DEPLOYMENT" not in os.environ:
        pytest.skip("Run real Docker checks with compose.runtime-test.yml")
    progress.migrate()
    client = docker.from_env()
    controller = RuntimeController(
        client, RuntimeStorage.from_environment(), image="knightsat-player:ksat11"
    )
    time = ManualTime()
    engine = SessionService(
        controller,
        ScriptBridge(),
        SimService(time, time),
        {
            HELLO: ChallengeFiles(
                {"notes.txt": b"", "ping_example.py": b"# asset fixture\n"}, {}
            ),
            CATCH: ChallengeFiles(
                {"notes.txt": b"", "main.py": b"# asset fixture\n"}, {}
            ),
        },
    )

    def run(check):
        async def managed():
            try:
                await check(engine)
            finally:
                try:
                    await engine.stop()
                finally:
                    await controller.destroy(clear_workspace=True)

        try:
            asyncio.run(managed())
        finally:
            client.close()

    return run


async def run_player(engine, script):
    runtime = engine.controller.current
    assert runtime is not None
    container = await asyncio.to_thread(
        engine.controller.client.containers.get, runtime.container_id
    )
    result = await asyncio.to_thread(container.exec_run, ["python", "-c", script])
    assert result.exit_code == 0, result.output.decode()
    return result.output


async def send_ping(engine):
    await run_player(
        engine,
        """
import kss_client
from websockets.sync.client import connect

config = kss_client.load_connection()
headers = {'Authorization': 'Bearer ' + config['credential']}
with connect(config['url'], additional_headers=headers) as ws:
    ws.send(bytes.fromhex('1001c000000501000000c03e'))
    assert isinstance(ws.recv(timeout=2), bytes)
""",
    )


def test_session_roundtrip_stop_revokes_and_preserves_authored_work(engine):
    async def check(engine):
        assert engine.read() is None
        first = await engine.start(HELLO)
        assert first.status == "running" and first.pass_view is None
        old_config = json.loads(
            (engine.controller.storage.paths["managed"] / "connection.json").read_text()
        )
        assert old_config["attempt_id"] == first.session_id
        assert old_config["credential"] not in first.model_dump_json(by_alias=True)
        runtime = engine.controller.current
        assert runtime is not None
        await run_player(
            engine,
            r"""
from pathlib import Path
import json, subprocess
from websockets.sync.client import connect

config = json.loads(Path('/attempt/connection.json').read_text())
headers = {'Authorization': 'Bearer ' + config['credential']}
with connect(config['url'], additional_headers=headers) as ws:
    ws.send(bytes.fromhex('1001c000000501000000c03e'))
    reply = ws.recv(timeout=3)
    expected = ('0002c0000018' '1101000000'
                '000000000000006400000000000000010000' 'e136')
    assert isinstance(reply, bytes) and reply.hex() == expected, reply.hex()
Path('notes.txt').write_text('saved authored work')
subprocess.Popen(
    ['sleep', '300'], start_new_session=True, stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
""",
        )
        view = engine.read()
        assert view is not None
        assert view.goal_reached and view.completion == "not_yet"
        assert view.state.commands_received == 1
        assert view.state.mode == "SAFE"
        assert [item.direction for item in view.history] == ["uplink", "downlink"]
        assert view.history[0].packet_hex == "1001c000000501000000c03e"
        view.history.clear()
        assert len(engine.read().history) == 2
        saved = await engine.save_completion(first.session_id)
        assert saved.completion == "saved" and progress.read_completed() == {HELLO}
        await engine.stop()
        await engine.stop()
        assert engine.read() is None and engine.sim.read() is None
        with pytest.raises(docker.errors.NotFound):
            engine.controller.client.containers.get(runtime.container_id)
        second = await engine.start(HELLO)
        assert second.session_id != first.session_id
        assert second.history == [] and not second.goal_reached
        assert second.completion == "not_yet" and second.state.commands_received == 0
        await run_player(
            engine,
            f"""
from pathlib import Path
from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus
assert Path('notes.txt').read_text() == 'saved authored work'
try:
    headers = {{'Authorization': 'Bearer ' + {old_config["credential"]!r}}}
    connect({old_config["url"]!r}, additional_headers=headers)
except InvalidStatus as error:
    assert error.response.status_code == 403
else:
    raise AssertionError('old credential admitted')
""",
        )

    engine(check)


def test_raw_handler_preserves_bad_bytes_and_returns_platform_feedback(engine):
    async def check(engine):
        await engine.start(HELLO)
        await run_player(
            engine,
            r"""
import json, kss_client
from websockets.sync.client import connect

config = kss_client.load_connection()
headers = {'Authorization': 'Bearer ' + config['credential']}
with connect(config['url'], additional_headers=headers) as ws:
    ws.send(b'\x00')
    assert json.loads(ws.recv(timeout=2))['code'] == 'TRUNCATED_HEADER'
    ws.send('not a binary packet')
    assert json.loads(ws.recv(timeout=2))['code'] == 'INVALID_INPUT'
    ws.send(bytes.fromhex('1001c000000501000000c03e'))
    assert isinstance(ws.recv(timeout=2), bytes)
""",
        )
        view = engine.read()
        assert view.state.commands_received == 1
        assert view.goal_reached and view.completion == "not_yet"
        assert [item.packet_hex for item in view.history[:2]] == [
            "00",
            "1001c000000501000000c03e",
        ]
        assert view.history[0].feedback.code == "TRUNCATED_HEADER"

    engine(check)


def test_cancelled_transport_close_still_stops_sim(engine):
    async def check(engine):
        current = await engine.start(HELLO)
        config = json.loads(
            (engine.controller.storage.paths["managed"] / "connection.json").read_text()
        )
        incoming = asyncio.Queue()
        accepted, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def send(message):
            if message["type"] == "websocket.accept":
                accepted.set()
            if message["type"] == "websocket.close":
                closing.set()
                await release.wait()  # External ASGI transport stalls while closing.

        scope = {
            "type": "websocket",
            "root_path": "",
            "query_string": b"",
            "path": f"/raw/attempts/{current.session_id}",
            "headers": [(b"authorization", f"Bearer {config['credential']}".encode())],
        }
        incoming.put_nowait({"type": "websocket.connect"})
        client = asyncio.create_task(engine.bridge.app(scope, incoming.get, send))
        try:
            await asyncio.wait_for(accepted.wait(), 2)
            stopping = asyncio.create_task(engine.stop())
            await asyncio.wait_for(closing.wait(), 2)
            stopping.cancel()
            with pytest.raises(asyncio.CancelledError):
                await stopping
            assert engine.read().status == "failed"
            assert engine.sim.read() is None
        finally:
            release.set()
            incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})
            await asyncio.wait_for(client, 2)
        await engine.stop()
        assert engine.read() is None

    engine(check)


def test_cancelled_session_stop_can_be_retried(engine):
    async def check(engine):
        await engine.start(HELLO)
        stopping = asyncio.create_task(engine.stop())
        await asyncio.sleep(0)  # Stop reaches listener shutdown on this turn.
        assert not stopping.done()
        stopping.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stopping
        assert engine.read().status == "failed"
        await asyncio.wait_for(engine.stop(), 3)
        assert engine.read() is None
        assert (await engine.start(HELLO)).status == "running"

    engine(check)


def test_failed_stop_retains_the_latest_unpolled_evidence(engine, monkeypatch):
    from api.runtime import RuntimeFailure

    async def check(engine):
        await engine.start(HELLO)
        await send_ping(engine)

        def unavailable(*args, **kwargs):
            raise docker.errors.DockerException("Docker unavailable")

        with monkeypatch.context() as patch:
            patch.setattr(engine.controller.client.api, "remove_container", unavailable)
            with pytest.raises(RuntimeFailure):
                await engine.stop()
        view = engine.read()
        assert view.status == "failed"
        assert view.goal_reached and view.state.commands_received == 1
        assert [item.direction for item in view.history] == ["uplink", "downlink"]
        await engine.stop()
        assert engine.read() is None

    engine(check)


@pytest.mark.parametrize("storage_failure", ["sqlite", "filesystem"])
def test_completion_storage_failure_preserves_goal_without_claiming_saved(
    engine,
    monkeypatch,
    tmp_path,
    storage_failure,
):
    from api.session import SessionFailure

    async def check(engine):
        current = await engine.start(HELLO)
        with pytest.raises(SessionFailure) as error:
            await engine.save_completion(current.session_id)
        assert error.value.code == "EVIDENCE_REQUIRED"
        await send_ping(engine)
        with monkeypatch.context() as patch:
            if storage_failure == "sqlite":
                # SQLite cannot open a directory as a database. Keep the real DB.
                path = tmp_path
            else:
                parent = tmp_path / "not-a-directory"
                parent.write_text("sentinel")
                path = parent / "progress.db"
            patch.setenv("SQLITE_PATH", str(path))
            with pytest.raises(SessionFailure) as error:
                await engine.save_completion(current.session_id)
        assert error.value.code == "STORAGE_UNAVAILABLE"
        view = engine.read()
        assert view.goal_reached and view.completion == "save_failed"
        assert progress.read_completed() == set()
        await send_ping(engine)  # Explicit retry of the learner task.
        saved = await engine.save_completion(current.session_id)
        assert saved.completion == "saved"
        assert progress.read_completed() == {HELLO}

    engine(check)


def test_cancelled_completion_cannot_be_overtaken_by_stop(engine):
    async def check(engine):
        current = await engine.start(HELLO)
        await send_ping(engine)
        assert engine.read().goal_reached
        connection = progress.connect()
        connection.execute("BEGIN IMMEDIATE")
        saving = asyncio.create_task(engine.save_completion(current.session_id))
        stopping = None
        try:
            await asyncio.sleep(0)  # Let save take the lifecycle lock.
            assert engine.lock.locked()
            stopping = asyncio.create_task(engine.stop())
            saving.cancel()
            await asyncio.sleep(0)
            assert not saving.done() and not stopping.done()
            assert engine.read().status == "running"
        finally:
            connection.rollback()
            connection.close()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(saving, 3)
            if stopping is not None:
                await asyncio.wait_for(stopping, 3)
        assert engine.read() is None
        assert progress.read_completed() == {HELLO}

    engine(check)


def test_partial_session_start_and_failed_stop_keep_slot_until_cleanup(
    engine, monkeypatch
):
    from api.runtime import RuntimeFailure
    from api.session import SessionFailure

    async def check(engine):
        api = engine.controller.client.api
        create = api.create_container

        def lost_response(*args, **kwargs):
            create(*args, **kwargs)
            raise docker.errors.DockerException("lost create response")

        with monkeypatch.context() as patch:
            patch.setattr(api, "create_container", lost_response)
            with pytest.raises(RuntimeFailure):
                await engine.start(HELLO)
        assert engine.read().status == "failed"
        assert engine.sim.read() is None
        with pytest.raises(SessionFailure) as error:
            await engine.start(HELLO)
        assert error.value.code == "SESSION_ACTIVE"

        def unavailable(*args, **kwargs):
            raise docker.errors.DockerException("Docker unavailable")

        with monkeypatch.context() as patch:
            patch.setattr(api, "remove_container", unavailable)
            with pytest.raises(RuntimeFailure) as error:
                await engine.stop()
        assert error.value.code == "CLEANUP_FAILED"
        assert engine.read().status == "failed"
        await engine.stop()
        assert engine.read() is None
        fresh = await engine.start(HELLO)
        assert fresh.status == "running" and fresh.history == []

    engine(check)


def test_catch_session_prepares_context_and_refreshes_pass_and_credential(engine):
    async def check(engine):
        progress.save_completion("ready-for-the-pass")
        first = await engine.start(CATCH)
        assert first.pass_view is not None
        first_pass = first.pass_view.pass_run_id
        managed = engine.controller.storage.paths["managed"]
        brief = json.loads((managed / "pass-brief.json").read_text())
        assert brief == {
            "scenario_id": "knightsat-training-v1",
            "expected_setup": {
                "satellite_id": "KNIGHTSAT",
                "pass_start_utc": "2026-09-21T18:00:00Z",
                "receive_frequency_hz": 145825000,
                "receive_mode": "FM",
                "tracking_enabled": True,
            },
        }
        template = json.loads((managed / "log-template.json").read_text())
        assert template["pass_run_id"] == first_pass
        assert template["battery_pct"] is None and template["recording_path"] == ""
        old_config = (managed / "connection.json").read_bytes()
        await run_player(
            engine,
            r"""
from pathlib import Path
import json
from websockets.sync.client import connect

config = json.loads(Path('/attempt/connection.json').read_text())
assert config['protocol'] == 'receive'
headers = {'Authorization': 'Bearer ' + config['credential']}
with connect(config['url'], additional_headers=headers) as ws:
    ready = json.loads(ws.recv(timeout=2))
    assert ready['type'] == 'ready'
    with connect(config['url'], additional_headers=headers) as duplicate:
        assert json.loads(duplicate.recv(timeout=2))['code'] == 'RECEIVER_BUSY'
    ws.send(b'forbidden uplink')
    assert json.loads(ws.recv(timeout=2))['code'] == 'WRONG_CHALLENGE'
Path('notes.txt').write_text('Catch notes')
""",
        )
        assert engine.read().history == []
        assert not engine.read().pass_view.receiver_ready
        await engine.stop()
        second = await engine.start(CATCH)
        assert second.pass_view.pass_run_id != first_pass
        assert second.pass_view.status == "not_started"
        assert second.pass_view.received_count == 0
        assert (managed / "connection.json").read_bytes() != old_config
        await run_player(
            engine,
            "from pathlib import Path; "
            "assert Path('notes.txt').read_text() == 'Catch notes'",
        )

    engine(check)
