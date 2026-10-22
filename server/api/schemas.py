from typing import Literal

from pydantic import BaseModel


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
