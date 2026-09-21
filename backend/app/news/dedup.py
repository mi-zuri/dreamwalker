"""Has this player already played this?

Per player only. Two strangers drawing the same event is not a problem worth
solving, and solving it would mean one player's variety depended on everyone
else's - which for a game with a handful of players is worse than the disease.

Two tests, either of which is enough:

* **a shared canonical URL.** Exact, cheap, and catches the common case of
  the same story being re-clustered under a different id on a later run.
* **a close embedding inside a two-week window.** Cluster ids drift between
  ingest runs, so the id alone is never trusted.

The 0.93 threshold is deliberately strict. "Another rocket landing" and
"another brawl in the Sejm" are supposed to pass as new events; only something
that is recognisably the same story should be blocked.
"""

import logging

from app.news.cluster import cosine
from app.news.models import (
    DEDUP_COSINE,
    DEDUP_WINDOW_DAYS,
    Event,
    PlayedEvent,
    now,
)

log = logging.getLogger(__name__)


def already_played(
    event: Event,
    history: list[PlayedEvent],
    *,
    threshold: float = DEDUP_COSINE,
    window_days: int = DEDUP_WINDOW_DAYS,
) -> bool:
    urls = event.canonical_urls
    for played in history:
        if played.event_id == event.id:
            return True
        if urls & set(played.canonical_urls):
            return True
        age_days = abs((played.played_at - now()).total_seconds()) / 86400
        if age_days > window_days:
            continue
        if cosine(event.embedding, played.embedding) >= threshold:
            log.info("event %s reads as already played (%s)", event.id, played.event_id)
            return True
    return False


def unplayed(events: list[Event], history: list[PlayedEvent], **kwargs) -> list[Event]:
    return [e for e in events if not already_played(e, history, **kwargs)]


def record(event: Event) -> PlayedEvent:
    return PlayedEvent(
        event_id=event.id,
        title=event.title,
        canonical_urls=sorted(event.canonical_urls),
        embedding=event.embedding,
    )
