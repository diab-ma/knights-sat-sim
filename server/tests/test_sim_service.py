"""SimService behaviour for Hello, using ManualTime instead of real sleeps."""

import asyncio
import dataclasses

import pytest

from sim.clock import ManualTime, TimerHandle
from sim.crc import crc16_ccitt_false
from sim.goal import GoalIssue
from sim.packet import (
    CommandCode,
    DownlinkKind,
    Status,
    decode_downlink,
    encode_command,
    encode_header,
    encode_packet,
)
from sim.service import (
    CATCH,
    HELLO,
    READY,
    Direction,
    NoSession,
    PacketKind,
    SessionActive,
    SimService,
    SimSnapshot,
    UnsupportedChallenge,
)
from sim.state import Mode, SatelliteState

WORKED_PING = bytes.fromhex("1001c0000005" "01000000" "c03e")
WORKED_REPLY = bytes.fromhex(
    "0002c0000018"
    "1101000000"
    "000000000000006400000000000000010000"
    "e136"
)
SESSION = "session-1"


@pytest.fixture
def time() -> ManualTime:
    return ManualTime()


@pytest.fixture
def sim(time: ManualTime) -> SimService:
    service = SimService(clock=time, scheduler=time)
    service.start(SESSION, HELLO)
    return service


@pytest.fixture
def received(sim: SimService) -> list[bytes]:
    packets: list[bytes] = []
    sim.attach_receiver(SESSION, packets.append)
    return packets


def snapshot(sim: SimService) -> SimSnapshot:
    result = sim.read()
    assert result is not None
    return result


def replies_to(sim: SimService, submission_id: str) -> list[bytes]:
    return [
        entry.packet
        for entry in snapshot(sim).history
        if entry.direction is Direction.DOWNLINK
        and entry.submission_id == submission_id
    ]


def with_crc(unsigned: bytes) -> bytes:
    return unsigned + crc16_ccitt_false(unsigned).to_bytes(2, "big")


def with_bad_crc(packet: bytes) -> bytes:
    return packet[:-2] + bytes([packet[-2] ^ 0xFF, packet[-1]])


# Worked exchange


def test_worked_exchange_reply_matches_spec(
    sim: SimService, received: list[bytes]
) -> None:
    receipt = sim.send_packet(SESSION, WORKED_PING)
    assert received == [WORKED_REPLY]
    assert replies_to(sim, receipt.submission_id) == [WORKED_REPLY]
    view = snapshot(sim)
    assert view.goal.goal_reached
    assert view.goal.submission_id == receipt.submission_id
    assert view.state == SatelliteState(commands_received=1, last_seq_seen=0)


def test_hello_starting_state(sim: SimService) -> None:
    assert snapshot(sim).state == SatelliteState(
        mode=Mode.SAFE,
        antenna_deployed=False,
        deploy_count=0,
        heater_on=False,
        battery_pct=100,
        uptime_s=0,
        commands_received=0,
        last_seq_seen=None,
    )
    assert snapshot(sim).history == ()


# Truncated and oversized packets never execute


@pytest.mark.parametrize("length", range(12))
def test_truncated_ping_never_executes(
    sim: SimService, received: list[bytes], length: int
) -> None:
    receipt = sim.send_packet(SESSION, WORKED_PING[:length])
    view = snapshot(sim)
    assert receipt.sent_to_link
    assert received == []
    assert replies_to(sim, receipt.submission_id) == []
    assert view.state.commands_received == 0
    assert view.state.last_seq_seen is None
    assert not view.goal.goal_reached
    [uplink] = view.history
    assert uplink.packet == WORKED_PING[:length]
    assert uplink.feedback is not None
    assert uplink.feedback.code in {"TRUNCATED_HEADER", "TRUNCATED_BODY"}


def test_truncation_does_not_consume_a_downlink_sequence(
    sim: SimService, received: list[bytes]
) -> None:
    sim.send_packet(SESSION, WORKED_PING[:9])
    sim.send_packet(SESSION, WORKED_PING)
    assert received == [WORKED_REPLY]  # downlink sequence still zero


