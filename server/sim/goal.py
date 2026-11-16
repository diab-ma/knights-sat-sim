"""Hello's conformance check for an accepted command.

This is a goal check, not a rejection Defense: a non-conforming command still
executes and keeps its real reply (docs/specs/challenges/01-hello-satellite.md).
"""

from enum import StrEnum

from sim.packet import CommandCode, CommandPacket, Role


class GoalIssue(StrEnum):
    NOT_PING = "NOT_PING"
    BAD_HEADER = "BAD_HEADER"
    LENGTH_MISMATCH = "LENGTH_MISMATCH"
    BAD_CHECKSUM = "BAD_CHECKSUM"
    UNKNOWN_ROLE = "UNKNOWN_ROLE"
    HAS_ARGUMENTS = "HAS_ARGUMENTS"
    HAS_AUTHORIZATION_DATA = "HAS_AUTHORIZATION_DATA"

    @property
    def message(self) -> str:
        return _MESSAGES[self]


_NOT_FORMED = "PING accepted, but the Challenge asks for a correctly formed packet."
_MESSAGES = {
    GoalIssue.NOT_PING: "Command accepted. This Challenge asks you to send PING.",
    GoalIssue.BAD_HEADER: f"{_NOT_FORMED} Check the header fields.",
    GoalIssue.LENGTH_MISMATCH: f"{_NOT_FORMED} Check the packet data length.",
    GoalIssue.BAD_CHECKSUM: f"{_NOT_FORMED} Check the checksum.",
    GoalIssue.UNKNOWN_ROLE: f"{_NOT_FORMED} Check the Mission role byte.",
    GoalIssue.HAS_ARGUMENTS: f"{_NOT_FORMED} PING takes no arguments.",
    GoalIssue.HAS_AUTHORIZATION_DATA: f"{_NOT_FORMED} Remove the authorization data.",
}


def ping_conformance_issue(command: CommandPacket) -> GoalIssue | None:
    """The first mismatched Hello requirement, or None for a conforming PING."""
    if command.code != CommandCode.PING:
        return GoalIssue.NOT_PING
    if not command.header_constants_ok:
        return GoalIssue.BAD_HEADER
    if not command.length_ok:
        return GoalIssue.LENGTH_MISMATCH
    if not command.crc_ok:
        return GoalIssue.BAD_CHECKSUM
    if command.role not in Role:
        return GoalIssue.UNKNOWN_ROLE
    if command.arguments:
        return GoalIssue.HAS_ARGUMENTS
    if command.authorization:
        return GoalIssue.HAS_AUTHORIZATION_DATA
    return None
