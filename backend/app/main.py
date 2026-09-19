"""HTTP surface.

The whole game loop is server-authoritative: the client animates movement and
renders scenes, but every transition goes through `app.pipeline.engine` here,
against the server's own copy of the state.
"""

from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.auth import CurrentUser
from app.errors import AppError, ErrorKind, app_error_handler
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
from app.pipeline import engine, orchestrator
from app.settings import settings
from app.storage import get_store
from app.storage.base import GameStore

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
    state = await orchestrator.start_game(st, user.uid, req)
    return NewGameResponse(game_id=state.game_id)


@app.get("/api/games/{game_id}/stream", response_model=StageEvent)
async def stream(game_id: str, user: CurrentUser, st: GameStore = Store) -> EventSourceResponse:
    """Coarse loading progress. The game itself is already persisted."""
    await _load(st, user.uid, game_id)
    return EventSourceResponse(orchestrator.stream_progress())


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
        played_at = datetime.now(UTC).isoformat()
        await st.save_finished(
            user.uid,
            engine.to_saved(state, script, played_at),
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


# ── Media ───────────────────────────────────────────────────────────────


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