def test_oversized_packet_is_refused_before_the_link(
    sim: SimService, received: list[bytes]
) -> None:
    # An otherwise interpretable SET_HEATER(on), padded with authorization
    # data to 257 bytes, hand-built because the encoder refuses to exceed 256.
    authorization = b"\xaa" * 244
    body = bytes([CommandCode.SET_HEATER, 0, 1, 1, len(authorization)]) + authorization
    header = encode_header(
        packet_type=1, apid=1, sequence_count=0, data_length=len(body) + 1
    )
    oversized = with_crc(header + body)
    assert len(oversized) == 257

    receipt = sim.send_packet(SESSION, oversized)

    assert not receipt.sent_to_link
    assert receipt.refusal is not None
    assert receipt.refusal.code == "PACKET_TOO_LARGE"
    view = snapshot(sim)
    assert not view.state.heater_on
    assert view.state.commands_received == 0
    assert received == []
    [uplink] = view.history
    assert uplink.packet == oversized
    assert not uplink.delivered


# Wrong-CRC PING executes but does not solve Hello


def test_wrong_crc_ping_executes_without_solving(
    sim: SimService, received: list[bytes]
) -> None:
    receipt = sim.send_packet(SESSION, with_bad_crc(WORKED_PING))

    [reply] = received
    decoded = decode_downlink(reply)
    assert decoded.status is Status.ACCEPTED
    assert decoded.echoed_sequence == 0
    view = snapshot(sim)
    assert view.state.commands_received == 1
    assert not view.goal.goal_reached
    [note] = view.goal.notes
    assert note.submission_id == receipt.submission_id
    assert note.code == GoalIssue.BAD_CHECKSUM
    assert note.message == (
        "PING accepted, but the Challenge asks for a correctly formed packet. "
        "Check the checksum."
    )


def test_correct_ping_after_wrong_crc_still_solves(
    sim: SimService, received: list[bytes]
) -> None:
    sim.send_packet(SESSION, with_bad_crc(WORKED_PING))
    good = sim.send_packet(SESSION, encode_command(CommandCode.PING, 1))
    goal = snapshot(sim).goal
    assert goal.goal_reached
    assert goal.submission_id == good.submission_id


def test_wrong_crc_actuator_command_executes_with_defense_off(
    sim: SimService, received: list[bytes]
) -> None:
    heater_on = encode_command(CommandCode.SET_HEATER, 3, arguments=b"\x01")
    sim.send_packet(SESSION, with_bad_crc(heater_on))
    assert snapshot(sim).state.heater_on


@pytest.mark.parametrize(
    ("packet", "issue"),
    [
        (encode_command(CommandCode.GET_TELEMETRY, 0), GoalIssue.NOT_PING),
        (
            encode_packet(
                packet_type=0, apid=2, sequence_count=0, body=b"\x01\x00\x00\x00"
            ),
            GoalIssue.BAD_HEADER,
        ),
        (
            with_crc(WORKED_PING[:4] + b"\x00\x09" + WORKED_PING[6:-2]),
            GoalIssue.LENGTH_MISMATCH,
        ),
        (encode_command(CommandCode.PING, 0, role=2), GoalIssue.UNKNOWN_ROLE),
        (
            encode_command(CommandCode.PING, 0, authorization=b"\x01"),
            GoalIssue.HAS_AUTHORIZATION_DATA,
        ),
    ],
)
def test_executed_but_nonconforming_commands_do_not_solve(
    sim: SimService, received: list[bytes], packet: bytes, issue: GoalIssue
) -> None:
    sim.send_packet(SESSION, packet)
    view = snapshot(sim)
    assert decode_downlink(received[0]).status is Status.ACCEPTED
    assert view.state.commands_received == 1
    assert not view.goal.goal_reached
    assert [note.code for note in view.goal.notes] == [issue]


