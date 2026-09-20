"""News mode: a game built from something that actually happened.

The difference from Idea mode is entirely in front of `live.open_game`. Where
Idea mode has a sentence the player typed, News mode has to find an event this
player has not seen, make sure it is one we are willing to dramatize at all,
read it properly, and hand the plan stage a factual brief plus a beat graph
the player's run will be measured against. After that the two modes are the
same code.

Three things here are load-bearing and easy to miss:

* **the pool refreshes lazily**, so a region that is already deep and recent
  costs nothing - this is what keeps an idle month at zero;
* **enrichment is cached on the event**, so the second player to draw a story
  pays nothing for the dossier the first one paid for;
* **the canon beats come from the dossier, not the plan.** The plan decides
  where the player walks; what actually happened is not its to invent.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.errors import AppError
from app.llm.base import LLM
from app.models.game import Language, NewGameRequest, Region, Stage
from app.models.plan import Beat
from app.news import ingest, pool
from app.news.dedup import record
from app.news.enrich import enrich
from app.news.models import Dossier, Event, PoolStatus, now
from app.pipeline import live
from app.pipeline.photos import best_for_opening
from app.pipeline.style_card import HISTORY_DEPTH, sample_style_card
from app.settings import settings
from app.storage.assets import AssetStore
from app.storage.base import GameStore

log = logging.getLogger(__name__)

Progress = Callable[[Stage], Awaitable[None]]

#: Shown for the whole run, in the player's UI language.
SOURCE_NOTE: dict[Language, str] = {
    "pl": "Na podstawie prawdziwych wydarzeń. Fabuła jest zmyślona.",
    "en": "Based on real events. The story around them is invented.",
}

#: Said when the pool has nothing this player has not already played.
EMPTY: dict[Language, str] = {
    "pl": "Na razie nie ma dla ciebie nowych wydarzeń. Zajrzyj później.",
    "en": "There is nothing new for you right now. Come back later.",
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
    region: Region = req.region or "world"

    event = await pick(llm, store, region, uid)
    if event is None:
        raise AppError("pool_empty", EMPTY[req.ui_language])

    await enrich(llm, event, assets)
    await store.put_event(region, event)

    if event.dossier is None:  # pragma: no cover - enrich always sets one
        raise AppError("generation_failed", "the dossier could not be built")

    safety = event.scores.safety_class
    style = sample_style_card(
        safety_class=safety,
        recent=await store.recent_style_cards(uid, HISTORY_DEPTH),
        allowed_roles=set(event.scores.roles) or None,
    )

    opened = await live.open_game(
        llm,
        assets,
        game_id=game_id,
        req=req,
        style=style,
        brief=news_brief(event),
        progress=progress,
        safety_class=safety,
        content_note=event.scores.content_note,
        source_note=SOURCE_NOTE[req.story_language],
        mode="news",
        canon=canon_beats(event),
        opening_image=best_for_opening(event.photos),
        photos=tuple(event.photos),
    )

    # Recorded now rather than at the ending: a player who abandons a run has
    # still seen the event, and should not be handed it again tomorrow.
    await store.mark_played(uid, record(event))
    return opened


async def pick(llm: LLM, store: GameStore, region: Region, uid: str) -> Event | None:
    """Draw something this player has not seen, refreshing the pool if needed.

    A refresh takes most of a minute - collecting six feeds, clustering two
    hundred articles and scoring eighty events - and putting that in front of
    the player is only justified when there is nothing to play without it. So
    a pool that can still serve is refreshed *behind* them instead.
    """
    status = await store.pool_status(region)
    if status.playable and ingest.wants_refresh(status):
        _refresh_behind(store, region)
    else:
        status = await ingest.ensure_pool(llm, store, region)

    history = await store.played_events(uid)
    events = await store.get_pool(region)

    chosen = pool.choose(events, history)
    if chosen is not None or not events:
        return chosen

    # The pool is not empty; this player has exhausted it. A refresh is the
    # only thing that can help - but only if the pool is old enough that one
    # might actually find something, or every retry becomes an ingest.
    if not _worth_retrying(status):
        log.info("%s pool exhausted for one player and too fresh to re-ingest", region)
        return None

    log.info("%s pool exhausted for one player; refreshing", region)
    await ingest.refresh(llm, store, region)
    return pool.choose(await store.get_pool(region), history)


#: In-flight background refreshes, so two players arriving together do not
#: each start one.
_refreshing: set[str] = set()


def _refresh_behind(store: GameStore, region: Region) -> None:
    """Refresh without the player waiting, on its own model and its own bill."""
    if region in _refreshing:
        return
    _refreshing.add(region)

    async def run() -> None:
        from app.llm import make_llm

        background = make_llm()
        try:
            await ingest.refresh(background, store, region)
            await store.add_spend(background.usage.usd)
        except Exception:
            log.exception("background refresh of %s failed", region)
        finally:
            _refreshing.discard(region)

    task = asyncio.create_task(run())
    task.add_done_callback(lambda _: None)


def _worth_retrying(status: PoolStatus) -> bool:
    if not settings.news_ingest_enabled:
        return False
    if status.refreshed_at is None:
        return True
    minutes = (now() - status.refreshed_at).total_seconds() / 60
    return minutes >= settings.pool_retry_minutes


def canon_beats(event: Event) -> list[Beat]:
    """The beat graph written during enrichment, with its citations attached."""
    sources = [a.canonical_url for a in event.articles[:3]]
    return [
        Beat(
            id=f"canon-{index + 1}",
            order=index,
            title=str(raw.get("title", "")).strip(),
            summary=str(raw.get("summary", "")).strip(),
            location_ref="",
            certainty="high",
            sources=sources,
        )
        for index, raw in enumerate(event.beats)
        if str(raw.get("title", "")).strip()
    ]


def news_brief(event: Event) -> str:
    """The dossier as a brief, in the language it was reported in.

    Deliberately not translated. The scene stage is told which language to
    write in and adapts the dossier inside a call it was making anyway, so
    there is no translation stage and no extra cost.
    """
    dossier: Dossier = event.dossier  # type: ignore[assignment]
    beats = canon_beats(event)

    lines = [
        "THIS IS A REAL EVENT. Everything below is reported fact.",
        "",
        f"WHAT HAPPENED: {dossier.what}",
        f"WHERE: {dossier.where}",
        f"WHEN: {dossier.when}",
    ]

    if dossier.who:
        lines += ["", "PEOPLE:"]
        for person in dossier.who:
            name = person.name or "(not named - a private individual)"
            lines.append(f"- {name}: {person.role}")

    if dossier.timeline:
        lines += ["", "TIMELINE:"]
        lines += [f"- [{fact.certainty}] {fact.text}" for fact in dossier.timeline]

    if dossier.uncertain:
        lines += ["", "NOT CONFIRMED - treat as rumour inside the story, never as fact:"]
        lines += [f"- {fact.text}" for fact in dossier.uncertain]

    lines += ["", "THE BEATS THE PLAYER WILL BE COMPARED AGAINST, IN ORDER:"]
    for index, beat in enumerate(beats):
        place = str(event.beats[index].get("place", "")).strip()
        where = f" (at {place})" if place else ""
        lines.append(f"{index}. {beat.title}{where}: {beat.summary}")

    lines += ["", _RULES]
    if dossier.thin:
        lines.append(
            "The reporting is thin, so keep the story close to what little is known "
            "rather than filling the gaps with invention."
        )
    return "\n".join(lines)


#: The pairing rule and the invention rule, which are the two ways a News game
#: goes wrong: beats that do not line up with locations, and facts that were
#: made up. Both are stated where the brief ends, so they read last.
_RULES = (
    "Build the story around this event. Give it one location per beat above, in the "
    "same order, named as the reports name them, and return one entry in `beats` per "
    "beat above with the `location_index` you gave it - the same count, the same "
    "order.\n"
    "Invent the small human detail; invent nothing about the facts. Do not name anyone "
    "the dossier does not name. Do not give the player the power to change what "
    "happened - they act inside it."
)
