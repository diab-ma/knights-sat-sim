"""Real Docker acceptance; run with compose.runtime-test.yml."""

import asyncio
import os

import docker
import pytest

from api.runtime import RuntimeController, RuntimeStorage


@pytest.fixture
def controller():
    if "RUNTIME_DEPLOYMENT" not in os.environ:
        pytest.skip("Run real Docker checks with compose.runtime-test.yml")
    client = docker.from_env()
    storage = RuntimeStorage.from_environment()
    controller = RuntimeController(client, storage, image="knightsat-player:ksat11")
    yield controller
    asyncio.run(controller.destroy(clear_workspace=True))
    client.close()


def test_create_isolated_runtime_and_remove_detached_children(controller):
    async def check():
        runtime = await controller.create(
            workspace_id="workspace-one",
            attempt_id="attempt-one",
            challenge_id="hello",
            starters={"notes.txt": b""},
            resources={},
        )
        container = controller.client.containers.get(runtime.container_id)
        config = container.attrs["HostConfig"]
        assert container.attrs["Config"]["User"] == "1000:1000"
        assert config["NetworkMode"] == "none"
        assert config["ReadonlyRootfs"]
        assert config["CapDrop"] == ["ALL"]
        assert "no-new-privileges" in config["SecurityOpt"]
        assert config["NanoCpus"] == 500_000_000
        assert config["Memory"] == config["MemorySwap"] == 128 * 1024**2
        assert config["PidsLimit"] == 64
        assert config["Ulimits"] == [{"Name": "nofile", "Soft": 256, "Hard": 256}]
        mounts = {m["Destination"]: m for m in container.attrs["Mounts"]}
        assert set(mounts) == {"/workspace", "/attempt", "/bridge"}
        assert mounts["/workspace"]["RW"]
        assert not mounts["/attempt"]["RW"] and not mounts["/bridge"]["RW"]
        result = await asyncio.to_thread(
            container.exec_run, ["python", "-c", "import os; print(os.getuid())"]
        )
        assert result.exit_code == 0 and result.output.strip() == b"1000"
        result = await asyncio.to_thread(
            container.exec_run,
            [
                "python",
                "-c",
                "import subprocess; subprocess.Popen(['sleep','300'], "
                "start_new_session=True, "
                "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
                "stderr=subprocess.DEVNULL)",
            ],
        )
        assert result.exit_code == 0
        assert len(container.top()["Processes"]) >= 2
        await controller.destroy(clear_workspace=True)
        assert controller.current is None
        with pytest.raises(docker.errors.NotFound):
            controller.client.containers.get(runtime.container_id)
        assert all(
            not list(path.iterdir()) for path in controller.storage.paths.values()
        )

    asyncio.run(check())


def test_replacement_retains_authored_files_and_refreshes_readonly_resources(
    controller,
):
    async def check():
        first = await controller.create(
            workspace_id="workspace-one",
            attempt_id="attempt-one",
            challenge_id="hello",
            starters={
                "notes.txt": b"starter",
                "ping_example.py": b"# supplied by KSAT-17\n",
            },
            resources={"connection.json": b'{"attempt_id":"attempt-one"}'},
        )
        container = controller.client.containers.get(first.container_id)
        command = (
            "from pathlib import Path; p=Path('/workspace/hello/notes.txt'); "
            "assert p.read_text()=='starter'; p.write_text('my saved work')"
        )
        assert container.exec_run(["python", "-c", command]).exit_code == 0
        await controller.destroy()
        second = await controller.create(
            workspace_id="workspace-one",
            attempt_id="attempt-two",
            challenge_id="hello",
            starters={"notes.txt": b"must not overwrite"},
            resources={"connection.json": b'{"attempt_id":"attempt-two"}'},
        )
        assert second.runtime_id != first.runtime_id
        container = controller.client.containers.get(second.container_id)
        result = container.exec_run(
            [
                "python",
                "-c",
                "from pathlib import Path; import json; "
                "p=Path('/workspace/hello/notes.txt'); "
                "assert p.read_text()=='my saved work'; "
                "config=json.loads(Path('/attempt/connection.json').read_text()); "
                "assert config['attempt_id']=='attempt-two'; "
                "Path('/attempt/connection.json').write_text('overwrite')",
            ]
        )
        assert result.exit_code != 0 and b"Read-only file system" in result.output
        await controller.destroy(clear_workspace=True)
        assert all(
            not list(path.iterdir()) for path in controller.storage.paths.values()
        )

    asyncio.run(check())