def test_reply_must_be_delivered_to_solve(time: ManualTime) -> None:
    sim = SimService(clock=time, scheduler=time)
    sim.start(SESSION, HELLO)
    sim.send_packet(SESSION, WORKED_PING)  # no receiver attached
    view = snapshot(sim)
    assert view.state.commands_received == 1
    assert not view.goal.goal_reached
    [_, reply] = view.history
    assert reply.kind is PacketKind.REPLY and not reply.delivered


def test_telemetry_alone_does_not_solve(
    sim: SimService, time: ManualTime, received: list[bytes]
) -> None:
    time.advance(5)
    assert len(received) == 5
    assert not snapshot(sim).goal.goal_reached


# Receipts, replies and parser feedback stay separate


def test_receipts_replies_and_feedback_are_distinct(
    sim: SimService, time: ManualTime, received: list[bytes]
) -> None:
    unreadable = sim.send_packet(SESSION, WORKED_PING[:7])
    accepted = sim.send_packet(SESSION, WORKED_PING)
    time.advance(1)

    # A receipt reports Link submission only; it carries no reply or verdict.
    assert {f.name for f in dataclasses.fields(unreadable)} == {
        "submission_id",
        "sent_to_link",
        "refusal",
    }
    assert unreadable.sent_to_link and unreadable.refusal is None
    assert accepted.submission_id != unreadable.submission_id

    history = snapshot(sim).history
    uplinks = [e for e in history if e.direction is Direction.UPLINK]
    replies = [e for e in history if e.kind is PacketKind.REPLY]
    telemetry = [e for e in history if e.kind is PacketKind.TELEMETRY]

    # Parser feedback sits on the unreadable uplink; it is not a reply.
    assert [u.feedback is not None for u in uplinks] == [True, False]
    assert all(r.feedback is None for r in replies + telemetry)
    # The one reply answers the accepted submission; telemetry answers nothing.
    assert [r.submission_id for r in replies] == [accepted.submission_id]
    assert [t.submission_id for t in telemetry] == [None]
    assert [decode_downlink(p).kind for p in received] == [
        DownlinkKind.REPLY,
        DownlinkKind.TELEMETRY,
    ]


def test_identical_pings_are_separate_submissions(
    sim: SimService, received: list[bytes]
) -> None:
    first = sim.send_packet(SESSION, WORKED_PING)
    second = sim.send_packet(SESSION, WORKED_PING)
    assert first.submission_id != second.submission_id
    [first_reply] = replies_to(sim, first.submission_id)
    [second_reply] = replies_to(sim, second.submission_id)
    assert decode_downlink(first_reply).echoed_sequence == 0
    assert decode_downlink(second_reply).echoed_sequence == 0
    assert decode_downlink(first_reply).header.sequence_count == 0
    assert decode_downlink(second_reply).header.sequence_count == 1


def test_submitted_bytes_are_kept_exactly(sim: SimService) -> None:
    buffer = bytearray(WORKED_PING)
    sim.send_packet(SESSION, buffer)
    buffer[0] = 0xFF
    assert snapshot(sim).history[0].packet == WORKED_PING


# Telemetry, timers and Stop


def test_one_telemetry_packet_per_second(
    sim: SimService, time: ManualTime, received: list[bytes]
) -> None:
    time.advance(0.999)
    assert received == []
    time.advance(2.001)
    decoded = [decode_downlink(p) for p in received]
    assert [d.kind for d in decoded] == [DownlinkKind.TELEMETRY] * 3
    assert [d.header.sequence_count for d in decoded] == [0, 1, 2]
    assert [d.state.uptime_s for d in decoded] == [1, 2, 3]


def test_replies_and_telemetry_share_one_downlink_count(
    sim: SimService, time: ManualTime, received: list[bytes]
) -> None:
    time.advance(1)
    sim.send_packet(SESSION, WORKED_PING)
    time.advance(1)
    assert [decode_downlink(p).header.sequence_count for p in received] == [0, 1, 2]


