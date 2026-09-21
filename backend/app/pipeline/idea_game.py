"""Idea mode: a game built from one sentence the player typed.

There is no research step, no safety classification and no canon - the idea is
the brief, and the style card supplies everything the sentence does not say.
That is the whole difference from News mode; every stage after this file is
shared.
"""

from collections.abc import Awaitable, Callable

from app.llm.base import LLM
from app.models.game import NewGameRequest, Stage
from app.pipeline import live
from app.pipeline.style_card import HISTORY_DEPTH, sample_style_card
from app.storage.assets import AssetStore
from app.storage.base import GameStore

Progress = Callable[[Stage], Awaitable[None]]

#: What an empty idea box becomes. The menu only sends the player here when
#: they typed something, but an all-whitespace box is still possible.
DEFAULT_IDEA = {
    "pl": "ktoś wraca do miejsca, które pamięta inaczej niż ono wygląda",
    "en": "someone returns to a place they remember differently than it is",
}


async def build(
    llm: LLM,
    assets: AssetStore,
    *,
    game_id: str,
    req: NewGameRequest,
    uid: str,
    store: GameStore,
    progress: Progress,
) -> live.OpenedGame:
    idea = (req.idea or "").strip() or DEFAULT_IDEA[req.language]
    style = sample_style_card(recent=await store.recent_style_cards(uid, HISTORY_DEPTH))

    return await live.open_game(
        llm,
        assets,
        game_id=game_id,
        req=req,
        style=style,
        brief=live.idea_brief(idea, req.language),
        progress=progress,
        mode="idea",
    )
