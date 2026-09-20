"""Grouping articles into events.

Six Polish feeds covering one afternoon produce the same story four or five
times over. Clustering is what turns "238 articles" into "about forty things
that happened", and it is also what gives each event its source diversity -
which is the strongest available signal that something actually mattered.

Greedy single-pass agglomeration, newest first. Not because it is the best
clustering algorithm but because it is the one whose failure mode is right:
an article that matches nothing starts its own cluster, so the worst case is
a duplicate event rather than a lost one.
"""

import hashlib
import logging
import re
from collections import Counter
from datetime import timedelta

from app.llm.base import LLM
from app.models.game import Region
from app.news.models import (
    CLUSTER_COSINE,
    CLUSTER_WINDOW_HOURS,
    Article,
    Event,
)

log = logging.getLogger(__name__)

STAGE = "cluster"


def cosine(a: list[float], b: list[float]) -> float:
    """A plain dot product: every vector in the system arrives normalized."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    width = len(vectors[0])
    total = [0.0] * width
    for vector in vectors:
        for index, value in enumerate(vector):
            total[index] += value
    norm = sum(v * v for v in total) ** 0.5
    return [v / norm for v in total] if norm else total


_TOKEN = re.compile(r"[\w\u00c0-\u017f]{5,}", re.UNICODE)

#: A token appearing in more than this share of the batch is a genre word -
#: "tragedia", "kierowca", "minister" - not a name, a place or a number.
#: Measured: at 0.06 two unrelated fatal crashes still merged on "kierowca".
COMMON_SHARE = 0.02
#: ...but in a tiny batch a share is meaningless, so never allow more than this.
COMMON_FLOOR = 2


def distinctive(articles: list[Article]) -> list[frozenset[str]]:
    """The rare words in each article, by document frequency over the batch.

    This is what stops two different fatal road accidents being merged. They
    share every word that makes them *sound* alike - tragedia, nie zyje,
    kierowca - and share none of the words that identify them: Kartuzy,
    Siepraw, the make of car, the number of the road. Rare words are the ones
    that carry identity, and document frequency finds them without a
    dictionary, in any language.
    """
    tokens = [frozenset(_TOKEN.findall(f"{a.title} {a.summary}".lower())) for a in articles]
    frequency = Counter(token for document in tokens for token in document)
    ceiling = max(COMMON_FLOOR, int(len(articles) * COMMON_SHARE))
    return [frozenset(t for t in document if frequency[t] <= ceiling) for document in tokens]


def embed_text(article: Article) -> str:
    """Title plus the first part of the summary. The lede carries the story."""
    return f"{article.title}. {article.summary}"[:600]


def event_id(articles: list[Article]) -> str:
    """Stable for the same set of sources, so a re-ingest does not churn ids.

    Cluster membership does drift between runs, though, which is exactly why
    per-player dedup never trusts this id on its own.
    """
    seed = "|".join(sorted(a.canonical_url for a in articles))
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


async def cluster(
    llm: LLM,
    articles: list[Article],
    region: Region,
    *,
    threshold: float = CLUSTER_COSINE,
    window_hours: int = CLUSTER_WINDOW_HOURS,
) -> list[Event]:
    if not articles:
        return []

    ordered = sorted(articles, key=lambda a: a.published_at, reverse=True)
    vectors = await llm.embed(STAGE, [embed_text(a) for a in ordered])
    rare = distinctive(ordered)
    window = timedelta(hours=window_hours)

    groups: list[list[int]] = []
    centres: list[list[float]] = []
    shared: list[frozenset[str]] = []

    for index, article in enumerate(ordered):
        best = -1
        best_score = threshold
        for group_index, group in enumerate(groups):
            leader = ordered[group[0]]
            if abs(leader.published_at - article.published_at) > window:
                continue
            # Both tests, not either: close enough *and* about the same thing.
            if not (rare[index] & shared[group_index]):
                continue
            score = cosine(centres[group_index], vectors[index])
            if score >= best_score:
                best, best_score = group_index, score

        if best < 0:
            groups.append([index])
            centres.append(vectors[index])
            shared.append(rare[index])
        else:
            groups[best].append(index)
            centres[best] = mean([vectors[i] for i in groups[best]])
            shared[best] = shared[best] | rare[index]

    events = [
        _event([ordered[i] for i in group], centres[position], region)
        for position, group in enumerate(groups)
    ]
    log.info("clustered %d articles into %d events for %s", len(articles), len(events), region)
    return events


def _event(members: list[Article], centre: list[float], region: Region) -> Event:
    # The earliest article names the event; later ones are usually follow-ups
    # with headlines that only make sense if you already read the first.
    members = sorted(members, key=lambda a: a.published_at)
    lead = members[0]
    return Event(
        id=event_id(members),
        region=region,
        title=lead.title,
        summary=max((a.summary for a in members), key=len, default=""),
        language=lead.language,
        published_at=lead.published_at,
        articles=members,
        embedding=centre,
    )


def sources_in(event: Event) -> int:
    return len({a.source for a in event.articles})
