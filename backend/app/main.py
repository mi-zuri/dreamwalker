"""HTTP surface.

The whole game loop is server-authoritative: the client animates movement and
renders scenes, but every transition goes through `app.pipeline.engine` here,
against the server's own copy of the state.
"""

import json
import logging
from contextlib import suppress
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.auth import CurrentUser, verify_ws
from app.errors import AppError, ErrorKind, app_error_handler
from app.game.map import destination_at
from app.media import PALETTES, placeholder_svg
from app.models.game import (
    AnswerRequest,
    ApiError,
    ChooseRequest,
    EndingComparison,
    GameState,
    MoveRequest,
    NewGameRequest,
    NewGameResponse,
    Replay,
    SavedGame,
    StageEvent,
)
from app.models.script import GameScript
from app.music import session as session_module
from app.pipeline import engine, orchestrator
from app.settings import settings
from app.storage import get_store
from app.storage.assets import get_assets
from app.storage.base import GameStore

log = logging.getLogger(__name__)

app = FastAPI(title="Dreamwalker API", version="0.1.0")
app.add_exception_handler(AppError, app_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def store() -> GameStore:
    return get_store()


Store = Depends(store)

#: Armed by the dev panel to exercise the error screens. Mock mode only.
_forced_error: ErrorKind | None = None


def _raise_if_forced() -> None:
    global _forced_error
    if _forced_error is not None:
        kind, _forced_error = _forced_error, None
        raise AppError(kind, "forced from the dev panel")


async def _load(st: GameStore, uid: str, game_id: str) -> tuple[GameState, GameScript]:
    state = await st.get_state(uid, game_id)
    script = await st.get_script(uid, game_id)
    if state is None or script is None:
        raise AppError("network", f"unknown game {game_id}", status_code=404)
    return state, script


async def _commit(st: GameStore, uid: str, state: GameState, script: GameScript) -> GameState:
    await st.put_state(uid, state)
    await st.put_script(uid, script)
    return state


class Me(BaseModel):
    uid: str
    email: str | None = None
    name: str | None = None


class Health(BaseModel):
    status: str
    llm_mode: str
    music_mode: str
    auth_mode: str


@app.get("/health")
def health() -> Health:
    return Health(
        status="ok",
        llm_mode=settings.llm_mode,
        music_mode=settings.music_mode,
        auth_mode=settings.auth_mode,
    )


@app.get("/api/me")
def me(user: CurrentUser) -> Me:
    """Verifies the token and enforces the invite list before the menu opens."""
    return Me(uid=user.uid, email=user.email, name=user.name)


# ── Game lifecycle ──────────────────────────────────────────────────────


#: The error model is declared here so it lands in the generated schema;
#: every endpoint answers failures with the same `{kind, detail}` body.
@app.post("/api/games", responses={"4XX": {"model": ApiError}})
async def create_game(
    req: NewGameRequest, user: CurrentUser, st: GameStore = Store
) -> NewGameResponse:
    _raise_if_forced()
    game_id = await orchestrator.start_game(st, user.uid, req)
    return NewGameResponse(game_id=game_id)


@app.get("/api/games/{game_id}/stream", response_model=StageEvent)
async def stream(game_id: str, user: CurrentUser, st: GameStore = Store) -> EventSourceResponse:
    """Coarse loading progress, and the only place a generation failure surfaces.

    Deliberately does not load the game first: under live generation the state
    does not exist yet when the client subscribes, which is the entire reason
    this stream exists.
    """
    if orchestrator.job_for(game_id) is None:
        await _load(st, user.uid, game_id)
    return EventSourceResponse(orchestrator.stream_progress(game_id))


@app.get("/api/games")
async def list_games(user: CurrentUser, st: GameStore = Store) -> list[SavedGame]:
    _raise_if_forced()
    return await st.list_saved(user.uid)


@app.get("/api/games/{game_id}")
async def get_game(game_id: str, user: CurrentUser, st: GameStore = Store) -> GameState:
    state, _ = await _load(st, user.uid, game_id)
    return state


# ── Turns ───────────────────────────────────────────────────────────────


@app.post("/api/games/{game_id}/move")
async def move(
    game_id: str, req: MoveRequest, user: CurrentUser, st: GameStore = Store
) -> GameState:
    state, script = await _load(st, user.uid, game_id)

    # Scenes are written in the background while the player reads the premise
    # and walks. A player who sprints to the first location can beat them, so
    # the move waits rather than dropping them into an empty room.
    target = destination_at(state.map, req.to)
    if target is not None and target.location_id not in script.scenes:
        await orchestrator.await_scenes(game_id)
        state, script = await _load(st, user.uid, game_id)

    engine.apply_move(state, script, req.to)
    return await _commit(st, user.uid, state, script)


@app.post("/api/games/{game_id}/choose")
async def choose(
    game_id: str, req: ChooseRequest, user: CurrentUser, st: GameStore = Store
) -> GameState:
    state, script = await _load(st, user.uid, game_id)
    engine.apply_choice(state, script, req.choice_id)
    return await _commit(st, user.uid, state, script)


@app.post("/api/games/{game_id}/answer")
async def answer(
    game_id: str, req: AnswerRequest, user: CurrentUser, st: GameStore = Store
) -> GameState:
    state, script = await _load(st, user.uid, game_id)
    engine.apply_answer(state, script, req.text)
    return await _commit(st, user.uid, state, script)


@app.post("/api/games/{game_id}/set-off")
async def set_off(game_id: str, user: CurrentUser, st: GameStore = Store) -> GameState:
    state, script = await _load(st, user.uid, game_id)
    engine.set_off(state)
    return await _commit(st, user.uid, state, script)


# ── Ending, library, replay ─────────────────────────────────────────────


def _replay_of(script: GameScript) -> Replay:
    return Replay(game_id=script.game_id, title=script.ending.title, turns=script.turns)


@app.get("/api/games/{game_id}/ending")
async def ending(game_id: str, user: CurrentUser, st: GameStore = Store) -> EndingComparison:
    state, script = await _load(st, user.uid, game_id)
    if state.finished:
        await orchestrator.finish_ending(st, user.uid, state, script)
        await st.put_script(user.uid, script)
        await st.save_finished(
            user.uid,
            engine.to_saved(state, script, datetime.now(UTC).isoformat()),
            script.ending,
            _replay_of(script),
        )
    return script.ending


@app.get("/api/games/{game_id}/replay")
async def replay(game_id: str, user: CurrentUser, st: GameStore = Store) -> Replay:
    stored = await st.get_replay(user.uid, game_id)
    if stored is not None:
        return stored
    _, script = await _load(st, user.uid, game_id)
    return _replay_of(script)


# ── Music ───────────────────────────────────────────────────────────────


@app.websocket("/api/music")
async def music(ws: WebSocket, game_id: str = "", token: str = "") -> None:
    """Binary PCM out, `{"location": ...}` in.

    The session lives here rather than in the browser because Lyria has no
    ephemeral-token support - the API key can never reach a client. The token
    arrives as a query parameter because a browser WebSocket cannot set
    headers; it is the same Firebase ID token the REST calls carry.
    """
    await ws.accept()
    st = get_store()
    try:
        user = await verify_ws(token)
        state = await st.get_state(user.uid, game_id)
        script = await st.get_script(user.uid, game_id)
    except AppError as exc:
        await ws.close(code=1008, reason=exc.kind)
        return

    if state is None or script is None:
        await ws.close(code=1008, reason="unknown game")
        return
    if not await session_module.allowed_minutes(st, user.uid):
        await ws.send_text(json.dumps({"mode": "off", "reason": "daily_limit"}))
        await ws.close()
        return

    session = session_module.MusicSession(
        ws, state, script, store=st, assets=get_assets(), uid=user.uid
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("music session for %s ended badly", game_id)
    finally:
        with suppress(RuntimeError):
            await ws.close()


# ── Media ───────────────────────────────────────────────────────────────


@app.get("/api/media/asset/{key}", include_in_schema=False)
async def asset(key: str) -> Response:
    """Generated images, when they are held in this process rather than in GCS."""
    found = await get_assets().get(key)
    if found is None:
        raise AppError("network", f"unknown asset {key}", status_code=404)
    data, content_type = found
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/api/media/placeholder/{palette}/{seed}.svg", include_in_schema=False)
def placeholder(palette: str, seed: str) -> Response:
    if palette not in PALETTES:
        raise AppError("network", f"unknown palette {palette}", status_code=404)
    return Response(
        content=placeholder_svg(seed, palette),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ── Dev ─────────────────────────────────────────────────────────────────


class ForceErrorRequest(BaseModel):
    kind: ErrorKind | None


@app.post("/api/dev/force-error", include_in_schema=False)
def force_error(req: ForceErrorRequest) -> dict[str, str | None]:
    """Arms the next game-creation or library call to fail, for the dev panel."""
    global _forced_error
    if settings.llm_mode != "mock":
        raise AppError("network", "dev endpoints are mock-mode only", status_code=404)
    _forced_error = req.kind
    return {"armed": _forced_error}
