"""The news pipeline, run offline against recorded feeds.

The fixtures in `tests/fixtures/news/` are real responses captured from the
real sources. Everything here runs against them through `respx`, so the whole
ingest job is exercised without a network and without spending anything.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import Random

import httpx
import pytest
import respx

from app.llm.fake import FakeLLM
from app.news import ingest, pool
from app.news.cluster import cluster, cosine, distinctive, mean
from app.news.dedup import already_played, record, unplayed
from app.news.fulltext import extract
from app.news.models import Article, Event, PlayedEvent, Scores, now
from app.news.normalize import canonical, clean, dedup, to_article
from app.news.sources.rss import PL_FEEDS, WORLD_FEEDS, Feed, RssSource, parse_feed
from app.news.sources.wikipedia import parse_day
from app.storage.memory import MemoryStore

FIXTURES = Path(__file__).parent / "fixtures" / "news"
INDEX = json.loads((FIXTURES / "index.json").read_text())


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def recorded(url: str) -> bytes:
    return fixture(INDEX[url])


# ── normalizing ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.rmf24.pl/a?utm_source=rss&utm_medium=feed", "https://rmf24.pl/a"),
        ("http://RMF24.pl/a/", "https://rmf24.pl/a"),
        ("https://theguardian.com/a?CMP=share_btn_url", "https://theguardian.com/a"),
        ("https://bbc.co.uk/news/x?id=7", "https://bbc.co.uk/news/x?id=7"),
    ],
)
def test_canonicalization_strips_only_what_means_nothing(raw, expected):
    assert canonical(raw) == expected


def test_summaries_arrive_as_html_and_leave_as_text():
    assert clean("<p>Coś <b>się</b>  stało</p>") == "Coś się stało"


def test_an_entry_with_no_title_is_not_an_article():
    assert (
        to_article(
            url="https://x.test/a",
            title="  ",
            summary="s",
            published_at=None,
            source="x",
            language="pl",
        )
        is None
    )


def test_dedup_keeps_the_fullest_version_of_a_url():
    def make(summary: str) -> Article:
        return Article(
            url="https://x.test/a?utm_source=rss",
            canonical_url="https://x.test/a",
            title="t",
            summary=summary,
            published_at=now(),
            source="x",
            language="pl",
        )

    kept = dedup([make("short"), make("a much longer summary")])
    assert len(kept) == 1
    assert kept[0].summary == "a much longer summary"


# ── sources ─────────────────────────────────────────────────────────────


def test_every_recorded_feed_parses_into_articles():
    for feed in (*PL_FEEDS, *WORLD_FEEDS):
        if feed.url not in INDEX:
            continue
        articles = parse_feed(recorded(feed.url), feed)
        assert len(articles) >= 15, feed.url
        assert all(a.title and a.canonical_url for a in articles)
        assert all(a.language == feed.language for a in articles)


def test_polish_feeds_carry_press_photos():
    """News mode leans on these; a feed that stopped sending them is a regression."""
    feed = PL_FEEDS[0]
    articles = parse_feed(recorded(feed.url), feed)
    assert sum(1 for a in articles if a.image_url) > len(articles) * 0.8


def test_the_current_events_portal_yields_only_sourced_bullets():
    body = json.loads(fixture("wikipedia-current-events.json"))
    day = datetime.now(UTC).date()
    articles = parse_day(body["parse"]["wikitext"], day)

    assert articles, "the recorded day had events on it"
    assert all(a.canonical_url.startswith("https://") for a in articles)
    assert all(len(a.title) >= 30 for a in articles)
    # Citations are stripped out of the prose, not left in it.
    assert all("[http" not in a.title for a in articles)
    assert all("[[" not in a.title for a in articles)


def test_a_bullet_without_a_citation_is_not_an_event():
    text = "*[[Some ongoing thing]]\n**A heading with no source at all in it here\n"
    assert parse_day(text, datetime.now(UTC).date()) == []


async def test_a_source_is_fetched_over_http_and_parsed():
    feed = PL_FEEDS[0]
    with respx.mock:
        respx.get(feed.url).mock(return_value=httpx.Response(200, content=recorded(feed.url)))
        articles = await RssSource(feed).fetch()
    assert len(articles) > 20


# ── clustering ──────────────────────────────────────────────────────────


def make_event(title: str, *, sources: int = 1, urls: list[str] | None = None) -> Event:
    articles = [
        Article(
            url=f"https://x{i}.test/a",
            canonical_url=(urls[i] if urls else f"https://x{i}.test/a"),
            title=title,
            summary=title,
            published_at=now(),
            source=f"outlet{i}",
            language="pl",
        )
        for i in range(sources)
    ]
    return Event(
        id=title[:8],
        region="pl",
        title=title,
        summary=title,
        language="pl",
        articles=articles,
        embedding=[1.0, 0.0],
    )


def test_cosine_of_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([], [1.0]) == 0.0


def test_the_mean_of_a_cluster_is_a_unit_vector():
    centre = mean([[1.0, 0.0], [0.0, 1.0]])
    assert round(sum(v * v for v in centre), 6) == 1.0


def test_distinctive_words_are_the_rare_ones():
    """Genre words are what two unrelated crashes share; names are not."""
    articles = [
        make_event(t).articles[0]
        for t in [
            "Tragedia pod Kartuzami kierowca zginął wypadek",
            "Tragedia w Krakowie kierowca zginął wypadek",
            "Tragedia w Poznaniu kierowca zginął wypadek",
            "Tragedia w Gdańsku kierowca zginął wypadek",
        ]
    ]
    rare = distinctive(articles)
    assert "kierowca" not in rare[0], "a word in every article identifies nothing"
    assert "kartuzami" in rare[0]
    assert not (rare[0] & rare[1]), "different places share no distinctive word"


async def test_two_reports_of_one_story_become_one_event():
    """Both gates have to pass: close enough, and about the same named thing."""
    llm = FakeLLM()
    shared = (
        "Pożar hali magazynowej pod Radziejowem. Dwie osoby zostały ranne i "
        "trafiły do szpitala. Strażacy walczyli z ogniem przez całą noc."
    )
    articles = [
        Article(
            url=f"https://o{i}.test/a",
            canonical_url=f"https://o{i}.test/a",
            title=f"{prefix} pod Radziejowem",
            summary=shared,
            published_at=now(),
            source=f"outlet{i}",
            language="pl",
        )
        for i, prefix in enumerate(["Potężny pożar hali", "Pożar hali magazynowej"])
    ]
    events = await cluster(llm, articles, "pl")
    assert len(events) == 1
    assert len(events[0].articles) == 2


async def test_clustering_never_loses_an_article():
    """Over a whole real feed: every article ends up in exactly one event."""
    llm = FakeLLM()
    feed = PL_FEEDS[0]
    articles = parse_feed(recorded(feed.url), feed)
    events = await cluster(llm, articles, "pl")

    assert sum(len(e.articles) for e in events) == len(articles)
    urls = [a.canonical_url for e in events for a in e.articles]
    assert len(set(urls)) == len(urls), "an article landed in two events"
    assert all(e.embedding for e in events)
    assert all(e.title and e.id for e in events)


async def test_clustering_never_merges_across_the_time_window():
    llm = FakeLLM()
    old = now() - timedelta(days=30)
    articles = [
        Article(
            url=f"https://x.test/{i}",
            canonical_url=f"https://x.test/{i}",
            title="Pożar hali w Radziejowie, dwie osoby ranne",
            summary="Pożar hali w Radziejowie, dwie osoby ranne",
            published_at=now() if i == 0 else old,
            source=f"o{i}",
            language="pl",
        )
        for i in range(2)
    ]
    events = await cluster(llm, articles, "pl")
    assert len(events) == 2, "identical text a month apart is not one event"


# ── dedup ───────────────────────────────────────────────────────────────


def test_a_shared_url_means_already_played():
    event = make_event("Coś się stało", urls=["https://a.test/1"])
    history = [PlayedEvent(event_id="other", canonical_urls=["https://a.test/1"])]
    assert already_played(event, history)


def test_the_same_cluster_id_means_already_played():
    event = make_event("Coś się stało")
    assert already_played(event, [record(event)])


def test_a_close_embedding_means_already_played():
    event = make_event("Coś się stało")
    event.embedding = [1.0, 0.0]
    history = [PlayedEvent(event_id="x", embedding=[0.99, 0.141])]
    assert already_played(event, history)


def test_a_similar_but_different_story_is_still_offered():
    """0.93 is deliberately strict: another rocket landing is a new event."""
    event = make_event("Kolejne lądowanie rakiety")
    event.embedding = [1.0, 0.0]
    history = [PlayedEvent(event_id="x", embedding=[0.9, 0.436])]
    assert not already_played(event, history)


def test_an_old_play_stops_blocking_eventually():
    event = make_event("Coś")
    event.embedding = [1.0, 0.0]
    stale = PlayedEvent(event_id="x", embedding=[1.0, 0.0], played_at=now() - timedelta(days=60))
    assert not already_played(event, [stale])


def test_unplayed_filters_a_list():
    a, b = make_event("A", urls=["https://a.test/1"]), make_event("B", urls=["https://b.test/1"])
    a.embedding = b.embedding = []
    history = [record(a)]
    assert [e.title for e in unplayed([a, b], history)] == ["B"]


# ── the pool ────────────────────────────────────────────────────────────


def playable_event(title: str, rank: float, *, safety: str = "allowed") -> Event:
    event = make_event(title, urls=[f"https://{title}.test/1"])
    event.scores = Scores(
        importance=rank,
        interest=rank,
        playability=rank,
        safety_class=safety,
        roles=["witness"],
    )
    return event


def test_merge_adds_without_replacing_and_expires_the_old():
    from app.news.models import Dossier

    held = playable_event("held", 0.8)
    held.dossier = Dossier(what="w", where="w", when="w")
    stale = playable_event("stale", 0.8)
    stale.published_at = now() - timedelta(days=30)

    merged = pool.merge([held, stale], [playable_event("held", 0.9), playable_event("new", 0.7)])
    titles = {e.title for e in merged}

    assert titles == {"held", "new"}, "expired events go, new ones arrive"
    kept = next(e for e in merged if e.title == "held")
    assert kept.dossier is not None, "enrichment that was paid for must survive a re-ingest"
    assert kept.scores.playability == 0.9, "but the scores are refreshed"


def test_a_blocked_event_never_becomes_playable():
    events = [playable_event("bad", 0.9, safety="blocked"), playable_event("fine", 0.9)]
    assert [e.title for e in pool.playable(events)] == ["fine"]


def test_choose_skips_what_this_player_has_already_seen():
    events = [playable_event("a", 0.9), playable_event("b", 0.8)]
    for e in events:
        e.embedding = []
    picked = pool.choose(events, [record(events[0])], rng=Random(0))
    assert picked is not None
    assert picked.title == "b"


def test_choose_returns_nothing_when_the_pool_is_exhausted():
    events = [playable_event("a", 0.9)]
    events[0].embedding = []
    assert pool.choose(events, [record(events[0])], rng=Random(0)) is None


def test_choose_does_not_serve_the_same_event_to_everyone():
    events = [playable_event(f"e{i}", 0.9 - i * 0.02) for i in range(8)]
    for e in events:
        e.embedding = []
    picked = {pool.choose(events, [], rng=Random(seed)).title for seed in range(30)}
    assert len(picked) > 3, "a weighted draw that always picks the top is not a draw"


# ── the job ─────────────────────────────────────────────────────────────


def mock_feeds(mock, feeds: tuple[Feed, ...]) -> list[Feed]:
    available = [f for f in feeds if f.url in INDEX]
    for feed in available:
        mock.get(feed.url).mock(return_value=httpx.Response(200, content=recorded(feed.url)))
    return available


async def test_the_whole_job_runs_offline_and_fills_a_pool():
    llm, store = FakeLLM(), MemoryStore()
    with respx.mock as mock:
        chosen = [RssSource(f) for f in mock_feeds(mock, PL_FEEDS)]
        status = await ingest.refresh(llm, store, "pl", which=chosen)

    assert status.total > 20
    assert status.playable > 0
    assert status.refreshed_at is not None
    assert llm.usage.usd > 0, "the job is costed even when it is faked"


async def test_a_dead_source_costs_depth_not_the_region():
    llm, store = FakeLLM(), MemoryStore()
    with respx.mock as mock:
        available = mock_feeds(mock, PL_FEEDS)
        dead = Feed("https://dead.test/feed", "dead", "pl", "pl")
        mock.get(dead.url).mock(side_effect=httpx.ConnectError("gone"))
        chosen = [RssSource(f) for f in (*available, dead)]
        status = await ingest.refresh(llm, store, "pl", which=chosen)

    assert status.total > 20, "one dead feed must not empty a region"


async def test_a_refresh_that_finds_nothing_leaves_the_pool_alone():
    llm, store = FakeLLM(), MemoryStore()
    with respx.mock as mock:
        chosen = [RssSource(f) for f in mock_feeds(mock, PL_FEEDS)]
        await ingest.refresh(llm, store, "pl", which=chosen)
    before = await store.pool_status("pl")

    with respx.mock as mock:
        dead = Feed("https://dead.test/feed", "dead", "pl", "pl")
        mock.get(dead.url).mock(side_effect=httpx.ConnectError("gone"))
        after = await ingest.refresh(llm, store, "pl", which=[RssSource(dead)])

    assert after.total == before.total > 0


async def test_a_deep_fresh_pool_is_not_refreshed_again():
    """This is the cost control: a second player in the same hour is free."""
    llm, store = FakeLLM(), MemoryStore()
    with respx.mock as mock:
        chosen = [RssSource(f) for f in mock_feeds(mock, PL_FEEDS)]
        await ingest.refresh(llm, store, "pl", which=chosen)

    spent = llm.usage.usd
    await ingest.ensure_pool(llm, store, "pl")
    assert llm.usage.usd == spent, "a healthy pool must not trigger a refresh"


async def test_an_empty_pool_is_always_refreshed():
    assert ingest._needs_refresh(await MemoryStore().pool_status("pl"))


# ── full text ───────────────────────────────────────────────────────────


def test_article_text_is_the_paragraphs_and_not_the_furniture():
    html = (
        "<html><head><style>p{}</style></head><body>"
        "<script>var p = '<p>not this</p>';</script>"
        "<p>Nav</p>"
        "<p>" + "A real paragraph of article text that is long enough to keep. " * 2 + "</p>"
        "<p>Another genuine paragraph, also comfortably past the length cut-off.</p>"
        "</body></html>"
    )
    text = extract(html)
    assert "A real paragraph" in text
    assert "Another genuine paragraph" in text
    assert "Nav" not in text
    assert "var p" not in text
