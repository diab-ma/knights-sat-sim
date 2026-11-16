"""Packet v1 encoder and decoder (docs/specs/packet-format-v1.md).

The command parser applies only minimum safe parsing. Header constants,
declared length and CRC are reported as flags, not enforced: the optional
format-validation Defense is off in the MVP.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum, StrEnum

from sim.crc import crc16_ccitt_false
from sim.state import STATE_BYTES, SatelliteState

MAX_PACKET_BYTES = 256
MIN_COMMAND_BYTES = 12
HEADER_BYTES = 6
CRC_BYTES = 2
SEQUENCE_MODULUS = 16384

VERSION = 0
TYPE_COMMAND = 1
TYPE_DOWNLINK = 0
COMMAND_APID = 0x001
DOWNLINK_APID = 0x002
UNSEGMENTED = 0b11

_HEADER = struct.Struct(">HHH")
_CRC = struct.Struct(">H")


class CommandCode(IntEnum):
    PING = 0x01
    GET_TELEMETRY = 0x02
    SET_MODE = 0x03
    DEPLOY_ANTENNA = 0x04
    SET_HEATER = 0x05
    REBOOT = 0x06


class Role(IntEnum):
    GUEST = 0
    OPERATOR = 1


class Status(IntEnum):
    ACCEPTED = 0x00
    BAD_ENVELOPE = 0x01
    BAD_CHECKSUM = 0x02
    REPLAY_DETECTED = 0x03
    UNAUTHORIZED = 0x04
    UNKNOWN_COMMAND = 0x05
    INVALID_ARGUMENTS = 0x06
    UNAVAILABLE = 0x07


class DownlinkKind(IntEnum):
    TELEMETRY = 0x10
    REPLY = 0x11


class Unreadable(StrEnum):
    """Why a submission cannot be read; it gets feedback but never a reply."""

    TOO_LARGE = "PACKET_TOO_LARGE"
    TRUNCATED_HEADER = "TRUNCATED_HEADER"
    TRUNCATED_BODY = "TRUNCATED_BODY"
    AMBIGUOUS_BODY = "AMBIGUOUS_BODY"

    @property
    def message(self) -> str:
        return _UNREADABLE_MESSAGES[self]


_UNREADABLE_MESSAGES = {
    Unreadable.TOO_LARGE: (
        f"Packet is larger than {MAX_PACKET_BYTES} bytes; it was not sent to the Link."
    ),
    Unreadable.TRUNCATED_HEADER: (
        "Cannot read packet: the 6-byte header is incomplete; no reply generated."
    ),
    Unreadable.TRUNCATED_BODY: (
        "Cannot read packet: command body is truncated; no reply generated."
    ),
    Unreadable.AMBIGUOUS_BODY: (
        "Cannot read packet: unexplained bytes follow the command body; "
        "no reply generated."
    ),
}


class SequenceCounter:
    """One sender's packet count: starts at zero, advances modulo 16384."""

    def __init__(self) -> None:
        self._next = 0

    def next(self) -> int:
        value = self._next
        self._next = (self._next + 1) % SEQUENCE_MODULUS
        return value


@dataclass(frozen=True)
class Header:
    version: int
    packet_type: int
    secondary_header: int
    apid: int
    sequence_flags: int
    sequence_count: int
    data_length: int


def encode_header(
    *,
    packet_type: int,
    apid: int,
    sequence_count: int,
    data_length: int,
    version: int = VERSION,
    secondary_header: int = 0,
    sequence_flags: int = UNSEGMENTED,
) -> bytes:
    if not 0 <= sequence_count < SEQUENCE_MODULUS:
        raise ValueError("Sequence count must be 0..16383")
    if not 0 <= apid < 0x800:
        raise ValueError("APID must fit in 11 bits")
    first = (version << 13) | (packet_type << 12) | (secondary_header << 11) | apid
    second = (sequence_flags << 14) | sequence_count
    return _HEADER.pack(first, second, data_length)


def decode_header(data: bytes) -> Header:
    if len(data) < HEADER_BYTES:
        raise ValueError("A header needs 6 bytes")
    first, second, data_length = _HEADER.unpack_from(data)
    return Header(
        version=first >> 13,
        packet_type=(first >> 12) & 1,
        secondary_header=(first >> 11) & 1,
        apid=first & 0x7FF,
        sequence_flags=second >> 14,
        sequence_count=second & 0x3FFF,
        data_length=data_length,
    )


def encode_packet(
    *, packet_type: int, apid: int, sequence_count: int, body: bytes
) -> bytes:
    """Header, body and a correct CRC. Data length counts body + CRC − 1."""
    header = encode_header(
        packet_type=packet_type,
        apid=apid,
        sequence_count=sequence_count,
        data_length=len(body) + CRC_BYTES - 1,
    )
    unsigned = header + body
    packet = unsigned + _CRC.pack(crc16_ccitt_false(unsigned))
    if len(packet) > MAX_PACKET_BYTES:
        raise ValueError(f"Packet exceeds {MAX_PACKET_BYTES} bytes")
    return packet