def test_partial_creation_and_failed_cleanup_keep_slot_unavailable(
    controller, monkeypatch
):
    from api.runtime import RuntimeFailure

    async def check():
        create = controller.client.api.create_container

        def lose_create_response(*args, **kwargs):
            create(*args, **kwargs)
            raise docker.errors.DockerException("injected lost create response")

        with monkeypatch.context() as patch:
            patch.setattr(
                controller.client.api, "create_container", lose_create_response
            )
            with pytest.raises(RuntimeFailure, match="cleanup") as error:
                await controller.create(
                    workspace_id="w",
                    attempt_id="a",
                    challenge_id="hello",
                    starters={},
                    resources={},
                )
        assert error.value.code == "RUNTIME_UNAVAILABLE"
        runtime = controller.current
        assert runtime is not None and controller.failed
        assert controller.client.containers.get(runtime.container_id)
        with pytest.raises(RuntimeFailure):
            await controller.create(
                workspace_id="w",
                attempt_id="b",
                challenge_id="hello",
                starters={},
                resources={},
            )
        with monkeypatch.context() as patch:

            def cannot_remove(*args, **kwargs):
                raise docker.errors.DockerException("injected removal failure")

            patch.setattr(controller.client.api, "remove_container", cannot_remove)
            with pytest.raises(RuntimeFailure) as error:
                await controller.destroy(clear_workspace=True)
        assert error.value.code == "CLEANUP_FAILED"
        assert controller.current == runtime and controller.failed
        await controller.destroy(clear_workspace=True)
        await controller.destroy(clear_workspace=True)
        assert controller.current is None and not controller.failed

    asyncio.run(check())


