"""Error contract.

Every failure the UI can show is one of a small set of kinds, matching
`AppErrorKind` in the frontend. The handler renders them as
`{"kind": ..., "detail": ...}` so the client never has to parse prose.
"""

import logging
from typing import Literal

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

ErrorKind = Literal[
    "network",
    "generation_failed",
    "pool_empty",
    "budget_exceeded",
    "blocked_event",
    "auth",
]

_STATUS: dict[str, int] = {
    "network": 502,
    "generation_failed": 500,
    "pool_empty": 503,
    "budget_exceeded": 429,
    "blocked_event": 422,
    "auth": 401,
}


class AppError(Exception):
    def __init__(self, kind: ErrorKind, detail: str = "", status_code: int | None = None) -> None:
        super().__init__(detail or kind)
        self.kind: ErrorKind = kind
        self.detail = detail or kind
        self.status_code = status_code or _STATUS.get(kind, 500)


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status_code,
        content={"kind": exc.kind, "detail": exc.detail},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything that was not an `AppError`, in the shape the client expects.

    Without this a bug reaches the browser as FastAPI's default 500 body,
    which carries no `kind`; the client falls back to "cannot reach the
    server", and the traceback is the only place the real cause exists. This
    logs it and answers in the contract, so the error screen says something
    true and the logs say what actually happened.
    """
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"kind": "generation_failed", "detail": type(exc).__name__},
    )
