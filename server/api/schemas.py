from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Challenge(BaseModel):
    challenge_id: str
    title: str
    availability: Literal["available", "locked"]
    prerequisite_ids: list[str]
    completed: bool


class Progress(BaseModel):
    completed_challenge_ids: list[str]


class ChallengeList(BaseModel):
    challenges: list[Challenge]
    progress: Progress


class Check(BaseModel):
    field: str
    passed: bool
    message: str


class PassView(BaseModel):
    pass_run_id: str
    status: Literal["not_started", "running", "finished", "interrupted"]
    receiver_ready: bool
    received_count: int


class StateView(BaseModel):
    mode: Literal["SAFE", "NOMINAL"]
    antenna_deployed: bool
    deploy_count: int
    heater_on: bool
    battery_pct: int
    uptime_s: int
    commands_received: int
    last_seq_seen: int | None


class Feedback(BaseModel):
    code: str
    message: str


class HistoryEntry(BaseModel):
    time: datetime
    direction: Literal["uplink", "downlink"]
    packet_hex: str
    origin: Literal["raw_player", "satellite"]
    pass_index: int | None
    feedback: Feedback | None


class Session(BaseModel):
    session_id: str
    challenge_id: str
    status: Literal["starting", "running", "failed"]
    state: StateView
    history: list[HistoryEntry]
    pass_view: PassView | None = Field(alias="pass")
    goal_reached: bool
    completion: Literal["not_yet", "saved", "save_failed"]
    checks: list[Check]