def test_cancelled_creation_cannot_race_cleanup_or_block_event_loop(
    controller, monkeypatch
):
    import threading

    from api.runtime import RuntimeFailure

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    create = controller.client.api.create_container

    def delayed_create(*args, **kwargs):
        entered.set()
        try:
            assert release.wait(5), "test must release Docker worker"
            return create(*args, **kwargs)
        finally:
            finished.set()

    async def check():
        with monkeypatch.context() as patch:
            patch.setattr(controller.client.api, "create_container", delayed_create)
            task = asyncio.create_task(
                controller.create(
                    workspace_id="w",
                    attempt_id="a",
                    challenge_id="hello",
                    starters={},
                    resources={},
                )
            )
            assert await asyncio.to_thread(entered.wait, 2)
            runtime = controller.current
            try:
                # The event loop stays responsive during the stalled Docker call.
                await asyncio.wait_for(asyncio.sleep(0.01), 0.2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                with pytest.raises(RuntimeFailure, match="in progress"):
                    await controller.destroy(clear_workspace=True)
                assert controller.current == runtime and controller.failed
            finally:
                release.set()
                await asyncio.to_thread(finished.wait, 5)
                # Retry the public boundary until the entire worker has finished.
                async with asyncio.timeout(5):
                    while True:
                        try:
                            await controller.destroy(clear_workspace=True)
                            break
                        except RuntimeFailure:
                            await asyncio.sleep(0.01)
        await controller.destroy(clear_workspace=True)
        with pytest.raises(docker.errors.NotFound):
            controller.client.containers.get(runtime.container_id)

    asyncio.run(check())


def test_retained_workspace_cannot_be_reassigned_until_cleared(controller):
    from api.runtime import RuntimeFailure

    async def check():
        await controller.create(
            workspace_id="first",
            attempt_id="a",
            challenge_id="hello",
            starters={"notes.txt": b"private"},
            resources={},
        )
        await controller.destroy()
        with pytest.raises(RuntimeFailure):
            await controller.create(
                workspace_id="second",
                attempt_id="b",
                challenge_id="hello",
                starters={},
                resources={},
            )
        await controller.destroy(clear_workspace=True)
        runtime = await controller.create(
            workspace_id="second",
            attempt_id="b",
            challenge_id="hello",
            starters={"notes.txt": b"fresh"},
            resources={},
        )
        result = controller.client.containers.get(runtime.container_id).exec_run(
            ["cat", "/workspace/hello/notes.txt"]
        )
        assert result.output == b"fresh"

    asyncio.run(check())


def test_script_bridge_authenticates_direct_socket_and_loopback_and_hides_api(
    controller,
):
    from api.script_bridge import ScriptBridge

    async def echo_fixture(websocket):
        await websocket.accept()
        await websocket.send_bytes(await websocket.receive_bytes())
        await websocket.close()

    async def check():
        bridge = ScriptBridge()
        bridge.bind("attempt-one", "fixture-secret", "raw", echo_fixture)
        await bridge.start(controller.storage.paths["bridge"] / "raw.sock")
        try:
            runtime = await controller.create(
                workspace_id="w",
                attempt_id="attempt-one",
                challenge_id="hello",
                starters={},
                resources={},
            )
            probe = r"""
import base64, os, socket


def request(path, credential=None, unix=False, upgrade=True):
    s = socket.socket(socket.AF_UNIX if unix else socket.AF_INET)
    s.settimeout(2)
    s.connect("/bridge/raw.sock" if unix else ("127.0.0.1", 8766))
    headers = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n"
    if upgrade:
        headers += (
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: "
            + base64.b64encode(os.urandom(16)).decode()
            + "\r\n"
        )
    if credential:
        headers += "Authorization: Bearer " + credential + "\r\n"
    s.sendall((headers + "\r\n").encode())
    reply = b""
    while b"\r\n\r\n" not in reply:
        reply += s.recv(4096)
    status = int(reply.split()[1])
    if status == 101:
        # One masked binary frame with deliberately unusual bytes.
        payload = b"\x00\xff\x80abc"
        mask = b"abcd"
        s.sendall(
            bytes([0x82, 0x80 | len(payload)])
            + mask
            + bytes(v ^ mask[i % 4] for i, v in enumerate(payload))
        )
        frame = b""
        while len(frame) < len(payload) + 2:
            frame += s.recv(64)
        assert frame.startswith(bytes([0x82, len(payload)]) + payload), frame
    s.close()
    return status


for unix in (False, True):
    assert request("/raw/attempts/attempt-one", "fixture-secret", unix) == 101
    for credential in (None, "wrong"):
        assert request("/raw/attempts/attempt-one", credential, unix) == 403
    for path in (
        "/raw/attempts/old",
        "/receive/attempts/attempt-one",
        "/api/session",
        "/health",
        "/docs",
        "/api/progress/reset",
        "/files",
        "/control",
    ):
        assert request(path, "fixture-secret", unix) != 101, path
        assert request(path, "fixture-secret", unix, False) == 404, path
print("allowed raw bytes preserved; other routes and credentials denied")
"""
            container = controller.client.containers.get(runtime.container_id)
            result = await asyncio.to_thread(
                container.exec_run, ["python", "-c", probe]
            )
            assert result.exit_code == 0, result.output.decode()
            await bridge.revoke()
            result = await asyncio.to_thread(
                container.exec_run,
                [
                    "python",
                    "-c",
                    probe.split("for unix in")[0]
                    + "assert request('/raw/attempts/attempt-one',"
                    "'fixture-secret',True)==403",
                ],
            )
            assert result.exit_code == 0, result.output.decode()
        finally:
            await bridge.stop()

    asyncio.run(check())


def test_runtime_limits_are_configurable_and_storage_is_actually_bounded(controller):
    from api.runtime import RuntimeLimits

    controller.limits = RuntimeLimits(
        cpu=0.25, memory_mib=64, processes=32, descriptors=96, temp_mib=2, home_mib=1
    )

    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={},
        )
        container = controller.client.containers.get(runtime.container_id)
        config = container.attrs["HostConfig"]
        assert config["NanoCpus"] == 250_000_000
        assert config["Memory"] == config["MemorySwap"] == 64 * 1024**2
        assert config["PidsLimit"] == 32
        probe = """
import os, resource

assert resource.getrlimit(resource.RLIMIT_NOFILE) == (96, 96)
for path, size in [
    ("/workspace", 64),
    ("/attempt", 1),
    ("/bridge", 1),
    ("/tmp", 2),
    ("/home/player", 1),
]:
    stat = os.statvfs(path)
    assert stat.f_blocks * stat.f_frsize == size * 1024**2, (path, stat)
print("configured limits verified")
"""
        result = container.exec_run(["python", "-c", probe])
        assert result.exit_code == 0, result.output.decode()

    asyncio.run(check())


