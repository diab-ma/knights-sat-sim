import pytest
from fastapi.testclient import TestClient

from api.challenges import list_challenges
from api.main import app


@pytest.fixture(autouse=True)
def disable_dev_unlock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEV_UNLOCK_ALL", raising=False)


@pytest.mark.parametrize(
    ("completed_ids", "expected_availability"),
    [
        (set(), ["available", "locked", "locked"]),
        ({"hello-satellite"}, ["available", "available", "locked"]),
        (
            {"hello-satellite", "ready-for-the-pass"},
            ["available", "available", "available"],
        ),
    ],
)
def test_challenge_progression(
    completed_ids: set[str], expected_availability: list[str]
) -> None:
    challenges = list_challenges(completed_ids)
    assert [item.availability for item in challenges] == expected_availability
    assert [item.completed for item in challenges] == [
        item.challenge_id in completed_ids for item in challenges
    ]


def test_challenge_endpoint() -> None:
    response = TestClient(app).get("/api/challenges")
    assert response.status_code == 200
    assert response.json() == {
        "challenges": [
            {
                "challenge_id": "hello-satellite",
                "title": "Hello, Satellite!",
                "availability": "available",
                "prerequisite_ids": [],
                "completed": False,
            },
            {
                "challenge_id": "ready-for-the-pass",
                "title": "Ready for the Pass",
                "availability": "locked",
                "prerequisite_ids": ["hello-satellite"],
                "completed": False,
            },
            {
                "challenge_id": "catch-and-log",
                "title": "Catch and Log",
                "availability": "locked",
                "prerequisite_ids": ["ready-for-the-pass"],
                "completed": False,
            },
        ],
        "progress": {"completed_challenge_ids": []},
    }


def test_dev_unlock_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_UNLOCK_ALL", "1")
    response = TestClient(app).get("/api/challenges")
    assert response.status_code == 200
    data = response.json()
    assert len(data["challenges"]) == 3
    assert all(item["availability"] == "available" for item in data["challenges"])
    assert all(item["completed"] is False for item in data["challenges"])
    assert data["progress"] == {"completed_challenge_ids": []}