def test_stop_ends_all_timers(
    sim: SimService, time: ManualTime, received: list[bytes]
) -> None:
    time.advance(2)
    assert time.pending_timers == 1
    sim.stop(SESSION)
    assert time.pending_timers == 0
    time.advance(10)
    assert len(received) == 2
    assert sim.read() is None


def test_repeated_and_stale_stop_are_harmless(sim: SimService) -> None:
    sim.stop("some-other-session")
    assert sim.read() is not None
    sim.stop(SESSION)
    sim.stop(SESSION)
    assert sim.read() is None


def test_new_session_starts_fresh(
    sim: SimService, time: ManualTime, received: list[bytes]
) -> None:
    sim.send_packet(SESSION, WORKED_PING)
    time.advance(3)
    sim.stop(SESSION)
    sim.start("session-2", HELLO)
    fresh: list[bytes] = []
    sim.attach_receiver("session-2", fresh.append)
    # Bytes queued by the old session's connection cannot reach the new one.
    with pytest.raises(NoSession):
        sim.send_packet(SESSION, WORKED_PING)
    assert snapshot(sim).history == ()
    sim.send_packet("session-2", WORKED_PING)
    assert fresh == [WORKED_REPLY]
    # The old receiver kept only its reply and three telemetry packets.
    assert received[0] == WORKED_REPLY and len(received) == 4
    view = snapshot(sim)
    assert view.session_id == "session-2"
    assert len(view.history) == 2
    assert view.state.commands_received == 1


# Commands


def send(sim: SimService, code: int, sequence: int, arguments: bytes = b"") -> Status:
    packet = encode_command(code, sequence, arguments=arguments)
    receipt = sim.send_packet(SESSION, packet)
    [reply] = replies_to(sim, receipt.submission_id)
    status = decode_downlink(reply).status
    assert status is not None
    return status


def test_actuator_commands(sim: SimService, received: list[bytes]) -> None:
    assert send(sim, CommandCode.SET_MODE, 1, b"\x01") is Status.ACCEPTED
    assert send(sim, CommandCode.SET_HEATER, 2, b"\x01") is Status.ACCEPTED
    assert send(sim, CommandCode.DEPLOY_ANTENNA, 3) is Status.ACCEPTED
    assert send(sim, CommandCode.DEPLOY_ANTENNA, 3) is Status.ACCEPTED  # replay
    state = snapshot(sim).state
    assert state.mode is Mode.NOMINAL and state.heater_on
    assert state.antenna_deployed and state.deploy_count == 2
    assert state.commands_received == 4 and state.last_seq_seen == 3
    assert decode_downlink(received[-1]).state == state


def test_ping_and_get_telemetry_change_no_actuators(sim: SimService) -> None:
    assert send(sim, CommandCode.PING, 1) is Status.ACCEPTED
    assert send(sim, CommandCode.GET_TELEMETRY, 2) is Status.ACCEPTED
    assert snapshot(sim).state == SatelliteState(commands_received=2, last_seq_seen=2)


def test_reboot(sim: SimService, time: ManualTime, received: list[bytes]) -> None:
    send(sim, CommandCode.SET_MODE, 1, b"\x01")
    send(sim, CommandCode.SET_HEATER, 2, b"\x01")
    send(sim, CommandCode.DEPLOY_ANTENNA, 3)
    time.advance(5.5)
    assert send(sim, CommandCode.REBOOT, 4) is Status.ACCEPTED
    reply_state = decode_downlink(received[-1]).state
    assert reply_state == SatelliteState(
        mode=Mode.SAFE,
        antenna_deployed=True,
        deploy_count=1,
        heater_on=False,
        battery_pct=100,
        uptime_s=0,
        commands_received=4,
        last_seq_seen=4,
    )
    time.advance(1)
    assert snapshot(sim).state.uptime_s == 1


