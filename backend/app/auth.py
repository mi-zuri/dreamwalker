"""Firebase ID token verification.

The frontend signs in with Google via Firebase and sends the resulting ID
token as a bearer token. Everything user-scoped hangs off the uid this
returns, so a request that cannot be verified never reaches the pipeline.
"""

import logging
from typing import Annotated

import firebase_admin
from fastapi import Depends, Request
from firebase_admin import auth as fb_auth

from app.errors import AppError
from app.settings import settings

log = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def _firebase() -> firebase_admin.App:
    global _app
    if _app is None:
        # Uses Application Default Credentials; no service-account key file.
        _app = firebase_admin.initialize_app(options={"projectId": settings.gcp_project})
    return _app


class User:
    def __init__(self, uid: str, email: str | None, name: str | None):
        self.uid = uid
        self.email = email
        self.name = name


def _dev_user() -> User:
    return User(uid="dev-user", email="dev@localhost", name="Dev")


async def verify_token(token: str) -> User:
    """Resolves a bearer token to a user, or raises.

    With `auth_mode=dev` every caller is the same local user, so the whole app
    can be exercised before Firebase config exists. That mode must never be
    used in deployment - Phase 8 sets `auth_mode=firebase`.
    """
    if settings.auth_mode == "dev":
        return _dev_user()

    if not token:
        raise AppError("auth", "missing bearer token")

    try:
        decoded = fb_auth.verify_id_token(token, app=_firebase())
    except Exception as exc:  # firebase-admin raises several distinct types
        log.info("token verification failed: %s", type(exc).__name__)
        raise AppError("auth", "invalid token") from exc

    email = decoded.get("email")
    if settings.invite_only and email not in settings.allowed_emails:
        raise AppError("auth", "not on the invite list", status_code=403)

    return User(uid=decoded["uid"], email=email, name=decoded.get("name"))


async def current_user(request: Request) -> User:
    header = request.headers.get("authorization", "")
    if settings.auth_mode != "dev" and not header.startswith("Bearer "):
        raise AppError("auth", "missing bearer token")
    return await verify_token(header.removeprefix("Bearer ").strip())


async def verify_ws(token: str) -> User:
    """The same check, for the music socket.

    A browser cannot set headers on a WebSocket, so the token arrives as a
    query parameter. That puts it in access logs, which is why it is only ever
    used here and never for the SSE stream - that one reads the body with
    `fetch` precisely so the token can stay in a header.
    """
    return await verify_token(token.strip())


CurrentUser = Annotated[User, Depends(current_user)]
