"""Satellite Sim state and its 18-byte telemetry layout."""

import struct
from dataclasses import dataclass
from enum import IntEnum

STATE_BYTES = 18
COUNTER_MAX = 0xFFFFFFFF
NO_SEQUENCE_WIRE = 0xFFFF

# mode, antenna_deployed, deploy_count, heater_on, battery_pct, uptime_s,
# commands_received, last_seq_seen
_LAYOUT = struct.Struct(">BBIBBIIH")


class Mode(IntEnum):
    SAFE = 0
    NOMINAL = 1


def saturating_increment(value: int) -> int:
    """Four-byte counters stop at 0xFFFFFFFF instead of rolling over."""
    return min(value + 1, COUNTER_MAX)


@dataclass(frozen=True)
class SatelliteState:
    """Defaults are Hello's starting state.

    ``last_seq_seen`` is ``None`` before any accepted command; the wire carries
    that as 0xFFFF.
    """

    mode: Mode = Mode.SAFE
    antenna_deployed: bool = False
    deploy_count: int = 0
    heater_on: bool = False
    battery_pct: int = 100
    uptime_s: int = 0
    commands_received: int = 0
    last_seq_seen: int | None = None

    def encode(self) -> bytes:
        return _LAYOUT.pack(
            self.mode,
            int(self.antenna_deployed),
            min(self.deploy_count, COUNTER_MAX),
            int(self.heater_on),
            max(0, min(int(self.battery_pct), 100)),
            min(self.uptime_s, COUNTER_MAX),
            min(self.commands_received, COUNTER_MAX),
            NO_SEQUENCE_WIRE if self.last_seq_seen is None else self.last_seq_seen,
        )

    @classmethod
    def decode(cls, data: bytes) -> "SatelliteState":
        if len(data) != STATE_BYTES:
            raise ValueError(f"State snapshot must be {STATE_BYTES} bytes")
        (mode, antenna, deploys, heater, battery, uptime, received, last_seq) = (
            _LAYOUT.unpack(data)
        )
        return cls(
            mode=Mode(mode),
            antenna_deployed=bool(antenna),
            deploy_count=deploys,
            heater_on=bool(heater),
            battery_pct=battery,
            uptime_s=uptime,
            commands_received=received,
            last_seq_seen=None if last_seq == NO_SEQUENCE_WIRE else last_seq,
        )
