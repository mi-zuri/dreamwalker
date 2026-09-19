"""Stage sequencing and game creation.

Phase 2 only ever runs the mock path: a new game is a fixture clone, so it is
ready the moment `start_game` returns and the progress stream exists purely to
drive the loading screen. The seam is the point - Phase 4 swaps `build_game`
for the real pipeline without the API contract moving.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import get_args

from app.errors import AppError
from app.llm.mock import build_game
from app.models.game import GameState, NewGameRequest, Stage
from app.models.script import GameScript
from app.settings import settings
from app.storage.base import GameStore

#: Coarse labels only - the UI never learns what a stage actually does.
STAGE_SCRIPT: tuple[tuple[Stage, float], ...] = (
    ("story", 0.9),
    ("map", 0.7),
    ("images", 1.1),
    ("music", 0.6),
    ("finishing", 0.5),
)

assert [s for s, _ in STAGE_SCRIPT] == list(get_args(Stage)), "stage script must cover every stage"


async def check_budget(store: GameStore) -> None:
    """Hard month-to-date cap, checked before anything can spend.

    This is the only spend limit in the system: there is deliberately no
    per-user or per-day game cap, and image generation is uncapped.
    """
    spend = await store.month_spend()
    if spend >= settings.monthly_budget_usd:
        raise AppError(
            "budget_exceeded",
            f"month-to-date spend ${spend:.2f} reached the ${settings.monthly_budget_usd:.2f} cap",
        )


async def start_game(store: GameStore, uid: str, req: NewGameRequest) -> GameState:
    await check_budget(store)

    game_id = uuid.uuid4().hex[:16]
    if settings.llm_mode == "mock":
        state, script = build_game(game_id, req)
    else:  # pragma: no cover - Phase 4
        raise AppError("generation_failed", "live generation is not wired up yet")

    if state.safety_class == "blocked":
        raise AppError("blocked_event", "this event is not playable")

    await _persist(store, uid, state, script)
    return state


async def _persist(store: GameStore, uid: str, state: GameState, script: GameScript) -> None:
    await asyncio.gather(store.put_state(uid, state), store.put_script(uid, script))


async def stream_progress() -> AsyncIterator[dict[str, str]]:
    """SSE events for the loading screen: `stage` several times, then `ready`."""
    for stage, delay in STAGE_SCRIPT:
        yield {"event": "stage", "data": json.dumps({"stage": stage})}
        if settings.mock_stage_scale:
            await asyncio.sleep(delay * settings.mock_stage_scale)
    yield {"event": "ready", "data": json.dumps({"ready": True})}