def test_wrong_storage_quota_is_refused_before_player_execution(controller):
    from api.runtime import RuntimeFailure, RuntimeLimits

    controller.limits = RuntimeLimits(authored_mib=32)

    async def check():
        try:
            with pytest.raises(RuntimeFailure):
                await controller.create(
                    workspace_id="w",
                    attempt_id="a",
                    challenge_id="hello",
                    starters={},
                    resources={},
                )
            assert not controller.client.containers.list(
                all=True, filters={"label": "org.knightsat.deployment=ksat11-test"}
            )
        finally:
            controller.limits = RuntimeLimits()

    asyncio.run(check())


def test_real_resource_exhaustion_and_forbidden_access_are_bounded(controller):
    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={},
        )
        container = controller.client.containers.get(runtime.container_id)
        probe = r"""
import errno, json, os, socket, subprocess, time
from pathlib import Path

for family, address in [
    (socket.AF_INET, ("1.1.1.1", 443)),
    (socket.AF_INET, ("192.168.65.1", 8000)),
    (socket.AF_INET6, ("2606:4700:4700::1111", 443)),
]:
    with socket.socket(family) as sock:
        sock.settimeout(0.3)
        assert sock.connect_ex(address) != 0, address
for path in [
    "/var/run/docker.sock",
    "/app/api/main.py",
    "/data/progress.sqlite",
    "/app/.env",
]:
    assert not Path(path).exists(), path
try:
    Path("/root-write").write_text("forbidden")
except OSError as e:
    assert e.errno in (errno.EROFS, errno.EACCES)
else:
    raise AssertionError("writable root")
for path, limit in [
    ("/workspace/full", 64),
    ("/tmp/full", 16),
    ("/home/player/full", 4),
]:
    written = 0
    try:
        with open(path, "wb", buffering=0) as file:
            for _ in range(limit + 1):
                written += file.write(b"x" * 1024**2)
    except OSError as e:
        assert e.errno == errno.ENOSPC, e
    else:
        raise AssertionError("unbounded storage")
    finally:
        Path(path).unlink(missing_ok=True)
    assert written <= limit * 1024**2
    print(path, "ENOSPC after", written, flush=True)
fds = []
try:
    for _ in range(257):
        fds.append(os.open("/dev/null", os.O_RDONLY))
except OSError as e:
    assert e.errno == errno.EMFILE, e
else:
    raise AssertionError("unbounded descriptors")
finally:
    for fd in fds:
        os.close(fd)
children = []
try:
    for _ in range(65):
        children.append(subprocess.Popen(["sleep", "10"]))
except OSError as e:
    assert e.errno == errno.EAGAIN, e
else:
    raise AssertionError("unbounded processes")
finally:
    for child in children:
        child.kill()
    for child in children:
        child.wait()
print(
    "processes capped after",
    len(children),
    "children; descriptors after",
    len(fds),
    flush=True,
)
start = time.monotonic()
while time.monotonic() - start < 1:
    pass
stats = dict(
    line.split() for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines()
)
assert int(stats["nr_throttled"]) > 0, stats
print("CPU throttled periods", stats["nr_throttled"], flush=True)
"""
        result = await asyncio.to_thread(container.exec_run, ["python", "-c", probe])
        assert result.exit_code == 0, result.output.decode()
        print(result.output.decode())
        for kind in ("managed", "bridge"):
            path = controller.storage.paths[kind] / "quota-probe"
            try:
                with pytest.raises(OSError) as error:
                    path.write_bytes(b"x" * (2 * 1024**2))
                assert error.value.errno == 28
            finally:
                path.unlink(missing_ok=True)
        result = await asyncio.to_thread(
            container.exec_run,
            ["python", "-c", "data=[]\nwhile True: data.append(bytearray(8*1024**2))"],
        )
        assert result.exit_code == 137, result.output
        print("memory exhaustion killed the allocating process (137)")
        await controller.destroy(clear_workspace=True)

    asyncio.run(check())


