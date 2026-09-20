"""English Wikipedia's Current Events portal.

This is the one source in the whole system that is *already* importance
filtered. An RSS feed is whatever an outlet published most recently, in
publication order, with no signal about which of it mattered; a
`Portal:Current_events/<date>` page is a human-curated list of the day's
significant events, each with its own citations, at roughly thirty-five to
forty bullets a day.

It is also backfillable: any past date can be fetched, so a pool that has gone
cold can be filled from yesterday and the day before rather than having to
wait for news to happen. No Polish equivalent exists - `pl.wikipedia.org`
answers the same request with `missingtitle`.
"""

import asyncio
import logging
import re
from datetime import UTC, date, datetime, timedelta

import httpx

from app.news.models import Article
from app.news.normalize import to_article
from app.news.sources.rss import TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)

API = "https://en.wikipedia.org/w/api.php"
#: How many days back a single fetch walks. Each day is one API call.
DEFAULT_DAYS = 3
#: Bullets shorter than this are section headings, not events.
MIN_TEXT = 30

_BULLET = re.compile(r"^\*+\s*(.+)$")
#: `[[Target|shown]]` or `[[shown]]`.
_LINK = re.compile(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]")
#: A citation: an external link whose label names the publisher, as in
#: `[https://example.com (''Iran International'')]`.
_REF = re.compile(r"\[(https?://[^\s\]]+)\s+([^\]]*)\]")
_MARKUP = re.compile(r"''+|\{\{[^}]*\}\}|<[^>]+>")
_PUBLISHER = re.compile(r"[()'\s]+")


def page_for(day: date) -> str:
    return f"Portal:Current events/{day.strftime('%Y_%B_%-d')}"


def parse_day(wikitext: str, day: date) -> list[Article]:
    """One article per bullet that carries a citation.

    A bullet with no source is a heading or a piece of context rather than an
    event, so it is dropped instead of becoming a sourceless article.
    """
    articles: list[Article] = []
    when = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)

    for line in wikitext.splitlines():
        bullet = _BULLET.match(line.strip())
        if bullet is None:
            continue
        raw = bullet.group(1)
        reference = _REF.search(raw)
        if reference is None:
            continue

        # Strip the citations first, then the wiki markup, leaving a sentence.
        text = _MARKUP.sub("", _LINK.sub(r"\1", _REF.sub("", raw))).strip(" –—-")
        text = " ".join(text.split())
        if len(text) < MIN_TEXT:
            continue

        publisher = _PUBLISHER.sub(" ", reference.group(2)).strip()
        article = to_article(
            url=reference.group(1),
            title=text[:180],
            summary=text,
            published_at=when,
            source=publisher or "Wikipedia Current Events",
            language="en",
        )
        if article is not None:
            articles.append(article)
    return articles


class WikipediaCurrentEvents:
    name = "wikipedia:current-events"
    region = "world"

    def __init__(self, days: int = DEFAULT_DAYS, today: date | None = None) -> None:
        self.days = days
        self.today = today or datetime.now(UTC).date()

    async def fetch(self) -> list[Article]:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            pages = await asyncio.gather(
                *(
                    self._day(client, self.today - timedelta(days=offset))
                    for offset in range(self.days)
                ),
                return_exceptions=True,
            )

        articles: list[Article] = []
        for page in pages:
            if isinstance(page, BaseException):
                # One missing day is normal near midnight UTC; the rest stand.
                log.warning("a current-events day failed: %s", page)
                continue
            articles.extend(page)
        return articles

    async def _day(self, client: httpx.AsyncClient, day: date) -> list[Article]:
        response = await client.get(
            API,
            params={
                "action": "parse",
                "page": page_for(day),
                "prop": "wikitext",
                "formatversion": "2",
                "format": "json",
            },
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            log.info("no current-events page for %s: %s", day, body["error"].get("code"))
            return []
        return parse_day(body["parse"]["wikitext"], day)
