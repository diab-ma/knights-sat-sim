import os

from api.schemas import Challenge

CHALLENGES = (
    ("hello-satellite", "Hello, Satellite!", ()),
    ("ready-for-the-pass", "Ready for the Pass", ("hello-satellite",)),
    ("catch-and-log", "Catch and Log", ("ready-for-the-pass",)),
)


def list_challenges(completed_ids: set[str]) -> list[Challenge]:
    unlock_all = os.getenv("DEV_UNLOCK_ALL") == "1"
    return [
        Challenge(
            challenge_id=challenge_id,
            title=title,
            availability=(
                "available"
                if unlock_all or all(item in completed_ids for item in prerequisites)
                else "locked"
            ),
            prerequisite_ids=list(prerequisites),
            completed=challenge_id in completed_ids,
        )
        for challenge_id, title, prerequisites in CHALLENGES
    ]