def test_runtime_has_one_live_bash_pty_starting_in_challenge_folder(controller):
    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={},
        )
        assert controller.terminal is not None
        await asyncio.get_running_loop().sock_sendall(
            controller.terminal, b"printf 'shell-%s\\n' \"$PWD\"\n"
        )
        output = b""
        async with asyncio.timeout(3):
            while b"shell-/workspace/hello" not in output:
                output += await asyncio.get_running_loop().sock_recv(
                    controller.terminal, 4096
                )
        container = controller.client.containers.get(runtime.container_id)
        processes = container.top()["Processes"]
        assert sum("/bin/bash --noprofile --norc" in row[-1] for row in processes) == 1
        await controller.destroy()
        assert controller.terminal is None

    asyncio.run(check())


def test_prepared_image_has_tools_and_loads_current_managed_connection(controller):
    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={
                "connection.json": b'{"attempt_id":"a","url":"ws://127.0.0.1:8766/raw/attempts/a","credential":"fixture","protocol":"raw"}'
            },
        )
        container = controller.client.containers.get(runtime.container_id)
        result = container.exec_run(
            [
                "python",
                "-c",
                "import shutil, kss_client; "
                "assert kss_client.load_connection()['attempt_id']=='a'; "
                "assert all(shutil.which(name) for name in "
                "'bash python ls cat cp mv rm mkdir head tail xxd od "
                "sha256sum socat'.split())",
            ]
        )
        assert result.exit_code == 0, result.output.decode()

    asyncio.run(check())


