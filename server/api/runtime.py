"""Trusted runtime boundary. Call under the application's shared lifecycle lock."""

import asyncio
import math
import os
import re
import shutil
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import docker
from docker.errors import NotFound
from docker.types import LogConfig, Ulimit

DEPLOYMENT_LABEL = "org.knightsat.deployment"
RUNTIME_LABEL = "org.knightsat.runtime"
WORKSPACE_LABEL = "org.knightsat.workspace"


@dataclass(frozen=True)
class RuntimeLimits:
    cpu: float = 0.5
    memory_mib: int = 128
    processes: int = 64
    descriptors: int = 256
    authored_mib: int = 64
    managed_mib: int = 1
    bridge_mib: int = 1
    temp_mib: int = 16
    home_mib: int = 4

    def __post_init__(self) -> None:
        if any(not math.isfinite(v) or v <= 0 for v in vars(self).values()):
            raise ValueError("Runtime limits must be finite and positive")


@dataclass(frozen=True)
class RuntimeStorage:
    deployment: str
    volumes: dict[str, str]
    paths: dict[str, Path]

    @classmethod
    def from_environment(cls):
        return cls(
            os.environ["RUNTIME_DEPLOYMENT"],
            {
                kind: os.environ[f"RUNTIME_{kind.upper()}_VOLUME"]
                for kind in ("authored", "managed", "bridge")
            },
            {
                kind: Path(f"/runtime/{kind}")
                for kind in ("authored", "managed", "bridge")
            },
        )


@dataclass(frozen=True)
class Runtime:
    runtime_id: str
    container_id: str
    workspace_id: str
    attempt_id: str


class RuntimeFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class RuntimeController:
    def __init__(
        self,
        client: docker.DockerClient,
        storage: RuntimeStorage,
        *,
        image: str,
        limits: RuntimeLimits = RuntimeLimits(),
    ):
        self.client = client
        self.storage = storage
        self.image = image
        self.limits = limits
        self.current: Runtime | None = None
        self.failed = False
        self.workspace_id: str | None = None
        self.terminal: socket.socket | None = None
        self.terminal_exec_id: str | None = None
        self._operation: asyncio.Task[None] | None = None

    async def _worker(self, operation: Callable[..., None], *args: Any) -> None:
        if self._operation is not None:
            if not self._operation.done():
                raise RuntimeFailure(
                    "CLEANUP_FAILED", "Docker operation in progress; retry cleanup"
                )
            self._operation.exception()  # Consume an error after caller cancellation.
        self._operation = asyncio.create_task(asyncio.to_thread(operation, *args))
        await asyncio.shield(self._operation)

    async def create(
        self,
        *,
        workspace_id: str,
        attempt_id: str,
        challenge_id: str,
        starters: dict[str, bytes],
        resources: dict[str, bytes],
    ) -> Runtime:
        if self.current is not None or self.failed:
            raise RuntimeFailure(
                "RUNTIME_UNAVAILABLE", "Runtime unavailable; retry cleanup first"
            )
        if self.workspace_id not in (None, workspace_id):
            raise RuntimeFailure(
                "RUNTIME_UNAVAILABLE", "Clear the previous workspace first"
            )
        for value in (workspace_id, attempt_id, challenge_id):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
                raise ValueError("Invalid runtime context")
        self.workspace_id = workspace_id
        runtime_id = uuid4().hex
        # Record the deterministic name before Docker can create anything.
        self.current = Runtime(
            runtime_id, f"ksat-{runtime_id}", workspace_id, attempt_id
        )
        try:
            await self._worker(self._create, challenge_id, starters, resources)
        except asyncio.CancelledError:
            self.failed = True
            raise
        except Exception as error:
            self.failed = True
            raise RuntimeFailure(
                "RUNTIME_UNAVAILABLE", "Preparation failed; retry cleanup"
            ) from error
        return self.current

    def _create(
        self, challenge_id: str, starters: dict[str, bytes], resources: dict[str, bytes]
    ) -> None:
        assert self.current is not None
        self._validate_storage()
        if self.client.containers.list(
            all=True, filters={"label": f"{DEPLOYMENT_LABEL}={self.storage.deployment}"}
        ):
            raise RuntimeError("Abandoned runtime present; reconcile before admission")
        root = os.open(self.storage.paths["authored"], os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                os.mkdir(challenge_id, dir_fd=root)
            except FileExistsError:
                pass
            folder = os.open(challenge_id, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            try:
                os.fchown(folder, 1000, 1000)
                self._seed(folder, starters)
            finally:
                os.close(folder)
        finally:
            os.close(root)
        managed = os.open(self.storage.paths["managed"], os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self._seed(managed, resources)
        finally:
            os.close(managed)
        container = self.client.containers.create(
            self.image,
            name=self.current.container_id,
            labels={
                DEPLOYMENT_LABEL: self.storage.deployment,
                RUNTIME_LABEL: self.current.runtime_id,
                WORKSPACE_LABEL: self.current.workspace_id,
            },
            user="1000:1000",
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            nano_cpus=int(self.limits.cpu * 1_000_000_000),
            mem_limit=f"{self.limits.memory_mib}m",
            memswap_limit=f"{self.limits.memory_mib}m",
            pids_limit=self.limits.processes,
            ulimits=[
                Ulimit(
                    name="nofile",
                    soft=self.limits.descriptors,
                    hard=self.limits.descriptors,
                )
            ],
            tmpfs={
                "/tmp": (
                    f"rw,nosuid,nodev,noexec,size={self.limits.temp_mib}m,"
                    "uid=1000,gid=1000"
                ),
                "/home/player": (
                    f"rw,nosuid,nodev,size={self.limits.home_mib}m,uid=1000,gid=1000"
                ),
            },
            volumes={
                self.storage.volumes[kind]: {"bind": target, "mode": mode}
                for kind, target, mode in (
                    ("authored", "/workspace", "rw"),
                    ("managed", "/attempt", "ro"),
                    ("bridge", "/bridge", "ro"),
                )
            },
            working_dir=f"/workspace/{challenge_id}",
            log_config=LogConfig(type="none"),
            init=True,
        )
        container.start()
        container.reload()
        if container.status != "running":
            raise RuntimeError("Player failed to start; destroy and retry explicitly")
        execution = self.client.api.exec_create(
            container.id,
            ["/bin/bash", "--noprofile", "--norc"],
            stdin=True,
            tty=True,
            workdir=f"/workspace/{challenge_id}",
            environment={"PS1": "player$ ", "TERM": "xterm-256color"},
        )
        self.terminal_exec_id = execution["Id"]
        stream = self.client.api.exec_start(execution["Id"], tty=True, socket=True)
        try:
            self.terminal = socket.socket(fileno=os.dup(stream.fileno()))
            self.terminal.setblocking(False)
        finally:
            stream.close()

    async def destroy(self, *, clear_workspace: bool = False) -> None:
        try:
            await self._worker(self._destroy, clear_workspace)
        except asyncio.CancelledError:
            self.failed = True
            raise
        except RuntimeFailure:
            self.failed = True
            raise
        except Exception as error:
            self.failed = True
            raise RuntimeFailure(
                "CLEANUP_FAILED", "Runtime unavailable; retry cleanup"
            ) from error
        self.current = None
        self.failed = False
        if clear_workspace:
            self.workspace_id = None

    def _destroy(self, clear_workspace: bool) -> None:
        if self.current is not None:
            try:
                container = self.client.containers.get(self.current.container_id)
            except NotFound:
                pass
            else:
                labels = container.labels
                if (
                    labels.get(DEPLOYMENT_LABEL) != self.storage.deployment
                    or labels.get(RUNTIME_LABEL) != self.current.runtime_id
                ):
                    raise RuntimeError("Foreign runtime; refusing removal")
                container.remove(force=True)
                try:
                    self.client.containers.get(self.current.container_id)
                except NotFound:
                    pass
                else:
                    raise RuntimeError("Runtime still present; retry cleanup")
        if self.terminal is not None:
            self.terminal.close()
            self.terminal = None
            self.terminal_exec_id = None
        if self.client.containers.list(
            all=True, filters={"label": f"{DEPLOYMENT_LABEL}={self.storage.deployment}"}
        ):
            raise RuntimeError(
                "Abandoned runtime present; reconcile before storage cleanup"
            )
        self._validate_storage()
        for kind in (
            ("authored", "managed", "bridge")
            if clear_workspace
            else ("managed", "bridge")
        ):
            for path in self.storage.paths[kind].iterdir():
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()

    @staticmethod
    def _seed(directory: int, files: dict[str, bytes]) -> None:
        for name, content in files.items():
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}", name):
                raise ValueError("Provisioning requires a plain filename")
            if len(content) > 1024**2:
                raise ValueError("Provisioned file exceeds 1 MiB")
            try:
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory,
                )
            except FileExistsError:
                continue  # Authored files and links are never followed or replaced.
            try:
                with os.fdopen(fd, "wb") as file:
                    os.fchown(file.fileno(), 1000, 1000)
                    file.write(content)
            except BaseException:
                os.unlink(name, dir_fd=directory)
                raise

    def _validate_storage(self) -> None:
        devices = set()
        for kind in ("authored", "managed", "bridge"):
            volume = self.client.volumes.get(self.storage.volumes[kind])
            options = volume.attrs.get("Options") or {}
            if (
                volume.attrs.get("Labels", {}).get(DEPLOYMENT_LABEL)
                != self.storage.deployment
                or volume.attrs["Driver"] != "local"
                or options.get("type") != "tmpfs"
                or options.get("device") != "tmpfs"
            ):
                raise RuntimeError(
                    f"Untrusted {kind} storage; check deployment volume labels"
                )
            path = self.storage.paths[kind]
            fd = os.open(path, os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                device = os.fstat(fd).st_dev
                size = os.fstatvfs(fd)
                if device in devices or not os.path.ismount(path):
                    raise RuntimeError(
                        "Runtime storage must use distinct mounted volumes"
                    )
                devices.add(device)
                if (
                    size.f_blocks * size.f_frsize
                    != getattr(self.limits, f"{kind}_mib") * 1024**2
                ):
                    raise RuntimeError(
                        f"Wrong {kind} quota; recreate the empty test volume"
                    )
            finally:
                os.close(fd)
