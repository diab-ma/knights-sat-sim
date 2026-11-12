"""Explicit, session-safe reset of shared demo completion."""

import asyncio
import sqlite3
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from api.progress import reset_completion
from api.schemas import ApiError, ErrorResponse, Progress, ResetProgressRequest
from api.session import SessionService


def failure(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ApiError(code=code, message=message))
    return JSONResponse(status_code=status, content=body.model_dump())


class ResetRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            origin = request.headers.get("origin")
            if origin is not None and origin != str(request.base_url).rstrip("/"):
                return failure(403, "INVALID_ORIGIN", "Use this site's own origin.")
            try:
                return await handler(request)
            except RequestValidationError:
                return failure(
                    422, "INVALID_INPUT", "Confirm with RESET DEMO PROGRESS."
                )

        return handle


router = APIRouter(route_class=ResetRoute)


@router.post(
    "/api/progress/reset",
    response_model=Progress,
    responses={code: {"model": ErrorResponse} for code in (403, 409, 422, 503)},
)
async def reset_progress(
    body: ResetProgressRequest, request: Request
) -> Progress | JSONResponse:
    service: SessionService | None = getattr(request.app.state, "session_service", None)
    # Session startup/completion/reset must coordinate through this same lock.
    lock = service.lock if service is not None else request.app.state.progress_lock
    async with lock:
        if service is not None and service.read() is not None:
            return failure(
                409, "SESSION_ACTIVE", "Stop the session before resetting progress."
            )
        worker = asyncio.create_task(asyncio.to_thread(reset_completion))
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            # Keep the lock until SQLite has committed or rolled back.
            try:
                await worker
            finally:
                raise
        except (sqlite3.Error, OSError):
            return failure(
                503, "STORAGE_UNAVAILABLE", "Progress could not be reset. Try again."
            )
    return Progress(completed_challenge_ids=[])
