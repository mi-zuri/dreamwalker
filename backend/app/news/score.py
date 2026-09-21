"""Deciding which events are worth playing, and which must not be.

Split deliberately in two.

**Importance is computed, not asked.** How many outlets carried it, how many
distinct outlets, and how recent it is - those are facts about the pool, and a
model asked to rate them would be guessing at something we can count. Counting
is free, deterministic and testable.

**Interest, playability and safety are asked**, once, for a whole region in a
single batched call, because they need judgement. Playability is the one that
does the most work: an event can be the most important thing that happened and
still be unplayable, because there is no place to stand in it and nothing for
a person to do.

Safety is classified here rather than at game start so that a blocked event
never enters the pool at all.
"""

import logging

from pydantic import BaseModel, Field

from app.llm.base import LLM
from app.models.game import SafetyClass
from app.news.cluster import sources_in
from app.news.models import Event, Scores
from app.pipeline.style_catalog import PROTAGONIST_ROLE

log = logging.getLogger(__name__)

STAGE = "score"

#: Scored in one call. Beyond this the prompt gets long enough that the model
#: starts losing track of which index it is on.
BATCH = 25

#: Events sent for judgement per refresh, highest computed importance first.
#: A Polish refresh clusters into about 160 events, most of them a single
#: article from a single outlet; scoring all of them would triple the bill to
#: rank things that were never going to reach the pool.
MAX_SCORED = 80

#: An event carried by this many distinct outlets is as important as counting
#: can tell us; more carriers do not make it more so.
DIVERSITY_CAP = 4
ARTICLES_CAP = 6

_ROLE_IDS = tuple(v.id for v in PROTAGONIST_ROLE)


class EventScoreDraft(BaseModel):
    index: int
    interest: float = 0.0
    playability: float = 0.0
    safety_class: SafetyClass = "allowed"
    #: One sentence, shown before the game starts. Only for `safe_mode`.
    content_note: str = ""
    #: Which roles this event could plausibly contain a person in.
    roles: list[str] = Field(default_factory=list)
    reason: str = ""


class ScoringDraft(BaseModel):
    events: list[EventScoreDraft] = Field(default_factory=list)


INSTRUCTIONS = f"""You are triaging real news events for a short interactive story game. \
The player will walk a small map of three to five places connected to the event, meet \
people, and choose what to do. A game lasts two to ten minutes.

Score each numbered event. Answer in English; nothing you write here is shown to a \
player except `content_note`.

- `interest` 0.0-1.0: would someone want to spend ten minutes inside this? A council \
budget vote is important and dull. A rescue, a discovery, a confrontation, a journey \
is not.
- `playability` 0.0-1.0: is there a concrete place, identifiable people doing things, \
a sequence of actions, and a clear outcome? Score below 0.3 for opinion pieces, market \
reports, rolling live commentary, league tables, weather summaries, and anything whose \
content is a number changing.
- `safety_class`:
  - `blocked` - do not make a game of this at all. Ongoing investigations into missing \
or unidentified people; crimes against children; hostage situations still in progress; \
private matters of private people; anything where a player acting it out would be \
intruding on someone's grief or privacy; celebrity personal lives.
  - `safe_mode` - real people were hurt or killed, and it can be played only with \
restraint: disasters, attacks, crashes, war. The player must be a rescuer, witness, \
official, journalist or volunteer, never a perpetrator.
  - `allowed` - everything else: politics, sport, science, space, business, culture, \
protests and incidents without casualties.
- `content_note`: for `safe_mode` only, one sentence in English naming what the player \
is about to encounter. Empty otherwise.
- `roles`: which of {list(_ROLE_IDS)} a person could plausibly be in this event. At \
least one. For `safe_mode` choose only from rescuer, witness, official, journalist, \
volunteer.
- `reason`: at most fifteen words, for the logs.

Return one entry per event, with the `index` you were given. Do not skip any."""


def importance(event: Event) -> float:
    """Counted, not judged: carriers, distinct outlets, and how recent it is."""
    diversity = min(sources_in(event), DIVERSITY_CAP) / DIVERSITY_CAP
    volume = min(len(event.articles), ARTICLES_CAP) / ARTICLES_CAP
    recency = max(0.0, 1.0 - event.age_days / 7)
    return round(diversity * 0.5 + volume * 0.25 + recency * 0.25, 3)


def _brief(events: list[Event]) -> str:
    lines = []
    for index, event in enumerate(events):
        outlets = ", ".join(sorted({a.source for a in event.articles}))
        lines.append(
            f"{index}. [{event.language}] {event.title}\n"
            f"   {event.summary[:320]}\n"
            f"   carried by: {outlets}"
        )
    return "\n".join(lines)


async def score(llm: LLM, events: list[Event]) -> list[Event]:
    """Fills in `event.scores` in place, and returns the same list.

    A batch that fails leaves its events at zero, which keeps them out of the
    pool without taking the rest of the region down with them.
    """
    for event in events:
        event.scores.importance = importance(event)

    # Judge the plausible ones. The rest keep their computed importance and a
    # playability of zero, which is what keeps them out of the pool.
    ranked = sorted(events, key=lambda e: e.scores.importance, reverse=True)[:MAX_SCORED]

    for start in range(0, len(ranked), BATCH):
        chunk = ranked[start : start + BATCH]
        try:
            draft = await llm.json(STAGE, _brief(chunk), ScoringDraft, system=INSTRUCTIONS)
        except Exception:
            log.exception("scoring batch at %d failed", start)
            continue
        _apply(chunk, draft)
    return events


def _apply(chunk: list[Event], draft: ScoringDraft) -> None:
    by_index = {d.index: d for d in draft.events}
    for index, event in enumerate(chunk):
        item = by_index.get(index)
        if item is None:
            # Unscored is not the same as unsafe, but it is not playable
            # either: nothing has vouched for it, so it stays out of the pool.
            log.info("event %s came back unscored", event.id)
            continue
        roles = [r for r in item.roles if r in _ROLE_IDS]
        event.scores = Scores(
            importance=event.scores.importance,
            interest=_clamp(item.interest),
            playability=_clamp(item.playability),
            safety_class=item.safety_class,
            content_note=item.content_note.strip(),
            roles=roles or ["witness"],
            reason=item.reason.strip()[:120],
        )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
