"""Building and playing a whole game offline, for the dimensions to grade.

Everything here is deliberately the *real* pipeline with the model swapped at
the bottom: `news_game.build` and `idea_game.build` do the planning, the map
generation and validation, the scene assembly and the ending exactly as they
do in production. An eval that stubbed those out would be measuring its own
fixtures.

Two details keep it offline and fast. Articles arrive with a `body` already
set, so full-text fetching finds nothing to fetch and never opens a socket;
and the pool is written straight into a `MemoryStore`, so no ingest runs.
"""

from collections.abc import Callable
from datetime import timedelta

from app.llm.base import LLM
from app.models.game import EndingComparison, GameState, NewGameRequest, Pos
from app.models.script import GameScript
from app.news.models import Article, Event, Scores, now
from app.pipeline import engine, idea_game, live, news_game
from app.pipeline.ending import write_ending
from app.storage.assets import MemoryAssets
from app.storage.memory import MemoryStore

#: A body long enough that `fetch_bodies` treats the article as already read.
_BODY = (
    "The scene on the ground was described consistently by several outlets "
    "through the afternoon, with officials confirming the sequence of events "
    "and witnesses adding detail that has not yet been independently checked. "
) * 4


def make_event(
    title: str, *, region: str = "world", language: str = "en", ident: str = ""
) -> Event:
    """One clustered event, shaped the way the ingest job leaves them."""
    articles = [
        Article(
            url=f"https://outlet{i}.example/{abs(hash(title)) % 99999}",
            canonical_url=f"https://outlet{i}.example/{abs(hash(title)) % 99999}",
            title=title,
            summary=f"{title}. Carried by several outlets through the afternoon.",
            body=_BODY,
            published_at=now() - timedelta(hours=i + 1),
            source=f"outlet{i}",
            language=language,
        )
        for i in range(3)
    ]
    return Event(
        id=ident or f"ev-{abs(hash(title)) % 99999}",
        region=region,
        title=title,
        summary=articles[0].summary,
        language=language,
        articles=articles,
        embedding=[1.0, 0.0],
        scores=Scores(importance=0.8, interest=0.8, playability=0.8, roles=["witness"]),
    )


async def _quiet(_stage: str) -> None:
    """Progress callback for a caller that is not watching a loading screen."""


def request(**overrides) -> NewGameRequest:
    return NewGameRequest(
        **{
            "mode": "idea",
            "idea": "a lighthouse keeper finds the lamp already lit",
            "story_language": "en",
            "ui_language": "en",
            **overrides,
        }
    )


async def open_idea(llm: LLM, **overrides) -> live.OpenedGame:
    store = MemoryStore()
    opened = await idea_game.build(
        llm,
        MemoryAssets(),
        game_id="eval-idea",
        req=request(**overrides),
        uid="eval-player",
        store=store,
        progress=_quiet,
    )
    await live.fill_scenes(llm, opened.script, opened.plan, opened.style)
    return opened


async def open_news(llm: LLM, event: Event, **overrides) -> live.OpenedGame:
    """Score the event the way ingest would, pool it, then play it."""
    from app.news.score import score

    await score(llm, [event])
    store = MemoryStore()
    await store.put_pool(event.region, [event])

    req = request(**{"mode": "news", "region": event.region, **overrides})
    opened = await news_game.build(
        llm,
        MemoryAssets(),
        game_id="eval-news",
        req=req,
        uid="eval-player",
        store=store,
        progress=_quiet,
    )
    await live.fill_scenes(
        llm, opened.script, opened.plan, opened.style, safety_class=opened.safety_class
    )
    return opened


# ── walking a built game ────────────────────────────────────────────────

#: Picks a choice id from the ones on offer, given whether each is on canon.
Strategy = Callable[[int, list[tuple[str, bool]]], str]


def follow_canon(_turn: int, options: list[tuple[str, bool]]) -> str:
    return next((cid for cid, canon in options if canon), options[0][0])


def leave_canon(_turn: int, options: list[tuple[str, bool]]) -> str:
    return next((cid for cid, canon in options if not canon), options[0][0])


def alternate(turn: int, options: list[tuple[str, bool]]) -> str:
    return follow_canon(turn, options) if turn % 2 == 0 else leave_canon(turn, options)


def only_last(count: int) -> Strategy:
    """On canon for the final beat only - the hardest one to hit by accident."""

    def pick(turn: int, options: list[tuple[str, bool]]) -> str:
        return follow_canon(turn, options) if turn == count - 1 else leave_canon(turn, options)

    return pick


def only_first(_count: int) -> Strategy:
    def pick(turn: int, options: list[tuple[str, bool]]) -> str:
        return follow_canon(turn, options) if turn == 0 else leave_canon(turn, options)

    return pick


def destination_positions(state: GameState) -> list[tuple[str, Pos]]:
    """Every destination tile, in the order the plan wanted them visited."""
    found: dict[str, Pos] = {}
    for y, row in enumerate(state.map.tiles):
        for x, char in enumerate(row):
            if char not in found and any(d.key == char for d in state.map.destinations):
                found[char] = Pos(x=x, y=y)
    return [(d.key, found[d.key]) for d in state.map.destinations if d.key in found]


def play(state: GameState, script: GameScript, strategy: Strategy) -> int:
    """Walk every destination in order and answer each scene. Returns turns taken.

    Locked destinations are retried after the rest, because a door opens only
    once the place that unlocks it has been finished - which is exactly the
    situation the engine is supposed to handle, so the walk is not allowed to
    cheat its way past it.
    """
    pending = destination_positions(state)
    turn = 0
    stuck = 0
    while pending and stuck <= len(pending):
        key, pos = pending.pop(0)
        engine.apply_move(state, script, pos)
        if (state.player_pos.x, state.player_pos.y) != (pos.x, pos.y):
            pending.append((key, pos))
            stuck += 1
            continue
        stuck = 0
        if not state.choices:
            continue
        options = [
            (c.id, bool(o.on_canon) if (o := script.outcomes.get(c.id)) else False)
            for c in state.choices
        ]
        if state.open_question is not None:
            engine.apply_answer(state, script, "I say what I came to say.")
        engine.apply_choice(state, script, strategy(turn, options))
        turn += 1
    return turn


async def played_ending(
    llm: LLM, opened: live.OpenedGame, strategy: Strategy
) -> tuple[GameState, EndingComparison]:
    """A complete run: walk it with `strategy`, then write its ending."""
    state, script = opened.state, opened.script
    play(state, script, strategy)
    ending = await write_ending(llm, state=state, script=script, plan=opened.plan)
    return state, ending
