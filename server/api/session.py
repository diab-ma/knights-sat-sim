"""One shared session; HTTP adapters call this engine, never its collaborators.

Challenge implementations supply authored starters and managed resources. The
engine owns credentials and the prepared Catch context, not learner solutions.
"""

import asyncio
import json
import logging
import secrets
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import uuid4

from starlette.websockets import WebSocket, WebSocketDisconnect

from api.challenges import list_challenges
from api.progress import read_completed, save_completion
from api.runtime import RuntimeController, RuntimeFailure
from api.schemas import Feedback, HistoryEntry, PassView, Session, StateView
from api.script_bridge import ScriptBridge
from sim.service import CATCH, HELLO, Downlink, SimService, SimSnapshot
from sim.state import SatelliteState

logger = logging.getLogger(__name__)
WORKSPACE_ID = "shared-team"
SCENARIO_ID = "knightsat-training-v1"
PREPARED_SETUP = {
    "satellite_id": "KNIGHTSAT",
    "pass_start_utc": "2026-09-21T18:00:00Z",
    "receive_frequency_hz": 145825000,
    "receive_mode": "FM",
    "tracking_enabled": True,
}


@dataclass(frozen=True)
class ChallengeFiles:
    starters: Mapping[str, bytes]
    resources: Mapping[str, bytes]


class SessionFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class SessionService:
    def __init__(
        self,
        controller: RuntimeController,
        bridge: ScriptBridge,
        sim: SimService,
        files: Mapping[str, ChallengeFiles],
    ) -> None:
        self.controller = controller
        self.bridge = bridge
        self.sim = sim
        self.files = files
        self.lock = asyncio.Lock()
        self._current: Session | None = None

    def read(self) -> Session | None:
        """Return an independent, credential-free view without performing work."""
        if self._current is None:
            return None
        snapshot = self.sim.read()
        if snapshot is not None and snapshot.session_id == self._current.session_id:
            self._update(snapshot)
        return self._current.model_copy(deep=True)

    async def start(self, challenge_id: str) -> Session:
        async with self.lock:
            if self._current is not None:
                raise SessionFailure("SESSION_ACTIVE", "Stop the current session first")
            if challenge_id not in (HELLO, CATCH):
                raise SessionFailure(
                    "WRONG_CHALLENGE", "Only Hello and Catch have sessions"
                )
            try:
                completed = await asyncio.to_thread(read_completed)
            except (sqlite3.Error, OSError) as error:
                raise SessionFailure(
                    "STORAGE_UNAVAILABLE", "Could not read saved progress"
                ) from error
            challenge = next(
                item
                for item in list_challenges(completed)
                if item.challenge_id == challenge_id
            )
            if challenge.availability == "locked":
                raise SessionFailure(
                    "CHALLENGE_LOCKED", "Finish Ready for the Pass first"
                )
            assets = self.files.get(challenge_id)
            if assets is None:
                raise RuntimeFailure(
                    "RUNTIME_UNAVAILABLE", "Challenge resources are not installed"
                )
            session_id = str(uuid4())
            credential = secrets.token_urlsafe(32)
            protocol: Literal["raw", "receive"] = (
                "raw" if challenge_id == HELLO else "receive"
            )
            self._current = Session(
                session_id=session_id,
                challenge_id=challenge_id,
                status="starting",
                state=_state_view(SatelliteState()),
                history=[],
                **{"pass": None},
                goal_reached=False,
                completion="not_yet",
                checks=[],
            )
            try:
                snapshot = self.sim.start(session_id, challenge_id)
                self._update(snapshot)
                resources = dict(assets.resources)
                resources["connection.json"] = _json(
                    {
                        "attempt_id": session_id,
                        "url": f"ws://127.0.0.1:8766/{protocol}/attempts/{session_id}",
                        "credential": credential,
                        "protocol": protocol,
                    }
                )
                if snapshot.pass_view is not None:
                    resources["pass-brief.json"] = _json(
                        {
                            "scenario_id": SCENARIO_ID,
                            "expected_setup": PREPARED_SETUP,
                        }
                    )
                    resources["log-template.json"] = _json(
                        {
                            "scenario_id": SCENARIO_ID,
                            "pass_run_id": snapshot.pass_view.pass_run_id,
                            **PREPARED_SETUP,
                            "recording_path": "",
                            "battery_pct": None,
                            "mode": "",
                            "outcome_note": "",
                        }
                    )
                await self.controller.create(
                    workspace_id=WORKSPACE_ID,
                    attempt_id=session_id,
                    challenge_id=challenge_id,
                    starters=dict(assets.starters),
                    resources=resources,
                )

                async def handler(ws: WebSocket) -> None:
                    if challenge_id == HELLO:
                        await self._raw(ws, session_id)
                    else:
                        await self._receive(ws, session_id)

                self.bridge.bind(session_id, credential, protocol, handler)
                await self.bridge.start(
                    self.controller.storage.paths["bridge"] / "raw.sock"
                )
                self._current.status = "running"
            except BaseException as error:
                # Keep the cleanup obligation even after partial/cancelled create.
                # Stop is the explicit, retryable recovery boundary.
                self._current.status = "failed"
                self.read()  # Preserve the final snapshot before discarding Sim state.
                self.sim.stop(session_id)
                await self.bridge.revoke()
                if isinstance(error, (asyncio.CancelledError, RuntimeFailure)):
                    raise
                if not isinstance(error, Exception):
                    raise
                logger.exception("Could not start session")
                raise RuntimeFailure(
                    "RUNTIME_UNAVAILABLE", "Session startup failed; retry Stop"
                ) from error
            result = self.read()
            assert result is not None
            return result

    async def stop(self) -> None:
        async with self.lock:
            if self._current is None:
                return
            self._current.status = "failed"
            self.read()  # Failed cleanup must retain unpolled packet/goal evidence.
            try:
                try:
                    await self.bridge.revoke()
                finally:
                    # A stalled/failed socket close must not leave Sim timers
                    # running after Stop fails or its caller is cancelled.
                    self.sim.stop(self._current.session_id)
                    if self._current.pass_view is not None:
                        self._current.pass_view.receiver_ready = False
                await self.bridge.stop()
                await self.controller.destroy(clear_workspace=False)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                raise RuntimeFailure(
                    "CLEANUP_FAILED", "Cleanup failed; retry Stop"
                ) from error
            self._current = None

    async def save_completion(self, session_id: str) -> Session:
        """Save already-verified Sim evidence. KSAT-65 decides when to call this.

        Holding the lifecycle lock through the actual SQLite commit prevents a
        cancelled request from letting Stop overtake a still-running DB worker.
        """
        async with self.lock:
            if not self._active(session_id):
                raise SessionFailure("NO_SESSION", "That session is no longer running")
            current = self.read()
            assert current is not None
            if not current.goal_reached:
                raise SessionFailure("EVIDENCE_REQUIRED", "Complete the task first")
            assert self._current is not None
            worker = asyncio.create_task(
                asyncio.to_thread(save_completion, current.challenge_id)
            )
            cancelled = False
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    cancelled = True
                except (sqlite3.Error, OSError):
                    break
            try:
                worker.result()
            except (sqlite3.Error, OSError) as error:
                self._current.completion = "save_failed"
                logger.exception("Could not save session completion")
                if cancelled:
                    raise asyncio.CancelledError from error
                raise SessionFailure(
                    "STORAGE_UNAVAILABLE", "Progress was not saved; repeat the task"
                ) from error
            self._current.completion = "saved"
            if cancelled:
                raise asyncio.CancelledError
            result = self.read()
            assert result is not None
            return result

    def _active(self, session_id: str) -> bool:
        return (
            self._current is not None
            and self._current.session_id == session_id
            and self._current.status == "running"
        )

    def _update(self, snapshot: SimSnapshot) -> None:
        assert self._current is not None
        self._current.state = _state_view(snapshot.state)
        self._current.goal_reached = snapshot.goal.goal_reached
        self._current.pass_view = (
            None
            if snapshot.pass_view is None
            else PassView(**asdict(snapshot.pass_view))
        )
        self._current.history = [
            HistoryEntry.model_validate(
                {
                    "time": entry.time,
                    "direction": entry.direction,
                    "origin": entry.origin,
                    "packet_hex": entry.packet.hex(),
                    "pass_index": None,
                    "feedback": None
                    if entry.feedback is None
                    else asdict(entry.feedback),
                }
            )
            for entry in snapshot.history
        ]

    async def _raw(self, ws: WebSocket, session_id: str) -> None:
        if not self._active(session_id):
            await ws.close(code=1008)
            return
        await ws.accept()
        outgoing: asyncio.Queue[Downlink | Feedback] = asyncio.Queue()
        receiver_id = self.sim.attach_receiver(session_id, outgoing.put_nowait)

        async def receive() -> None:
            while self._active(session_id):
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if not self._active(session_id):
                    return
                data = message.get("bytes")
                if data is None:
                    outgoing.put_nowait(
                        Feedback(
                            code="INVALID_INPUT",
                            message="Send one binary packet per message",
                        )
                    )
                    continue
                receipt = self.sim.send_packet(session_id, data)
                feedback = receipt.refusal or receipt.feedback
                if feedback is not None:
                    outgoing.put_nowait(Feedback(**asdict(feedback)))

        async def send() -> None:
            while True:
                item = await outgoing.get()
                if not self._active(session_id):
                    return
                if isinstance(item, Downlink):
                    await ws.send_bytes(item.packet)
                    if self._active(session_id):
                        self.sim.confirm_delivery(session_id, item.delivery_id)
                else:
                    await ws.send_json({"type": "feedback", **item.model_dump()})

        tasks = [asyncio.create_task(receive()), asyncio.create_task(send())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except WebSocketDisconnect:
            pass
        finally:
            self.sim.detach_receiver(receiver_id)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _receive(self, ws: WebSocket, session_id: str) -> None:
        """Register Catch's idle receiver; KSAT-20 adds finite pass delivery."""
        if not self._active(session_id):
            await ws.close(code=1008)
            return
        snapshot = self.sim.read()
        assert snapshot is not None and snapshot.pass_view is not None
        if snapshot.pass_view.receiver_ready:
            await ws.accept()
            await ws.send_json(
                {
                    "type": "error",
                    "code": "RECEIVER_BUSY",
                    "message": "A receiver is already connected",
                }
            )
            await ws.close(code=1008)
            return
        receiver_id = self.sim.attach_receiver(session_id, lambda packet: None)
        try:
            await ws.accept()
            await ws.send_json(
                {"type": "ready", "pass_run_id": snapshot.pass_view.pass_run_id}
            )
            message = await ws.receive()
            if message["type"] != "websocket.disconnect":
                await ws.send_json(
                    {
                        "type": "error",
                        "code": "WRONG_CHALLENGE",
                        "message": "Catch is receive-only",
                    }
                )
                await ws.close(code=1008)
        finally:
            self.sim.detach_receiver(receiver_id)


def _state_view(state: SatelliteState) -> StateView:
    return StateView.model_validate({**asdict(state), "mode": state.mode.name})


def _json(value: object) -> bytes:
    return json.dumps(value).encode()
