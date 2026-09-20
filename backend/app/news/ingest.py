"""The ingest job.

There is no scheduler. The plan originally called for a Cloud Scheduler job
every 48 hours, which at roughly $0.30 a region a run is about $9 a month -
most of a 10 PLN budget, spent whether or not anybody played. So ingest runs
*lazily*: a News game checks whether the region's pool is thin or stale and
refreshes it first if it is. Nobody playing means nothing spent.

That is affordable because the expensive half was moved out. A refresh only
collects, clusters and scores - free feeds, a fraction of a cent of embeddings
and one batched scoring call, well under a cent for a region. Reading articles
and writing a beat graph happens per *event*, on the way into a game, and is
cached on the event afterwards.
"""

import asyncio
import logging

from app.llm.base import LLM
from app.models.game import Region
from app.news import pool as pool_module
from app.news.cluster import cluster
from app.news.models import Article, PoolStatus, now
from app.news.normalize import dedup
from app.news.score import score
from app.news.sources.base import NewsSource
from app.news.sources.rss import sources_for
from app.news.sources.wikipedia import WikipediaCurrentEvents
from app.settings import settings
from app.storage.base import GameStore

log = logging.getLogger(__name__)


def sources(region: Region) -> list[NewsSource]:
    """Wikipedia first for World: it is the only importance-filtered source."""
    feeds: list[NewsSource] = list(sources_for(region))
    if region == "world":
        return [WikipediaCurrentEvents(), *feeds]
    return feeds


async def collect(region: Region, which: list[NewsSource] | None = None) -> list[Article]:
    """Everything every source is offering, deduped by canonical URL.

    A source that fails is skipped and logged. Losing one feed should cost a
    little pool depth, not a region.
    """
    chosen = which if which is not None else sources(region)
    results = await asyncio.gather(*(s.fetch() for s in chosen), return_exceptions=True)

    articles: list[Article] = []
    failed = 0
    for source, result in zip(chosen, results, strict=True):
        if isinstance(result, BaseException):
            failed += 1
            log.warning("source %s failed: %s", source.name, result)
            continue
        articles.extend(result)

    merged = dedup(articles)
    log.info(
        "collected %d articles (%d after dedup) from %d sources, %d failed",
        len(articles),
        len(merged),
        len(chosen),
        failed,
    )
    return merged


async def refresh(
    llm: LLM,
    store: GameStore,
    region: Region,
    *,
    which: list[NewsSource] | None = None,
) -> PoolStatus:
    """Collect, cluster, score, merge into the pool. Never shrinks it on failure."""
    articles = await collect(region, which)
    if not articles:
        log.warning("no articles for %s; leaving the pool as it is", region)
        return await store.pool_status(region)

    events = await cluster(llm, articles, region)
    await score(llm, events)

    merged = pool_module.merge(await store.get_pool(region), events)
    await store.put_pool(region, merged)
    log.info("refreshed %s - %s", region, pool_module.describe(merged, region))
    return await store.pool_status(region)


async def ensure_pool(llm: LLM, store: GameStore, region: Region) -> PoolStatus:
    """Refresh only when the pool cannot serve. This is the whole cost control.

    A pool that is deep enough and recent enough is served as it stands, so a
    second player in the same hour costs nothing beyond their own game.
    """
    status = await store.pool_status(region)
    if not _needs_refresh(status):
        return status
    return await refresh(llm, store, region)


def _needs_refresh(status: PoolStatus) -> bool:
    if status.refreshed_at is None:
        return True
    if status.playable < settings.pool_min_playable:
        return True
    age_hours = (now() - status.refreshed_at).total_seconds() / 3600
    return age_hours >= settings.pool_max_age_hours
