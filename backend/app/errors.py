"""Error contract.

Every failure the UI can show is one of a small set of kinds, matching
`AppErrorKind` in the frontend. The handler renders them as
`{"kind": ..., "detail": ...}` so the client never has to parse prose.
"""

from typing import Literal

from fastapi import Request
from fastapi.responses import JSONResponse

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
