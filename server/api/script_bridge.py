"""Script-only listener in the server event loop; KSAT-12 supplies Sim handlers."""

import asyncio
import os
import secrets
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import uvicorn
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.types import Message
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

ScriptHandler = Callable[[WebSocket], Awaitable[None]]


@dataclass(frozen=True)
class ScriptAccess:
    attempt_id: str
    credential: str = field(repr=False)
    protocol: Literal["raw", "receive"]
    handler: ScriptHandler = field(repr=False)


class ScriptBridge:
    def __init__(self) -> None:
        self.access: ScriptAccess | None = None
        self.connections: set[WebSocket] = set()
        self.app = Starlette(
            routes=[
                WebSocketRoute("/{protocol}/attempts/{attempt_id}", self._connect),
            ]
        )
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None
        self._socket: socket.socket | None = None

    def bind(
        self,
        attempt_id: str,
        credential: str,
        protocol: Literal["raw", "receive"],
        handler: ScriptHandler,
    ) -> None:
        if self.access is not None or self.connections:
            raise RuntimeError(
                "Revoke old script access before binding another Attempt"
            )
        if not credential or protocol not in ("raw", "receive"):
            raise ValueError("A script protocol and nonempty credential are required")
        self.access = ScriptAccess(attempt_id, credential, protocol, handler)

    async def _connect(self, request: WebSocket) -> None:
        access = self.access
        headers = request.headers.getlist("authorization")
        if (
            access is None
            or request.path_params
            != {"protocol": access.protocol, "attempt_id": access.attempt_id}
            or len(headers) != 1
            or not secrets.compare_digest(
                headers[0].encode(), f"Bearer {access.credential}".encode()
            )
        ):
            await request.close(code=1008)
            return

        async def receive() -> Message:
            message = await request.receive()
            if self.access is not access:
                raise WebSocketDisconnect(1008)
            return message

        async def send(message: Message) -> None:
            if self.access is not access:
                raise WebSocketDisconnect(1008)
            await request.send(message)

        guarded = WebSocket(request.scope, receive, send)
        self.connections.add(request)
        try:
            await access.handler(guarded)
        except WebSocketDisconnect:
            pass
        finally:
            self.connections.discard(request)

    async def revoke(self) -> None:
        self.access = (
            None  # Revoke synchronously before closing sockets or Docker work.
        )
        for connection in tuple(self.connections):
            if connection.application_state != WebSocketState.DISCONNECTED:
                await connection.close(code=1008)

    async def start(self, path: Path) -> None:
        if self._task is not None:
            raise RuntimeError("Script listener already started")
        sock = socket.socket(socket.AF_UNIX)
        self._socket = sock
        try:
            sock.bind(str(path))  # Never unlink an unknown, potentially live listener.
            os.chown(path, 1000, 1000)
            os.chmod(path, 0o600)
            config = uvicorn.Config(
                self.app,
                lifespan="off",
                access_log=False,
                ws_max_size=256,
                ws_max_queue=16,
                timeout_graceful_shutdown=1,
                log_level="warning",
            )
            self._server = uvicorn.Server(config)
            self._task = asyncio.create_task(self._server.serve(sockets=[sock]))
            async with asyncio.timeout(5):
                while not self._server.started:
                    if self._task.done():
                        await self._task
                        raise RuntimeError("Script listener did not start")
                    await asyncio.sleep(0.01)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        await self.revoke()
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            await asyncio.wait_for(self._task, timeout=3)
            self._task = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None
