from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.challenges import list_challenges
from api.schemas import ChallengeList, Progress

app = FastAPI(title="Satellite Security Challenge Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/challenges", response_model=ChallengeList)
def get_challenges() -> ChallengeList:
    return ChallengeList(
        challenges=list_challenges(set()),
        progress=Progress(completed_challenge_ids=[]),
    )
