"""RSS feeds.

Fetched with `httpx` and only then handed to `feedparser`, rather than letting
feedparser do its own networking. That is what makes every source recordable:
the tests replay real captured responses through `respx` and never touch the
network.

Feed choice is deliberate and was measured rather than guessed. Category feeds
carry fewer items per hour than a firehose and therefore reach *further back
in time* with the same fifty entries - `polsatnews.pl/rss/polska.xml` spans
about 54 hours where `wiadomosci.onet.pl/.feed` spans about five. For a pool
that refreshes on demand rather than on a schedule, depth beats freshness.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import NamedTuple

import feedparser
import httpx

from app.models.game import Language, Region
from app.news.models import Article
from app.news.normalize import to_article

log = logging.getLogger(__name__)

USER_AGENT = "dreamwalker/0.1 (student project; contact via repository)"
TIMEOUT = httpx.Timeout(12.0, connect=6.0)


class Feed(NamedTuple):
    url: str
    source: str
    region: Region
    language: Language


#: Poland. No curated Polish equivalent of Wikipedia's current-events portal
#: exists (`pl.wikipedia.org` returns `missingtitle`), so this is category
#: feeds chosen for time depth.
PL_FEEDS: tuple[Feed, ...] = (
    Feed("https://www.polsatnews.pl/rss/polska.xml", "polsatnews", "pl", "pl"),
    Feed("https://www.rmf24.pl/fakty/polska/feed", "rmf24", "pl", "pl"),
    Feed("https://www.rmf24.pl/fakty/feed", "rmf24", "pl", "pl"),
    Feed("https://www.polsatnews.pl/rss/wszystkie.xml", "polsatnews", "pl", "pl"),
    Feed("https://wiadomosci.onet.pl/.feed", "onet", "pl", "pl"),
    Feed("https://tvn24.pl/najnowsze.xml", "tvn24", "pl", "pl"),
)

#: World. `feeds.reuters.com` is dead - it fails to connect, and is not here
#: for that reason rather than by oversight.
WORLD_FEEDS: tuple[Feed, ...] = (
    Feed("https://feeds.bbci.co.uk/news/world/rss.xml", "bbc", "world", "en"),
    Feed("https://www.theguardian.com/world/rss", "guardian", "world", "en"),
    Feed("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "nytimes", "world", "en"),
)

#: NYT is summary-only on ToS grounds; nothing ever fetches its article bodies.
SUMMARY_ONLY = frozenset({"nytimes"})


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=UTC)
    return None


def _image(entry) -> tuple[str, str]:
    for media in entry.get("media_content", []) or []:
        if media.get("url"):
            return media["url"], media.get("credit", "") or ""
    for thumb in entry.get("media_thumbnail", []) or []:
        if thumb.get("url"):
            return thumb["url"], ""
    for link in entry.get("links", []) or []:
        if str(link.get("type", "")).startswith("image/") and link.get("href"):
            return link["href"], ""
    return "", ""


def parse_feed(body: bytes, feed: Feed) -> list[Article]:
    """Pure: bytes in, articles out. The half of this module worth testing."""
    parsed = feedparser.parse(body)
    articles: list[Article] = []
    for entry in parsed.entries:
        image_url, credit = _image(entry)
        article = to_article(
            url=entry.get("link", ""),
            title=entry.get("title", ""),
            summary=entry.get("summary", "") or entry.get("description", ""),
            published_at=_published(entry),
            source=feed.source,
            language=feed.language,
            image_url=image_url,
            image_credit=credit or feed.source,
        )
        if article is not None:
            articles.append(article)
    return articles


class RssSource:
    def __init__(self, feed: Feed) -> None:
        self.feed = feed
        self.name = f"{feed.source}:{feed.url}"
        self.region = feed.region

    async def fetch(self) -> list[Article]:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            response = await client.get(self.feed.url)
            response.raise_for_status()
        return await asyncio.to_thread(parse_feed, response.content, self.feed)


def sources_for(region: Region) -> list[RssSource]:
    return [RssSource(f) for f in (PL_FEEDS if region == "pl" else WORLD_FEEDS)]
