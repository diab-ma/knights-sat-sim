"""Stateless preparation for the fictional KnightSat training pass."""

import sqlite3
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from api import progress
from api.challenges import list_challenges
from api.schemas import Check, ReadyBrief, ReadyCheck, StationSetup

CHALLENGE_ID = "ready-for-the-pass"
SCENARIO_ID = "knightsat-training-v1"
EXPECTED_SETUP = StationSetup(
    satellite_id="KNIGHTSAT",
    pass_start_utc="2026-09-21T18:00:00Z",
    receive_frequency_hz=145825000,
    receive_mode="FM",
    tracking_enabled=True,
)
MESSAGES = {
    "satellite_id": "Select KNIGHTSAT, the satellite named in the practice brief.",
    "pass_start_utc": "Set the scheduled practice pass time to 2026-09-21T18:00:00Z.",
    "receive_frequency_hz": "Tune to 145825000 Hz (145.825 MHz) to match the brief.",
    "receive_mode": "Select FM, the receiving mode specified in the brief.",
    "tracking_enabled": "Enable automatic tracking to follow the satellite.",
}


def error(status: int, code: str, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}, **extra},
    )


class ReadyRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            if request.method == "POST":
                origin = request.headers.get("origin")
                if origin is not None and origin != str(request.base_url).rstrip("/"):
                    return error(403, "INVALID_ORIGIN", "Use this site's own origin.")
            try:
                return await handler(request)
            except RequestValidationError:
                return error(
                    422,
                    "INVALID_INPUT",
                    "Submit five settings with valid types and positive integer Hz.",
                )

        return handle


router = APIRouter(prefix=f"/api/challenges/{CHALLENGE_ID}", route_class=ReadyRoute)


def require_unlocked() -> JSONResponse | None:
    try:
        challenges = list_challenges(progress.read_completed())
    except (sqlite3.Error, OSError):
        return error(
            503, "STORAGE_UNAVAILABLE", "Progress could not be read. Try again."
        )
    challenge = next(item for item in challenges if item.challenge_id == CHALLENGE_ID)
    if challenge.availability == "locked":
        return error(409, "CHALLENGE_LOCKED", "Complete Hello, Satellite! first.")
    return None


@router.get("/brief", response_model=ReadyBrief)
def get_brief() -> ReadyBrief | JSONResponse:
    if failure := require_unlocked():
        return failure
    return ReadyBrief(
        scenario_id=SCENARIO_ID,
        brief=EXPECTED_SETUP.model_copy(),
        starting_setup=EXPECTED_SETUP.model_copy(
            update={"receive_frequency_hz": 145800000, "tracking_enabled": False}
        ),
    )


@router.post("/check", response_model=ReadyCheck)
def check_setup(setup: StationSetup) -> ReadyCheck | JSONResponse:
    if failure := require_unlocked():
        return failure
    checks = [
        Check(
            field=field,
            passed=getattr(setup, field) == getattr(EXPECTED_SETUP, field),
            message=(
                "This setting matches the practice brief."
                if getattr(setup, field) == getattr(EXPECTED_SETUP, field)
                else message
            ),
        )
        for field, message in MESSAGES.items()
    ]
    if not all(check.passed for check in checks):
        return ReadyCheck(checks=checks, completion="not_yet")
    try:
        progress.save_completion(CHALLENGE_ID)
    except (sqlite3.Error, OSError):
        return error(
            503,
            "STORAGE_UNAVAILABLE",
            "Setup is correct, but saving failed. Try Check setup again.",
            **ReadyCheck(checks=checks, completion="save_failed").model_dump(),
        )
    return ReadyCheck(checks=checks, completion="saved")
