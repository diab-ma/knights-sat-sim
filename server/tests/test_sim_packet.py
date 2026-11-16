"""Packet v1 bytes, CRC and minimum safe parsing (docs/specs/packet-format-v1.md)."""

import ast
import sys
from pathlib import Path

import pytest

from sim.crc import crc16_ccitt_false
from sim.packet import (
    MAX_PACKET_BYTES,
    MIN_COMMAND_BYTES,
    CommandCode,
    CommandPacket,
    DownlinkKind,
    SequenceCounter,
    Status,
    Unreadable,
    decode_downlink,
    encode_command,
    encode_packet,
    encode_reply,
    encode_telemetry,
    parse_command,
)
from sim.state import COUNTER_MAX, Mode, SatelliteState, saturating_increment

WORKED_PING = bytes.fromhex("1001c0000005" "01000000" "c03e")
WORKED_REPLY = bytes.fromhex(
    "0002c0000018"
    "1101000000"
    "000000000000006400000000000000010000"
    "e136"
)


def test_crc_check_value() -> None:
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_worked_ping_bytes_and_crc() -> None:
    assert encode_command(CommandCode.PING, 0) == WORKED_PING
    assert len(WORKED_PING) == MIN_COMMAND_BYTES == 12
    assert crc16_ccitt_false(WORKED_PING[:-2]) == 0xC03E


def test_command_header_starts_10_01_without_secondary_header() -> None:
    assert encode_command(CommandCode.PING, 0)[:2] == b"\x10\x01"


def test_worked_reply_bytes_and_crc() -> None:
    state = SatelliteState(commands_received=1, last_seq_seen=0)
    reply = encode_reply(
        0,
        command_code=CommandCode.PING,
        echoed_sequence=0,
        status=Status.ACCEPTED,
        state=state,
    )
    assert reply == WORKED_REPLY
    assert len(reply) == 31
    assert crc16_ccitt_false(WORKED_REPLY[:-2]) == 0xE136


def test_decode_worked_reply() -> None:
    decoded = decode_downlink(WORKED_REPLY)
    assert decoded.kind is DownlinkKind.REPLY
    assert decoded.crc_ok
    assert decoded.header.apid == 0x002 and decoded.header.packet_type == 0
    assert decoded.header.data_length == 0x18
    assert decoded.command_code == CommandCode.PING
    assert decoded.echoed_sequence == 0
    assert decoded.status is Status.ACCEPTED
    assert decoded.state == SatelliteState(commands_received=1, last_seq_seen=0)


def test_parse_worked_ping() -> None:
    parsed = parse_command(WORKED_PING)
    assert isinstance(parsed, CommandPacket)
    assert parsed.code == CommandCode.PING
    assert parsed.role == 0
    assert parsed.arguments == b"" and parsed.authorization == b""
    assert parsed.header.sequence_count == 0
    assert parsed.header_constants_ok and parsed.length_ok and parsed.crc_ok
    assert parsed.raw == WORKED_PING


def test_telemetry_layout_before_any_command() -> None:
    packet = encode_telemetry(5, SatelliteState(uptime_s=3))
    assert len(packet) == 6 + 1 + 18 + 2
    decoded = decode_downlink(packet)
    assert decoded.kind is DownlinkKind.TELEMETRY
    assert decoded.header.sequence_count == 5
    assert packet[6 + 1 + 16 : 6 + 1 + 18] == b"\xff\xff"  # last_seq_seen
    assert decoded.state.last_seq_seen is None


def test_state_field_offsets() -> None:
    state = SatelliteState(
        mode=Mode.NOMINAL,
        antenna_deployed=True,
        deploy_count=0x01020304,
        heater_on=True,
        battery_pct=99,
        uptime_s=0x0A0B0C0D,
        commands_received=7,
        last_seq_seen=0x1234,
    )
    assert state.encode() == bytes.fromhex(
        "01" "01" "01020304" "01" "63" "0a0b0c0d" "00000007" "1234"
    )
    assert SatelliteState.decode(state.encode()) == state


def test_counters_saturate() -> None:
    assert saturating_increment(COUNTER_MAX) == COUNTER_MAX
    state = SatelliteState(deploy_count=COUNTER_MAX, commands_received=COUNTER_MAX)
    assert state.encode()[2:6] == b"\xff\xff\xff\xff"


def test_sequence_counter_wraps() -> None:
    counter = SequenceCounter()
    values = [counter.next() for _ in range(16385)]
    assert values[0] == 0 and values[16383] == 16383 and values[16384] == 0


@pytest.mark.parametrize("length", range(MIN_COMMAND_BYTES))
def test_every_truncation_of_ping_is_unreadable(length: int) -> None:
    result = parse_command(WORKED_PING[:length])
    assert isinstance(result, Unreadable)
    expected = Unreadable.TRUNCATED_HEADER if length < 6 else Unreadable.TRUNCATED_BODY
    assert result is expected


def test_truncated_arguments_and_authorization_are_unreadable() -> None:
    # Argument count promises 4 bytes; only 1 present before the CRC slot.
    args_cut = bytes.fromhex("1001c0000006" "03000401" "0000")
    # Authorization count promises 3 bytes; none present.
    auth_cut = bytes.fromhex("1001c0000005" "01000003" "0000")
    assert parse_command(args_cut) is Unreadable.TRUNCATED_BODY
    assert parse_command(auth_cut) is Unreadable.TRUNCATED_BODY


def test_trailing_body_bytes_are_ambiguous() -> None:
    padded = WORKED_PING[:-2] + b"\x00" + WORKED_PING[-2:]
    assert parse_command(padded) is Unreadable.AMBIGUOUS_BODY


def test_declared_length_is_not_trusted() -> None:
    # Header claims a huge body; the real boundary is still used.
    lying = bytearray(WORKED_PING)
    lying[4:6] = b"\xff\xff"
    parsed = parse_command(bytes(lying))
    assert isinstance(parsed, CommandPacket)
    assert not parsed.length_ok and not parsed.crc_ok


def test_oversized_is_unreadable_and_cannot_be_encoded() -> None:
    assert parse_command(b"\x00" * (MAX_PACKET_BYTES + 1)) is Unreadable.TOO_LARGE
    with pytest.raises(ValueError):
        encode_packet(packet_type=1, apid=1, sequence_count=0, body=b"\x00" * 249)
    largest = encode_packet(
        packet_type=1, apid=1, sequence_count=0, body=b"\x00" * 248
    )
    assert len(largest) == MAX_PACKET_BYTES


@pytest.mark.parametrize("module", ["crc", "packet", "state"])
def test_packet_library_uses_only_the_standard_library(module: str) -> None:
    # The Player image reuses these files without the server (KSAT-17).
    source = Path(__file__).parents[1] / "sim" / f"{module}.py"
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    allowed = {"sim.crc", "sim.state"}
    assert {
        name
        for name in imported
        if name not in allowed and name.split(".")[0] not in sys.stdlib_module_names
    } == set()
