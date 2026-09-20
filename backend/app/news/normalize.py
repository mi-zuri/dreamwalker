"""Turning a feed entry into an `Article`.

Mostly this is URL canonicalization, which does more work for us than it
looks: two outlets syndicating the same wire story, or one outlet linking its
own article from three places, collapse to one canonical URL and are deduped
before clustering ever has to think about them.
"""

import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from app.models.game import Language
from app.news.models import Article

#: Tracking parameters, which differ per referrer and mean nothing.
_JUNK_PARAMS = re.compile(
    r"^(utm_|fbclid$|gclid$|ref$|ref_src$|srnd$|smid$|partner$|CMP$|cmp$|ito$)"
)
_WHITESPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


def canonical(url: str) -> str:
    """Scheme and host lowered, tracking stripped, trailing slash dropped."""
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return url.strip()

    host = parts.netloc.lower().removeprefix("www.").split(":")[0]
    query = "&".join(f"{k}={v}" for k, v in parse_qsl(parts.query) if not _JUNK_PARAMS.match(k))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, query, ""))


def clean(text: str) -> str:
    """Feed summaries arrive as HTML fragments more often than not."""
    return _WHITESPACE.sub(" ", _TAGS.sub(" ", text or "")).strip()


def to_article(
    *,
    url: str,
    title: str,
    summary: str,
    published_at: datetime | None,
    source: str,
    language: Language,
    image_url: str = "",
    image_credit: str = "",
) -> Article | None:
    """`None` for an entry with nothing usable in it, rather than a blank article."""
    title = clean(title)
    if not url or not title:
        return None
    return Article(
        url=url.strip(),
        canonical_url=canonical(url),
        title=title,
        summary=clean(summary),
        published_at=published_at or datetime.now(UTC),
        source=source,
        language=language,
        image_url=image_url.strip(),
        image_credit=clean(image_credit),
    )


def dedup(articles: list[Article]) -> list[Article]:
    """One article per canonical URL, keeping the one with the most text."""
    best: dict[str, Article] = {}
    for article in articles:
        held = best.get(article.canonical_url)
        if held is None or len(article.summary) > len(held.summary):
            best[article.canonical_url] = article
    return sorted(best.values(), key=lambda a: a.published_at, reverse=True)
