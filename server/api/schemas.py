from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class StationSetup(BaseModel):
    model_config = ConfigDict(strict=True)

    satellite_id: str
    pass_start_utc: str
    receive_frequency_hz: int = Field(gt=0)
    receive_mode: str
    tracking_enabled: bool


class Check(BaseModel):
    field: str
    passed: bool
    message: str


class ReadyBrief(BaseModel):
    scenario_id: str
    brief: StationSetup
    starting_setup: StationSetup


class ReadyCheck(BaseModel):
    checks: list[Check]
    completion: Literal["not_yet", "saved", "save_failed"]