def test_bridge_revokes_open_connections_and_rejects_queued_and_oversize_frames(
    controller,
):
    from starlette.websockets import WebSocketDisconnect

    from api.script_bridge import ScriptBridge

    async def check():
        bridge = ScriptBridge()
        entered, release = asyncio.Event(), asyncio.Event()
        delivered = []

        async def delayed_receiver(ws):
            await ws.accept()
            entered.set()
            await release.wait()
            try:
                delivered.append(await ws.receive_bytes())
            except WebSocketDisconnect:
                pass

        bridge.bind("a", "old-credential", "raw", delayed_receiver)
        await bridge.start(controller.storage.paths["bridge"] / "raw.sock")
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={},
        )
        container = controller.client.containers.get(runtime.container_id)
        probe = """
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed

with connect(
    "ws://127.0.0.1:8766/raw/attempts/a",
    additional_headers={"Authorization": "Bearer old-credential"},
) as ws:
    ws.send(b"queued")
    from pathlib import Path

    Path("/workspace/sent").touch()
    try:
        ws.recv(timeout=2)
    except ConnectionClosed:
        print("closed")
    else:
        raise AssertionError("revocation did not close socket")
"""
        task = asyncio.create_task(
            asyncio.to_thread(container.exec_run, ["python", "-c", probe])
        )
        try:
            await asyncio.wait_for(entered.wait(), 3)
            async with asyncio.timeout(3):
                while not (controller.storage.paths["authored"] / "sent").exists():
                    await asyncio.sleep(0.01)
            await bridge.revoke()
            release.set()
            result = await asyncio.wait_for(task, 3)
            assert result.exit_code == 0, result.output.decode()
            assert delivered == []

            async def receive_fixture(ws):
                await ws.accept()
                await ws.send_json({"type": "ready", "pass_run_id": "fixture"})
                await ws.close()

            bridge.bind("b", "fresh-credential", "receive", receive_fixture)
            probe = """
from websockets.sync.client import unix_connect

with unix_connect(
    "/bridge/raw.sock",
    uri="ws://localhost/receive/attempts/b",
    additional_headers={"Authorization": "Bearer fresh-credential"},
) as ws:
    assert "fixture" in ws.recv(timeout=2)
"""
            result = await asyncio.to_thread(
                container.exec_run, ["python", "-c", probe]
            )
            assert result.exit_code == 0, result.output.decode()
            await bridge.revoke()

            async def raw_fixture(ws):
                await ws.accept()
                try:
                    delivered.append(await ws.receive_bytes())
                except WebSocketDisconnect:
                    pass

            bridge.bind("c", "fresh-credential", "raw", raw_fixture)
            probe = """
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed

with connect(
    "ws://127.0.0.1:8766/raw/attempts/c",
    additional_headers={"Authorization": "Bearer fresh-credential"},
) as ws:
    ws.send(b"x" * 257)
    try:
        ws.recv(timeout=2)
    except ConnectionClosed as error:
        assert error.rcvd.code == 1009, error
    else:
        raise AssertionError("oversize frame accepted")
"""
            result = await asyncio.to_thread(
                container.exec_run, ["python", "-c", probe]
            )
            assert result.exit_code == 0, result.output.decode()
            assert delivered == []
        finally:
            release.set()
            await bridge.stop()

    asyncio.run(check())


def test_abandoned_execution_blocks_creation_and_storage_cleanup(controller):
    from api.runtime import DEPLOYMENT_LABEL, RuntimeFailure

    orphan = controller.client.containers.create(
        controller.image, labels={DEPLOYMENT_LABEL: controller.storage.deployment}
    )

    async def check():
        with pytest.raises(RuntimeFailure):
            await controller.create(
                workspace_id="w",
                attempt_id="a",
                challenge_id="hello",
                starters={},
                resources={},
            )
        with pytest.raises(RuntimeFailure):
            await controller.destroy(clear_workspace=True)
        assert controller.failed and controller.client.containers.get(orphan.id)

    try:
        asyncio.run(check())
    finally:
        orphan.remove(force=True)


def test_quota_failure_does_not_leave_a_partial_starter(controller):
    from api.runtime import RuntimeFailure

    async def check():
        await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={"notes.txt": b"saved"},
            resources={},
        )
        await controller.destroy()
        root = controller.storage.paths["authored"]
        filler = root / "filler"
        with filler.open("wb") as file:
            for _ in range(63):
                file.write(b"x" * 1024**2)
            file.write(b"x" * (512 * 1024))
        with pytest.raises(RuntimeFailure):
            await controller.create(
                workspace_id="w",
                attempt_id="b",
                challenge_id="hello",
                starters={"main.py": b"x" * 1024**2},
                resources={},
            )
        assert not (root / "hello/main.py").exists()
        assert (root / "hello/notes.txt").read_bytes() == b"saved"
        filler.unlink()
        await controller.destroy()
        await controller.create(
            workspace_id="w",
            attempt_id="b",
            challenge_id="hello",
            starters={"main.py": b"complete"},
            resources={},
        )
        assert (root / "hello/main.py").read_bytes() == b"complete"

    asyncio.run(check())


