"""Browser lifecycle adapters for the process-wide session engine."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from api.progress_routes import failure
from api.runtime import RuntimeFailure
from api.schemas import ErrorResponse, Session, StartSessionRequest
from api.session import SessionFailure, SessionService


class SessionRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            origin = request.headers.get("origin")
            if origin is not None and origin != str(request.base_url).rstrip("/"):
                return failure(403, "INVALID_ORIGIN", "Use this site's own origin.")
            try:
                return await handler(request)
            except RequestValidationError:
                return failure(422, "INVALID_INPUT", "Provide a challenge_id string.")
            except (SessionFailure, RuntimeFailure) as error:
                status = (
                    503
                    if error.code
                    in {"RUNTIME_UNAVAILABLE", "CLEANUP_FAILED", "STORAGE_UNAVAILABLE"}
                    else 409
                )
                return failure(status, error.code, str(error))

        return handle


router = APIRouter(route_class=SessionRoute)
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 409, 422, 503)
}


def session_service(request: Request) -> SessionService:
    service = getattr(request.app.state, "session_service", None)
    if service is None:
        raise RuntimeFailure(
            "RUNTIME_UNAVAILABLE", "Session runtime is not configured."
        )
    return service


@router.post("/api/session", status_code=201, response_model=Session, responses=ERRORS)
async def start_session(body: StartSessionRequest, request: Request) -> Session:
    return await session_service(request).start(body.challenge_id)


@router.delete("/api/session", status_code=204, responses=ERRORS)
async def stop_session(request: Request) -> Response:
    await session_service(request).stop()
    return Response(status_code=204)
