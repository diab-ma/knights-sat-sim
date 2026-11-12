"""Sim Service: the Python interface for Hello and idle Catch sessions.

Operations follow docs/specs/backend-and-simulation.md#operations-and-data.
The Software Link is deterministic: ordered, synchronous handoff with no
latency or drops. Every result handed out is an immutable copy.
"""

import threading
import uuid
from collections.abc import Buffer, Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Literal

from sim.clock import AsyncioScheduler, Clock, Scheduler, SystemClock, TimerHandle
from sim.goal import ping_conformance_issue
from sim.packet import (
    MAX_PACKET_BYTES,
    CommandPacket,
    SequenceCounter,
    Status,
    Unreadable,
    encode_reply,
    encode_telemetry,
    parse_command,
)
from sim.satellite import Satellite
from sim.state import Mode, SatelliteState

HELLO = "hello-satellite"
READY = "ready-for-the-pass"
CATCH = "catch-and-log"
TELEMETRY_PERIOD_S = 1.0
CATCH_INITIAL_STATE = SatelliteState(
    mode=Mode.NOMINAL,
    antenna_deployed=True,
    deploy_count=1,
    battery_pct=80,
    uptime_s=600,
)


class SimError(Exception):
    pass


class SessionActive(SimError):
    pass


class NoSession(SimError):
    pass


class UnsupportedChallenge(SimError):
    pass


class Reentry(SimError):
    """A receiver called back into the Sim while a packet was being handed off."""


class Direction(StrEnum):
    UPLINK = "uplink"
    DOWNLINK = "downlink"


class Origin(StrEnum):
    RAW_PLAYER = "raw_player"
    SATELLITE = "satellite"


class PacketKind(StrEnum):
    COMMAND = "command"
    REPLY = "reply"
    TELEMETRY = "telemetry"


@dataclass(frozen=True)
class Downlink:
    """A Satellite Sim packet handed to a receiver.

    The receiver's transport passes ``delivery_id`` to
    ``SimService.confirm_delivery`` once the packet has actually been sent.
    """

    delivery_id: str
    packet: bytes


Receiver = Callable[[Downlink], None]


@dataclass(frozen=True)
class Feedback:
    """A local Platform explanation, never a Satellite Sim reply."""

    code: str
    message: str


@dataclass(frozen=True)
class HistoryEntry:
    """One packet as it crossed the Link, with the original bytes.

    ``submission_id`` is the uplink's own ID, or for a reply the submission it
    answers; telemetry has none. ``delivered`` means sent to the Link for an
    uplink. For a downlink it means a receiver confirmed sending it to a
    script connection.
    """

    time: datetime
    direction: Direction
    origin: Origin
    kind: PacketKind
    packet: bytes
    submission_id: str | None
    delivered: bool
    feedback: Feedback | None = None


@dataclass(frozen=True)
class SubmissionReceipt:
    """Sent to the Link (or refused before it). Not command acceptance."""

    submission_id: str
    sent_to_link: bool
    refusal: Feedback | None = None
    feedback: Feedback | None = None


@dataclass(frozen=True)
class GoalNote:
    submission_id: str
    code: str
    message: str


@dataclass(frozen=True)
class GoalEvidence:
    goal_reached: bool
    submission_id: str | None
    notes: tuple[GoalNote, ...]


@dataclass(frozen=True)
class PassSnapshot:
    pass_run_id: str
    status: Literal["not_started", "running", "finished", "interrupted"]
    receiver_ready: bool
    received_count: int


@dataclass(frozen=True)
class SimSnapshot:
    session_id: str
    challenge_id: str
    state: SatelliteState
    history: tuple[HistoryEntry, ...]
    goal: GoalEvidence
    pass_view: PassSnapshot | None = None


@dataclass
class _PendingDelivery:
    history_index: int
    # The submission whose conforming PING this reply would complete.
    goal_submission_id: str | None
    # Receivers holding the packet that could still confirm it.
    receiver_ids: set[str]


class _Session:
    def __init__(self, session_id: str, challenge_id: str, now: float) -> None:
        self.session_id = session_id
        self.challenge_id = challenge_id
        self.pass_run_id = str(uuid.uuid4()) if challenge_id == CATCH else None
        self.pass_state = CATCH_INITIAL_STATE if challenge_id == CATCH else None
        self.satellite = Satellite(now)
        self.downlink_sequence = SequenceCounter()
        self.history: list[HistoryEntry] = []
        self.receivers: dict[str, Receiver] = {}
        self.pending: dict[str, _PendingDelivery] = {}
        self.next_telemetry_at = now + TELEMETRY_PERIOD_S
        self.timer: TimerHandle | None = None
        self.goal_submission_id: str | None = None
        self.goal_notes: list[GoalNote] = []


