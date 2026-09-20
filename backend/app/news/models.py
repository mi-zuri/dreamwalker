"""News domain models.

Three layers, and the distinction between them is what keeps the cost down:

* an `Article` is one item from one feed - free to collect;
* an `Event` is a cluster of articles about the same thing, scored - cheap,
  one batched model call for a whole region;
* a `Dossier` is an `Event` researched properly, with full text read and a
  beat graph written - expensive, and therefore only ever built for an event
  somebody is actually about to play.

The pool holds the first two. The third is built on demand and then cached on
the event, so the second player to draw the same event pays nothing.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.game import Language, Region, SafetyClass
from app.models.plan import Certainty

#: How long a pooled event stays playable. Past this it reads as history.
POOL_TTL_DAYS = 7
#: Two events this close are the same story, for one player's "already played".
#: Deliberately strict: "another rocket landing" is supposed to pass as new.
DEDUP_COSINE = 0.93
#: Two articles this close *may* belong in one cluster - they also have to
#: share a distinctive word. Measured on 120 real Polish articles: the same
#: story scores 0.89-0.94, and two unrelated fatal road accidents score 0.89,
#: so cosine alone cannot separate them at any threshold. The plan's 0.82 was
#: an estimate made before that measurement and would merge whole genres.
CLUSTER_COSINE = 0.88
#: Articles further apart in time than this are never clustered together.
CLUSTER_WINDOW_HOURS = 72
#: A played event only blocks a new one inside this window either side.
DEDUP_WINDOW_DAYS = 14


def now() -> datetime:
    return datetime.now(UTC)


class Article(BaseModel):
    url: str
    canonical_url: str
    title: str
    summary: str = ""
    published_at: datetime
    source: str
    language: Language
    image_url: str = ""
    image_credit: str = ""
    #: Fetched lazily during enrichment, never during collection.
    body: str = ""


class Photo(BaseModel):
    """A press photo, kept with everything needed to credit it."""

    url: str
    source_url: str
    credit: str
    #: Set once it has been copied into our own bucket.
    stored_url: str = ""
    #: False when the vision check refused it.
    safe: bool = True
    caption: str = ""


class Fact(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)
    certainty: Certainty = "high"


class Person(BaseModel):
    name: str
    role: str = ""
    #: Private individuals are anonymized before they ever reach a prompt.
    public_figure: bool = False


class Dossier(BaseModel):
    """What actually happened, in the source language, with citations.

    Stored in the language it was reported in. The scene stage adapts it to
    the player's language inside a call it was making anyway, so there is no
    separate translation step and no extra cost.
    """

    what: str
    where: str
    when: str
    who: list[Person] = Field(default_factory=list)
    timeline: list[Fact] = Field(default_factory=list)
    uncertain: list[Fact] = Field(default_factory=list)
    language: Language = "en"
    #: True when no full text could be fetched and this is summary-only.
    thin: bool = False


class Scores(BaseModel):
    """Why this event is in the pool, and whether it can be played at all."""

    importance: float = 0.0
    interest: float = 0.0
    playability: float = 0.0
    safety_class: SafetyClass = "allowed"
    #: One sentence the safety stage can show the player before they start.
    content_note: str = ""
    #: Roles the event could plausibly contain, gating the style card.
    roles: list[str] = Field(default_factory=list)
    reason: str = ""

    @property
    def rank(self) -> float:
        """Playability dominates: an important event nobody can act in is not a game."""
        return self.playability * 0.5 + self.importance * 0.3 + self.interest * 0.2


class Event(BaseModel):
    id: str
    region: Region
    title: str
    summary: str
    language: Language
    first_seen: datetime = Field(default_factory=now)
    published_at: datetime = Field(default_factory=now)
    articles: list[Article] = Field(default_factory=list)
    #: Mean of the cluster's article embeddings; used for per-player dedup.
    embedding: list[float] = Field(default_factory=list)
    scores: Scores = Field(default_factory=Scores)
    #: Filled on first play and then reused by everyone after.
    dossier: Dossier | None = None
    photos: list[Photo] = Field(default_factory=list)
    #: Beats derived from the dossier - player-independent, so cached with it.
    beats: list[dict] = Field(default_factory=list)

    @property
    def canonical_urls(self) -> set[str]:
        return {a.canonical_url for a in self.articles}

    @property
    def age_days(self) -> float:
        return (now() - self.published_at).total_seconds() / 86400

    @property
    def playable(self) -> bool:
        return self.scores.safety_class != "blocked" and self.scores.playability >= 0.4

    def freshness(self) -> Literal["fresh", "aging", "stale"]:
        age = self.age_days
        return "fresh" if age < 2 else "aging" if age < POOL_TTL_DAYS else "stale"


class PlayedEvent(BaseModel):
    """What a player has already seen, for per-player dedup.

    Cluster ids drift between ingest runs, so they are never the only key -
    a shared canonical URL or a close embedding is what actually decides it.
    """

    event_id: str
    played_at: datetime = Field(default_factory=now)
    title: str = ""
    canonical_urls: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)


class PoolStatus(BaseModel):
    region: Region
    total: int = 0
    playable: int = 0
    refreshed_at: datetime | None = None

    @property
    def stale(self) -> bool:
        return self.refreshed_at is None
