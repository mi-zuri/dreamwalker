"""Reading the article, not just the headline.

A feed summary is one or two sentences, which is enough to cluster and score
an event and nowhere near enough to build a dossier from. Enrichment fetches
the real page for a handful of articles in the cluster.

Two rules constrain this and both are checked, not assumed:

* **robots.txt**, fetched once per host and cached. None of the chosen outlets
  disallow article paths for `*`, but that is a fact that can change and this
  re-checks it rather than trusting a note in a design document.
* **NYT is summary-only**, on ToS grounds rather than robots grounds. Its
  articles are never fetched, however permissive its robots file is.

No readability library. A news article's body is what is inside its `<p>`
tags, and the failure mode of getting that slightly wrong is a dossier with a
little navigation furniture in it, which the dossier stage ignores.
"""

import asyncio
import logging
import re
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.news.models import Article
from app.news.sources.rss import SUMMARY_ONLY, TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)

#: Articles read per event. Three to five gives the dossier cross-checkable
#: detail without paying to read the same wire copy five times.
MAX_ARTICLES = 4
#: Characters kept per article. Past this it is comment threads and related
#: links, and it is the dossier prompt's input bill.
MAX_BODY = 6000

_SCRIPTS = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_PARAGRAPH = re.compile(r"<p\b[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")

_robots: dict[str, RobotFileParser | None] = {}
_robots_lock = asyncio.Lock()


def extract(html: str) -> str:
    """Paragraph text, in document order."""
    body = _SCRIPTS.sub(" ", html)
    paragraphs = []
    for match in _PARAGRAPH.finditer(body):
        text = _SPACE.sub(" ", _TAG.sub(" ", match.group(1))).strip()
        # One-liners at this length are captions, bylines and cookie notices.
        if len(text) >= 60:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)[:MAX_BODY]


async def _robots_for(client: httpx.AsyncClient, url: str) -> RobotFileParser | None:
    host = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
    async with _robots_lock:
        if host in _robots:
            return _robots[host]
    parser: RobotFileParser | None = None
    try:
        response = await client.get(f"{host}/robots.txt")
        if response.status_code < 400:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
    except httpx.HTTPError as exc:
        # No robots.txt we can read means no stated restriction.
        log.info("could not read robots.txt for %s: %s", host, exc)
    async with _robots_lock:
        _robots[host] = parser
    return parser


async def allowed(client: httpx.AsyncClient, url: str) -> bool:
    parser = await _robots_for(client, url)
    return parser is None or parser.can_fetch(USER_AGENT, url)


async def fetch_bodies(articles: list[Article], *, limit: int = MAX_ARTICLES) -> int:
    """Fill `article.body` for up to `limit` articles. Returns how many landed.

    Failures are individually survivable: a dossier built from two bodies and
    three summaries is thinner, not wrong, and is flagged as thin.
    """
    candidates = [a for a in articles if a.source not in SUMMARY_ONLY and not a.body][:limit]
    if not candidates:
        return 0

    async with httpx.AsyncClient(
        timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        results = await asyncio.gather(
            *(_one(client, article) for article in candidates), return_exceptions=True
        )
    return sum(1 for r in results if r is True)


async def _one(client: httpx.AsyncClient, article: Article) -> bool:
    if not await allowed(client, article.url):
        log.info("robots.txt disallows %s", article.url)
        return False
    try:
        response = await client.get(article.url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.info("could not fetch %s: %s", article.url, exc)
        return False

    body = extract(response.text)
    if len(body) < 300:
        return False
    article.body = body
    return True


def reset_robots_cache() -> None:
    """Test hook; the cache is process-wide and deliberately long-lived."""
    _robots.clear()