class SimService:
    """Holds at most one session. Commands are processed one at a time."""

    def __init__(
        self, clock: Clock | None = None, scheduler: Scheduler | None = None
    ) -> None:
        self._clock = clock or SystemClock()
        self._scheduler = scheduler or AsyncioScheduler()
        self._lock = threading.RLock()
        self._session: _Session | None = None
        self._handing_off = False

    def start(self, session_id: str, challenge_id: str) -> SimSnapshot:
        """Create fresh simulation state. FastAPI checks unlocks first.

        With the default scheduler, call this on the server's event-loop
        thread (from an ``async`` route), because the once-per-second
        telemetry timer is scheduled on the running loop.
        """
        with self._lock:
            self._refuse_reentry()
            if self._session is not None:
                raise SessionActive("A Sim session is already running")
            if challenge_id == READY:
                raise UnsupportedChallenge("Ready for the Pass has no simulator")
            if challenge_id not in (HELLO, CATCH):
                raise UnsupportedChallenge(f"Unknown Challenge {challenge_id!r}")
            session = _Session(session_id, challenge_id, self._clock.monotonic())
            # Schedule before taking the slot so a failure leaves none running.
            if challenge_id == HELLO:
                self._schedule_telemetry(session)
            self._session = session
            return self._snapshot(session)

    def stop(self, session_id: str) -> None:
        """End timers and receivers. Repeated or stale stop is harmless.

        Deliveries still awaiting confirmation can no longer count.
        """
        with self._lock:
            self._refuse_reentry()
            session = self._session
            if session is None or session.session_id != session_id:
                return
            if session.timer is not None:
                session.timer.cancel()
                session.timer = None
            session.receivers.clear()
            session.pending.clear()
            self._session = None

    def send_packet(self, session_id: str, packet_bytes: Buffer) -> SubmissionReceipt:
        """Record and deliver exactly these bytes through the Link.

        Returns a receipt, not proof of acceptance. Never retries, renumbers or
        repairs. Raises ``NoSession`` for bytes meant for a session that is no
        longer running, so old traffic cannot affect a new session.
        """
        data = bytes(packet_bytes)
        with self._lock:
            self._refuse_reentry()
            session = self._require(session_id)
            if session.challenge_id != HELLO:
                raise UnsupportedChallenge("Catch is receive-only")
            submission_id = str(uuid.uuid4())

            if len(data) > MAX_PACKET_BYTES:
                refusal = _feedback(Unreadable.TOO_LARGE)
                self._record_uplink(session, data, submission_id, False, refusal)
                return SubmissionReceipt(submission_id, False, refusal)

            parsed = parse_command(data)
            feedback = None
            if isinstance(parsed, Unreadable):
                feedback = _feedback(parsed)
                self._record_uplink(session, data, submission_id, True, feedback)
            else:
                self._record_uplink(session, data, submission_id, True, None)
                self._execute(session, parsed, submission_id)
            return SubmissionReceipt(submission_id, True, feedback=feedback)

    def read(self) -> SimSnapshot | None:
        """A copy of current state, history and goal evidence."""
        with self._lock:
            return None if self._session is None else self._snapshot(self._session)

    def attach_receiver(self, session_id: str, receiver: Receiver) -> str:
        """Register a downlink destination (the raw script connection).

        The Link hands each Satellite Sim packet, in order, to every attached
        receiver. Receivers run while the Sim's lock is held, on the caller's
        thread or the telemetry timer's event loop. A receiver must only
        enqueue the packet (for example with ``put_nowait``) and raise if it
        cannot. It must not call ``start``, ``stop`` or ``send_packet``;
        those raise ``Reentry`` during a handoff.

        A handoff is not delivery. After the transport has actually sent the
        packet to the script, it calls ``confirm_delivery``; Hello's goal
        needs a confirmed reply. When the connection closes or a send fails,
        call ``detach_receiver`` so its unsent packets are abandoned.
        """
        with self._lock:
            session = self._require(session_id)
            if session.challenge_id == CATCH and session.receivers:
                raise SimError("Catch permits only one receiver")
            receiver_id = str(uuid.uuid4())
            session.receivers[receiver_id] = receiver
            return receiver_id

    def detach_receiver(self, receiver_id: str) -> None:
        """Remove a script connection, for example when it disconnects.

        Packets it held but never confirmed are abandoned; once no receiver
        holds a packet, it can no longer be confirmed.
        """
        with self._lock:
            session = self._session
            if session is None:
                return
            session.receivers.pop(receiver_id, None)
            for delivery_id, pending in list(session.pending.items()):
                pending.receiver_ids.discard(receiver_id)
                if not pending.receiver_ids:
                    del session.pending[delivery_id]

    def confirm_delivery(self, session_id: str, delivery_id: str) -> bool:
        """Record that a handed-off packet actually reached a script.

        Returns whether this confirmation counted. Confirmations for a stopped
        session, an unknown delivery or one already confirmed are ignored, so
        a late send cannot affect a new session.
        """
        with self._lock:
            session = self._session
            if session is None or session.session_id != session_id:
                return False
            pending = session.pending.pop(delivery_id, None)
            if pending is None:
                return False
            index = pending.history_index
            session.history[index] = replace(session.history[index], delivered=True)
            if (
                pending.goal_submission_id is not None
                and session.goal_submission_id is None
            ):
                session.goal_submission_id = pending.goal_submission_id
            return True

    def _refuse_reentry(self) -> None:
        # The lock is re-entrant, so only a receiver on this thread can get
        # here mid-handoff; nesting would reorder packets or outlive Stop.
        if self._handing_off:
            raise Reentry("Receivers must enqueue packets, not call back into the Sim")

    def _require(self, session_id: str) -> _Session:
        session = self._session
        if session is None:
            raise NoSession("No Sim session is running")
        if session.session_id != session_id:
            raise NoSession("That Sim session is no longer running")
        return session

    def _execute(
        self, session: _Session, command: CommandPacket, submission_id: str
    ) -> None:
        status, state = session.satellite.execute(command, self._clock.monotonic())
        reply = encode_reply(
            session.downlink_sequence.next(),
            command_code=command.code,
            echoed_sequence=command.header.sequence_count,
            status=status,
            state=state,
        )
        conforming = False
        if status is Status.ACCEPTED:
            issue = ping_conformance_issue(command)
            if issue is None:
                conforming = True
            else:
                session.goal_notes.append(GoalNote(submission_id, issue, issue.message))
        self._downlink(
            session,
            reply,
            PacketKind.REPLY,
            submission_id,
            goal_submission_id=submission_id if conforming else None,
        )

    def _schedule_telemetry(self, session: _Session) -> None:
        delay = session.next_telemetry_at - self._clock.monotonic()
        session.timer = self._scheduler.call_later(
            max(0.0, delay), lambda: self._emit_telemetry(session)
        )

    def _emit_telemetry(self, session: _Session) -> None:
        with self._lock:
            if self._session is not session:
                return
            state = session.satellite.snapshot(self._clock.monotonic())
            packet = encode_telemetry(session.downlink_sequence.next(), state)
            self._downlink(session, packet, PacketKind.TELEMETRY, None)
            session.next_telemetry_at += TELEMETRY_PERIOD_S
            self._schedule_telemetry(session)

    def _downlink(
        self,
        session: _Session,
        packet: bytes,
        kind: PacketKind,
        submission_id: str | None,
        *,
        goal_submission_id: str | None = None,
    ) -> None:
        session.history.append(
            HistoryEntry(
                time=self._clock.now(),
                direction=Direction.DOWNLINK,
                origin=Origin.SATELLITE,
                kind=kind,
                packet=packet,
                submission_id=submission_id,
                delivered=False,
            )
        )
        delivery_id = str(uuid.uuid4())
        # Registered before the handoff so a receiver may confirm at once.
        pending = _PendingDelivery(
            len(session.history) - 1, goal_submission_id, set(session.receivers)
        )
        session.pending[delivery_id] = pending
        downlink = Downlink(delivery_id, packet)
        self._handing_off = True
        try:
            for receiver_id, receiver in list(session.receivers.items()):
                if receiver_id not in session.receivers:
                    continue  # Detached by an earlier receiver in this loop.
                try:
                    receiver(downlink)
                except Exception:
                    # One broken connection must not stop delivery to the
                    # others or leave the command half-recorded.
                    pending.receiver_ids.discard(receiver_id)
        finally:
            self._handing_off = False
        if not pending.receiver_ids:
            session.pending.pop(delivery_id, None)

    def _record_uplink(
        self,
        session: _Session,
        data: bytes,
        submission_id: str,
        sent_to_link: bool,
        feedback: Feedback | None,
    ) -> None:
        session.history.append(
            HistoryEntry(
                time=self._clock.now(),
                direction=Direction.UPLINK,
                origin=Origin.RAW_PLAYER,
                kind=PacketKind.COMMAND,
                packet=data,
                submission_id=submission_id,
                delivered=sent_to_link,
                feedback=feedback,
            )
        )

    def _snapshot(self, session: _Session) -> SimSnapshot:
        return SimSnapshot(
            session_id=session.session_id,
            challenge_id=session.challenge_id,
            state=(
                session.pass_state
                if session.pass_state is not None
                else session.satellite.snapshot(self._clock.monotonic())
            ),
            history=tuple(session.history),
            goal=GoalEvidence(
                goal_reached=session.goal_submission_id is not None,
                submission_id=session.goal_submission_id,
                notes=tuple(session.goal_notes),
            ),
            pass_view=(
                None
                if session.pass_run_id is None
                else PassSnapshot(
                    pass_run_id=session.pass_run_id,
                    status="not_started",
                    receiver_ready=bool(session.receivers),
                    received_count=0,
                )
            ),
        )


def _feedback(reason: Unreadable) -> Feedback:
    return Feedback(reason.value, reason.message)