def test_provisioning_and_cleanup_never_follow_player_symlinks(controller, tmp_path):
    from api.runtime import RuntimeFailure

    outside = tmp_path / "private.txt"
    outside.write_text("private sentinel")

    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={},
        )
        container = controller.client.containers.get(runtime.container_id)
        result = container.exec_run(
            [
                "python",
                "-c",
                "import os; os.symlink('/attempt/connection.json',"
                "'/workspace/hello/notes.txt'); "
                "os.symlink('/tmp','/workspace/catch')",
            ]
        )
        assert result.exit_code == 0
        await controller.destroy()
        await controller.create(
            workspace_id="w",
            attempt_id="b",
            challenge_id="hello",
            starters={"notes.txt": b"must not follow"},
            resources={},
        )
        assert not (controller.storage.paths["managed"] / "connection.json").exists()
        await controller.destroy()
        with pytest.raises(RuntimeFailure):
            await controller.create(
                workspace_id="w",
                attempt_id="c",
                challenge_id="catch",
                starters={"main.py": b"starter"},
                resources={},
            )
        (controller.storage.paths["authored"] / "outside").symlink_to(outside)
        await controller.destroy(clear_workspace=True)
        assert outside.read_text() == "private sentinel"

    asyncio.run(check())


def test_cleanup_leaves_foreign_deployment_resources_untouched(controller):
    from api.runtime import DEPLOYMENT_LABEL

    labels = {DEPLOYMENT_LABEL: "ksat11-foreign-fixture"}
    foreign = controller.client.containers.create(controller.image, labels=labels)
    volume = controller.client.volumes.create(labels=labels)

    async def check():
        await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={},
            resources={},
        )
        await controller.destroy(clear_workspace=True)
        assert controller.client.containers.get(foreign.id)
        assert controller.client.volumes.get(volume.id)

    try:
        asyncio.run(check())
    finally:
        foreign.remove(force=True)
        volume.remove()


def test_storage_deletion_failure_keeps_slot_unavailable_until_retry(
    controller, monkeypatch
):
    from api.runtime import RuntimeFailure

    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={"notes.txt": b"personal work"},
            resources={},
        )
        unlink = os.unlink

        def denied(path, *args, **kwargs):
            if str(path) == "notes.txt":
                raise PermissionError("injected storage deletion failure")
            return unlink(path, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(os, "unlink", denied)
            with pytest.raises(RuntimeFailure) as error:
                await controller.destroy(clear_workspace=True)
        assert error.value.code == "CLEANUP_FAILED"
        assert controller.current == runtime and controller.failed
        assert (
            controller.storage.paths["authored"] / "hello/notes.txt"
        ).read_bytes() == b"personal work"
        with pytest.raises(RuntimeFailure):
            await controller.create(
                workspace_id="other",
                attempt_id="b",
                challenge_id="hello",
                starters={},
                resources={},
            )
        await controller.destroy(clear_workspace=True)
        assert not list(controller.storage.paths["authored"].iterdir())
        assert controller.current is None and not controller.failed

    asyncio.run(check())


def test_cancelled_destruction_keeps_slot_until_verified_retry(controller, monkeypatch):
    import threading

    from api.runtime import RuntimeFailure

    entered, release = threading.Event(), threading.Event()
    remove = controller.client.api.remove_container

    def delayed_remove(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return remove(*args, **kwargs)

    async def check():
        runtime = await controller.create(
            workspace_id="w",
            attempt_id="a",
            challenge_id="hello",
            starters={"notes.txt": b"personal work"},
            resources={},
        )
        with monkeypatch.context() as patch:
            patch.setattr(controller.client.api, "remove_container", delayed_remove)
            task = asyncio.create_task(controller.destroy(clear_workspace=True))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert controller.current == runtime and controller.failed
                with pytest.raises(RuntimeFailure):
                    await controller.create(
                        workspace_id="other",
                        attempt_id="b",
                        challenge_id="hello",
                        starters={},
                        resources={},
                    )
            finally:
                release.set()
                async with asyncio.timeout(5):
                    while True:
                        try:
                            await controller.destroy(clear_workspace=True)
                            break
                        except RuntimeFailure:
                            await asyncio.sleep(0.01)
        assert controller.current is None and not controller.failed
        assert not list(controller.storage.paths["authored"].iterdir())
        with pytest.raises(docker.errors.NotFound):
            controller.client.containers.get(runtime.container_id)

    asyncio.run(check())
