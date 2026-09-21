"""The event pool: what is currently playable in a region.

The pool accumulates. A refresh adds what it found and expires what has aged
out; it never replaces, so a run that fails - or a source that goes down -
leaves yesterday's pool exactly where it was. That is the property that makes
refreshing on demand safe: the worst outcome of a bad refresh is a slightly
staler pool, never an empty one.

Two ways out of it. `shortlist` is what the player chooses from, ordered by
importance. `choose` is the machine picking one for them - weighted-random
over the top candidates rather than "take the best", because always serving
the highest-ranked event would mean every player in a day plays the same
thing, and would make the pool's depth pointless.
"""

import logging
from random import Random

from app.models.game import Region
from app.news.dedup import unplayed
from app.news.models import POOL_TTL_DAYS, Event, PlayedEvent

log = logging.getLogger(__name__)

#: How many of the top-ranked events a player's pick is drawn from.
TOP_K = 12
#: Events at or below this are not offered at all.
MIN_RANK = 0.35
#: A fresh event is worth this much more than an aging one when picking.
FRESH_BONUS = 1.6
#: How strongly the draw favours variety of subject over rank.
CATEGORY_PENALTY = 0.55


def merge(existing: list[Event], found: list[Event]) -> list[Event]:
    """Add what is new, keep what is already enriched, drop what has expired.

    An event that has already been played once carries a dossier and photos
    that cost real money, so a re-ingest must never overwrite it with the
    freshly collected version of itself.
    """
    by_id = {event.id: event for event in existing}
    by_url: dict[str, Event] = {url: event for event in existing for url in event.canonical_urls}

    for event in found:
        held = by_id.get(event.id) or next(
            (by_url[u] for u in event.canonical_urls if u in by_url), None
        )
        if held is None:
            by_id[event.id] = event
            for url in event.canonical_urls:
                by_url[url] = event
            continue

        # Same story, seen again: take the new articles and the new scores,
        # keep the expensive half.
        known = held.canonical_urls
        held.articles.extend(a for a in event.articles if a.canonical_url not in known)
        held.scores = event.scores
        held.embedding = event.embedding or held.embedding

    alive = [e for e in by_id.values() if e.age_days <= POOL_TTL_DAYS]
    dropped = len(by_id) - len(alive)
    if dropped:
        log.info("expired %d events past %d days", dropped, POOL_TTL_DAYS)
    return sorted(alive, key=lambda e: e.scores.rank, reverse=True)


def playable(events: list[Event], *, min_rank: float = MIN_RANK) -> list[Event]:
    return [e for e in events if e.playable and e.scores.rank >= min_rank]


def _category(event: Event) -> str:
    """A crude subject key, so a draw does not return five politics stories.

    The scorer does not emit a category and asking for one would be another
    field to get wrong; the lead outlet plus the top role is a good enough
    proxy for "more of the same".
    """
    return f"{event.scores.roles[0] if event.scores.roles else '-'}"


#: How many stories the player is offered to choose between.
SHORTLIST = 7


def shortlist(
    events: list[Event],
    history: list[PlayedEvent],
    *,
    limit: int = SHORTLIST,
) -> list[Event]:
    """The most important playable events this player has not already seen.

    Ordered by `importance` rather than by `rank`. `rank` exists to answer
    "which of these makes the best game", which is the right question when the
    machine picks; the player is picking now, and the useful order for them is
    what actually mattered. Playability still filters - an event nobody can
    act inside is not a game however large it was - it just stops deciding the
    order. Ties fall back to rank.
    """
    return sorted(
        unplayed(playable(events), history),
        key=lambda e: (e.scores.importance, e.scores.rank),
        reverse=True,
    )[:limit]


def choose(
    events: list[Event],
    history: list[PlayedEvent],
    *,
    rng: Random | None = None,
    top_k: int = TOP_K,
) -> Event | None:
    """One event for one player, or `None` when the pool has nothing left."""
    rng = rng or Random()
    candidates = unplayed(playable(events), history)[:top_k]
    if not candidates:
        return None

    seen: dict[str, int] = {}
    weights: list[float] = []
    for event in candidates:
        category = _category(event)
        repeats = seen.get(category, 0)
        seen[category] = repeats + 1
        weight = event.scores.rank
        weight *= FRESH_BONUS if event.freshness() == "fresh" else 1.0
        weight *= CATEGORY_PENALTY**repeats
        weights.append(max(weight, 0.01))

    return rng.choices(candidates, weights=weights, k=1)[0]


def describe(events: list[Event], region: Region) -> str:
    counts = {"fresh": 0, "aging": 0, "stale": 0}
    for event in playable(events):
        counts[event.freshness()] += 1
    return (
        f"{region}: {len(events)} events, {len(playable(events))} playable "
        f"({counts['fresh']} fresh, {counts['aging']} aging)"
    )