@pytest.mark.parametrize(
    ("code", "arguments", "status"),
    [
        (0x07, b"", Status.UNKNOWN_COMMAND),
        (0x00, b"", Status.UNKNOWN_COMMAND),
        (CommandCode.SET_MODE, b"\x02", Status.INVALID_ARGUMENTS),
        (CommandCode.SET_HEATER, b"", Status.INVALID_ARGUMENTS),
        (CommandCode.SET_HEATER, b"\x01\x01", Status.INVALID_ARGUMENTS),
        (CommandCode.PING, b"\x00", Status.INVALID_ARGUMENTS),
        (CommandCode.GET_TELEMETRY, b"\x00", Status.INVALID_ARGUMENTS),
    ],
)
def test_rejected_commands_reply_without_changing_state(
    sim: SimService, code: int, arguments: bytes, status: Status
) -> None:
    before = snapshot(sim).state
    assert send(sim, code, 9, arguments) is status
    view = snapshot(sim)
    assert view.state == before
    assert not view.goal.goal_reached and view.goal.notes == ()


# Interface boundaries


def test_read_returns_copies(sim: SimService, received: list[bytes]) -> None:
    before = snapshot(sim)
    sim.send_packet(SESSION, WORKED_PING)
    assert before.history == ()
    assert before.state.commands_received == 0
    assert not before.goal.goal_reached
    with pytest.raises(dataclasses.FrozenInstanceError):
        before.state.heater_on = True  # type: ignore[misc]
    assert isinstance(snapshot(sim).history, tuple)


def test_start_refusals(time: ManualTime) -> None:
    sim = SimService(clock=time, scheduler=time)
    for challenge in (READY, CATCH, "unknown"):
        with pytest.raises(UnsupportedChallenge):
            sim.start(SESSION, challenge)
    assert sim.read() is None and time.pending_timers == 0
    sim.start(SESSION, HELLO)
    with pytest.raises(SessionActive):
        sim.start("session-2", HELLO)


def test_send_requires_the_running_session(time: ManualTime) -> None:
    sim = SimService(clock=time, scheduler=time)
    with pytest.raises(NoSession):
        sim.send_packet(SESSION, WORKED_PING)
    sim.start(SESSION, HELLO)
    with pytest.raises(NoSession):
        sim.send_packet("old-session", WORKED_PING)
    assert snapshot(sim).history == ()
    sim.send_packet(SESSION, WORKED_PING)
    assert len(snapshot(sim).history) == 2


def test_failing_receiver_does_not_block_others(sim: SimService) -> None:
    def broken(packet: bytes) -> None:
        raise ConnectionError

    good: list[bytes] = []
    sim.attach_receiver(SESSION, broken)
    sim.attach_receiver(SESSION, good.append)
    sim.send_packet(SESSION, WORKED_PING)
    assert good == [WORKED_REPLY]
    assert snapshot(sim).goal.goal_reached


def test_detached_receiver_gets_nothing(sim: SimService, time: ManualTime) -> None:
    packets: list[bytes] = []
    receiver_id = sim.attach_receiver(SESSION, packets.append)
    sim.detach_receiver(receiver_id)
    time.advance(2)
    assert packets == []


def test_failed_start_leaves_no_session(time: ManualTime) -> None:
    class NoLoop:
        def call_later(self, delay: float, callback: object) -> TimerHandle:
            raise RuntimeError("no running event loop")

    sim = SimService(clock=time, scheduler=NoLoop())
    with pytest.raises(RuntimeError):
        sim.start(SESSION, HELLO)
    assert sim.read() is None
    sim = SimService(clock=time, scheduler=time)
    sim.start(SESSION, HELLO)


def test_default_asyncio_timers_start_and_stop() -> None:
    async def scenario() -> None:
        sim = SimService()
        sim.start(SESSION, HELLO)
        loop = asyncio.get_running_loop()
        assert any(not h.cancelled() for h in loop._scheduled)  # type: ignore[attr-defined]
        sim.stop(SESSION)
        assert all(h.cancelled() for h in loop._scheduled)  # type: ignore[attr-defined]
        assert sim.read() is None

    asyncio.run(scenario())
