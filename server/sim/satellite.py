"""Satellite Sim command execution for the six Packet v1 commands."""

import math
from dataclasses import replace

from sim.packet import CommandCode, CommandPacket, Status
from sim.state import COUNTER_MAX, Mode, SatelliteState, saturating_increment

_NO_ARGUMENTS = {
    CommandCode.PING,
    CommandCode.GET_TELEMETRY,
    CommandCode.DEPLOY_ANTENNA,
    CommandCode.REBOOT,
}
_ONE_BOOLEAN_ARGUMENT = {CommandCode.SET_MODE, CommandCode.SET_HEATER}


class Satellite:
    """Spacecraft state for one session.

    Uptime is whole seconds since session start or the latest REBOOT, read
    from the clock rather than counted by a timer. Battery stays at its
    initial value for Hello.
    """

    def __init__(self, now: float, initial: SatelliteState | None = None) -> None:
        self._state = replace(initial or SatelliteState(), uptime_s=0)
        self._uptime_origin = now

    def snapshot(self, now: float) -> SatelliteState:
        elapsed = max(0, math.floor(now - self._uptime_origin))
        return replace(self._state, uptime_s=min(elapsed, COUNTER_MAX))

    def execute(
        self, command: CommandPacket, now: float
    ) -> tuple[Status, SatelliteState]:
        """Run an interpretable command. Rejection leaves state unchanged."""
        status = _validate(command)
        if status is not Status.ACCEPTED:
            return status, self.snapshot(now)

        state = self._state
        code = CommandCode(command.code)
        if code is CommandCode.SET_MODE:
            state = replace(state, mode=Mode(command.arguments[0]))
        elif code is CommandCode.SET_HEATER:
            state = replace(state, heater_on=bool(command.arguments[0]))
        elif code is CommandCode.DEPLOY_ANTENNA:
            state = replace(
                state,
                antenna_deployed=True,
                deploy_count=saturating_increment(state.deploy_count),
            )
        elif code is CommandCode.REBOOT:
            # Keeps battery, antenna, counts and sequence history.
            state = replace(state, mode=Mode.SAFE, heater_on=False)
            self._uptime_origin = now
        self._state = replace(
            state,
            commands_received=saturating_increment(state.commands_received),
            last_seq_seen=command.header.sequence_count,
        )
        return status, self.snapshot(now)


def _validate(command: CommandPacket) -> Status:
    if command.code not in CommandCode:
        return Status.UNKNOWN_COMMAND
    code = CommandCode(command.code)
    if code in _NO_ARGUMENTS and command.arguments:
        return Status.INVALID_ARGUMENTS
    if code in _ONE_BOOLEAN_ARGUMENT and (
        len(command.arguments) != 1 or command.arguments[0] not in (0, 1)
    ):
        return Status.INVALID_ARGUMENTS
    return Status.ACCEPTED
