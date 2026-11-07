import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.challenges import list_challenges
from api.progress import migrate, read_completed
from api.schemas import ChallengeList, Progress


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(migrate)
    yield


app = FastAPI(title="Satellite Security Challenge Platform", lifespan=lifespan)

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
    completed_ids = read_completed()
    return ChallengeList(
        challenges=list_challenges(completed_ids),
        progress=Progress(completed_challenge_ids=sorted(completed_ids)),
    )