def encode_command(
    code: int,
    sequence_count: int,
    *,
    role: int = Role.GUEST,
    arguments: bytes = b"",
    authorization: bytes = b"",
) -> bytes:
    body = (
        bytes([code, role, len(arguments)])
        + arguments
        + bytes([len(authorization)])
        + authorization
    )
    return encode_packet(
        packet_type=TYPE_COMMAND,
        apid=COMMAND_APID,
        sequence_count=sequence_count,
        body=body,
    )


def encode_telemetry(sequence_count: int, state: SatelliteState) -> bytes:
    return encode_packet(
        packet_type=TYPE_DOWNLINK,
        apid=DOWNLINK_APID,
        sequence_count=sequence_count,
        body=bytes([DownlinkKind.TELEMETRY]) + state.encode(),
    )


def encode_reply(
    sequence_count: int,
    *,
    command_code: int,
    echoed_sequence: int,
    status: Status,
    state: SatelliteState,
) -> bytes:
    body = (
        bytes([DownlinkKind.REPLY, command_code])
        + struct.pack(">H", echoed_sequence)
        + bytes([status])
        + state.encode()
    )
    return encode_packet(
        packet_type=TYPE_DOWNLINK,
        apid=DOWNLINK_APID,
        sequence_count=sequence_count,
        body=body,
    )


@dataclass(frozen=True)
class CommandPacket:
    """An interpretable command: every body section is bounded by the bytes."""

    raw: bytes
    header: Header
    code: int
    role: int
    arguments: bytes
    authorization: bytes
    received_crc: int
    computed_crc: int

    @property
    def crc_ok(self) -> bool:
        return self.received_crc == self.computed_crc

    @property
    def header_constants_ok(self) -> bool:
        h = self.header
        return (
            h.version == VERSION
            and h.packet_type == TYPE_COMMAND
            and h.secondary_header == 0
            and h.apid == COMMAND_APID
            and h.sequence_flags == UNSEGMENTED
        )

    @property
    def length_ok(self) -> bool:
        return self.header.data_length + HEADER_BYTES + 1 == len(self.raw)


def parse_command(data: bytes) -> CommandPacket | Unreadable:
    """Minimum safe parsing using the actual message boundary.

    The last two bytes are always the CRC slot; the declared data length is
    never trusted to find them.
    """
    if len(data) > MAX_PACKET_BYTES:
        return Unreadable.TOO_LARGE
    if len(data) < HEADER_BYTES:
        return Unreadable.TRUNCATED_HEADER
    body = data[HEADER_BYTES:-CRC_BYTES] if len(data) >= HEADER_BYTES + 2 else b""
    if len(body) < 3:
        return Unreadable.TRUNCATED_BODY
    code, role, argument_count = body[0], body[1], body[2]
    authorization_count_at = 3 + argument_count
    if authorization_count_at >= len(body):
        return Unreadable.TRUNCATED_BODY
    authorization_count = body[authorization_count_at]
    end = authorization_count_at + 1 + authorization_count
    if end > len(body):
        return Unreadable.TRUNCATED_BODY
    if end < len(body):
        return Unreadable.AMBIGUOUS_BODY
    (received_crc,) = _CRC.unpack_from(data, len(data) - CRC_BYTES)
    return CommandPacket(
        raw=data,
        header=decode_header(data),
        code=code,
        role=role,
        arguments=body[3:authorization_count_at],
        authorization=body[authorization_count_at + 1 : end],
        received_crc=received_crc,
        computed_crc=crc16_ccitt_false(data[:-CRC_BYTES]),
    )


@dataclass(frozen=True)
class DownlinkPacket:
    header: Header
    kind: DownlinkKind
    state: SatelliteState
    crc_ok: bool
    command_code: int | None = None
    echoed_sequence: int | None = None
    status: Status | None = None


def decode_downlink(data: bytes) -> DownlinkPacket:
    """Decode a reply or telemetry packet; raises ValueError if malformed."""
    if not HEADER_BYTES + 1 + CRC_BYTES <= len(data) <= MAX_PACKET_BYTES:
        raise ValueError("Downlink packet has an impossible length")
    header = decode_header(data)
    body = data[HEADER_BYTES:-CRC_BYTES]
    (received_crc,) = _CRC.unpack_from(data, len(data) - CRC_BYTES)
    crc_ok = received_crc == crc16_ccitt_false(data[:-CRC_BYTES])
    kind = DownlinkKind(body[0])
    if kind is DownlinkKind.TELEMETRY:
        if len(body) != 1 + STATE_BYTES:
            raise ValueError("Telemetry body must be 19 bytes")
        return DownlinkPacket(header, kind, SatelliteState.decode(body[1:]), crc_ok)
    if len(body) != 5 + STATE_BYTES:
        raise ValueError("Reply body must be 23 bytes")
    (echoed,) = struct.unpack_from(">H", body, 2)
    return DownlinkPacket(
        header,
        kind,
        SatelliteState.decode(body[5:]),
        crc_ok,
        command_code=body[1],
        echoed_sequence=echoed,
        status=Status(body[4]),
    )
