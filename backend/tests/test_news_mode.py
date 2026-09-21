"""News mode end to end, and the safety cases it must get right.

The safety eval runs against `FakeLLM`, whose scorer classifies on keywords.
That is the point: these tests assert that the *pipeline* honours a
classification - blocking what is blocked, restricting who the player is
allowed to be, showing a note before the game starts - rather than asserting
that a model produces the right one. The second thing is what the live eval in
Phase 9 is for; this is the thing CI can hold.
"""

from datetime import timedelta

import pytest

from app.errors import AppError
from app.llm.fake import FakeLLM
from app.models.game import NewGameRequest
from app.news import pool
from app.news.dedup import record
from app.news.models import Article, Event, Scores, now
from app.pipeline import live, news_game
from app.pipeline.ending import match_score, write_ending
from app.pipeline.photos import MIN_CONFIDENCE, best_for_opening, match_photos
from app.pipeline.style_catalog import SAFE_ROLES
from app.storage.assets import MemoryAssets
from app.storage.memory import MemoryStore

#: The six cases from the plan, each written the way a feed would carry it.
EVAL_CASES = {
    "nepal_earthquake": (
        "Earthquake in Nepal kills hundreds as rescue teams reach the valley",
        "safe_mode",
    ),
    "sejm_brawl": ("Brawl in the Sejm as opposition MPs storm the rostrum", "allowed"),
    "spacex_landing": ("SpaceX lands a booster on the drone ship after night launch", "allowed"),
    "terror_attack_named": (
        "Terror attack at the station: police name the victims killed in the blast",
        "safe_mode",
    ),
    "missing_child": (
        "Search continues for missing girl last seen near the canal",
        "blocked",
    ),
    "celebrity_divorce": ("Actor files for divorce after eight years", "blocked"),
}


def make_event(title: str, *, region="world", photos: int = 0, ident: str | None = None) -> Event:
    articles = [
        Article(
            url=f"https://o{i}.test/{abs(hash(title)) % 9999}",
            canonical_url=f"https://o{i}.test/{abs(hash(title)) % 9999}",
            title=title,
            summary=f"{title}. Several outlets carried the story through the afternoon.",
            published_at=now() - timedelta(hours=i),
            source=f"outlet{i}",
            language="en",
            image_url=f"https://o{i}.test/photo.jpg" if i < photos else "",
            image_credit=f"Outlet {i}",
        )
        for i in range(3)
    ]
    return Event(
        id=ident or title[:14],
        region=region,
        title=title,
        summary=articles[0].summary,
        language="en",
        articles=articles,
        embedding=[1.0, 0.0],
        scores=Scores(
            importance=0.8, interest=0.8, playability=0.8, roles=["witness", "journalist"]
        ),
    )


async def pooled(store: MemoryStore, *events: Event, region="world") -> None:
    await store.put_pool(region, list(events))


def request(**overrides) -> NewGameRequest:
    return NewGameRequest(
        **{
            "mode": "news",
            "region": "world",
            "language": "en",
            **overrides,
        }
    )


async def build(store: MemoryStore, llm: FakeLLM | None = None, **overrides):
    llm = llm or FakeLLM()
    stages: list[str] = []

    async def progress(stage: str) -> None:
        stages.append(stage)

    opened = await news_game.build(
        llm,
        MemoryAssets(),
        game_id="news-game",
        req=request(**overrides),
        uid="u1",
        store=store,
        progress=progress,
    )
    return llm, opened, stages


# ── the safety cases ────────────────────────────────────────────────────


@pytest.mark.parametrize(("case", "expected"), [(k, v[1]) for k, v in EVAL_CASES.items()])
async def test_every_safety_case_classifies_as_it_should(case, expected):
    from app.news.score import score

    event = make_event(EVAL_CASES[case][0])
    await score(FakeLLM(), [event])
    assert event.scores.safety_class == expected


async def test_a_blocked_event_is_never_drawn_from_the_pool():
    from app.news.score import score

    store = MemoryStore()
    blocked = make_event(EVAL_CASES["missing_child"][0])
    fine = make_event(EVAL_CASES["spacex_landing"][0])
    await score(FakeLLM(), [blocked, fine])
    await pooled(store, blocked, fine)

    _, opened, _ = await build(store)
    assert opened.state.safety_class != "blocked"
    assert "missing" not in opened.script.plan.premise.lower()


async def test_safe_mode_restricts_who_the_player_is_allowed_to_be():
    from app.news.score import score

    store = MemoryStore()
    event = make_event(EVAL_CASES["nepal_earthquake"][0])
    await score(FakeLLM(), [event])
    await pooled(store, event)

    _, opened, _ = await build(store)
    assert opened.state.safety_class == "safe_mode"
    assert opened.state.style_card.protagonist_role in SAFE_ROLES
    # The deadpan/absurdist/pixel values would read badly over a disaster.
    assert opened.state.style_card.genre != "absurdist"
    assert opened.state.style_card.tone != "deadpan"
    assert opened.state.style_card.visual_style != "pixel"


async def test_safe_mode_shows_a_content_note_before_the_game_starts():
    from app.news.score import score

    store = MemoryStore()
    event = make_event(EVAL_CASES["terror_attack_named"][0])
    await score(FakeLLM(), [event])
    await pooled(store, event)

    _, opened, _ = await build(store)
    assert opened.state.content_note, "safe mode without a note gives no chance to decline"


async def test_an_allowed_event_carries_no_content_note():
    from app.news.score import score

    store = MemoryStore()
    event = make_event(EVAL_CASES["sejm_brawl"][0])
    await score(FakeLLM(), [event])
    await pooled(store, event)

    _, opened, _ = await build(store)
    assert opened.state.safety_class == "allowed"
    assert opened.state.content_note is None


async def test_the_safety_rule_reaches_the_prompts_that_write_the_prose():
    from app.news.score import score

    store = MemoryStore()
    event = make_event(EVAL_CASES["nepal_earthquake"][0])
    await score(FakeLLM(), [event])
    await pooled(store, event)

    llm, opened, _ = await build(store)
    await live.fill_scenes(llm, opened.script, opened.plan, opened.style, safety_class="safe_mode")

    written = [system for stage, system in llm.prompts if stage in {"plan", "scenes"}]
    assert written
    assert all("Do not describe injuries" in text for text in written)


async def test_a_private_individual_is_never_named_in_the_brief():
    """The name is dropped during enrichment, so no prompt can leak it."""
    from app.news.enrich import enrich

    event = make_event(EVAL_CASES["terror_attack_named"][0])
    await enrich(FakeLLM(), event)

    private = [p for p in event.dossier.who if not p.public_figure]
    assert private, "the fake dossier includes a private individual"
    assert all(not p.name for p in private)
    assert "Kowalski" not in news_game.news_brief(event)


# ── the game ────────────────────────────────────────────────────────────


async def test_a_news_game_is_built_from_the_dossier_and_scored_against_it():
    store = MemoryStore()
    await pooled(store, make_event(EVAL_CASES["spacex_landing"][0]))

    _, opened, stages = await build(store)
    assert stages == ["story", "map", "images", "music", "finishing"]
    assert opened.state.mode == "news"
    assert opened.state.region == "world"
    assert opened.state.source_note, "a real-events disclaimer runs for the whole game"

    # The canon is what happened, not what the plan invented.
    assert opened.plan.beats
    assert [b.id for b in opened.plan.beats] == [
        f"beat-{i + 1}" for i in range(len(opened.plan.beats))
    ]
    assert all(b.sources for b in opened.plan.beats), "canon beats carry citations"
    assert all(b.location_ref for b in opened.plan.beats)
    assert opened.script.ending.canon, "news endings compare against canon"


async def test_a_news_ending_scores_the_run_against_what_happened():
    store = MemoryStore()
    await pooled(store, make_event(EVAL_CASES["spacex_landing"][0]))
    llm, opened, _ = await build(store)
    await live.fill_scenes(llm, opened.script, opened.plan, opened.style)

    state = opened.state
    for index, beat in enumerate(state.beat_progress):
        beat.status = "matched" if index % 2 == 0 else "diverged"

    ending = await write_ending(llm, state=state, script=opened.script, plan=opened.plan)
    assert ending.match_score == match_score(state)
    assert 0.0 < ending.match_score < 1.0
    assert ending.sources, "the player can go and read what actually happened"


async def test_an_event_is_not_offered_to_the_same_player_twice():
    store = MemoryStore()
    first = make_event(EVAL_CASES["spacex_landing"][0], ident="a")
    second = make_event(EVAL_CASES["sejm_brawl"][0], ident="b")
    second.embedding = [0.0, 1.0]
    await pooled(store, first, second)

    await build(store)
    await build(store)

    played = await store.played_events("u1")
    assert {p.event_id for p in played} == {"a", "b"}, "the second game drew the other event"


async def test_an_exhausted_pool_is_a_friendly_error_not_a_crash():
    store = MemoryStore()
    event = make_event(EVAL_CASES["spacex_landing"][0])
    await pooled(store, event)
    await store.mark_played("u1", record(event))

    with pytest.raises(AppError) as raised:
        await build(store)
    assert raised.value.kind == "pool_empty"


async def test_the_pool_is_only_refreshed_when_it_has_to_be():
    """A deep, recent pool must not trigger an ingest for every game."""
    store = MemoryStore()
    await pooled(
        store, *(make_event(f"Event number {i} happened today", ident=str(i)) for i in range(20))
    )
    llm, _, _ = await build(store)
    assert "cluster" not in llm.usage.by_stage, "a healthy pool must not be re-ingested"


# ── press photos ────────────────────────────────────────────────────────


async def test_a_press_photo_is_used_for_the_opening_instead_of_a_generated_one():
    import httpx
    import respx

    from app.news.enrich import enrich

    store = MemoryStore()
    event = make_event(EVAL_CASES["spacex_landing"][0], photos=2)
    with respx.mock:
        respx.get(url__regex=r".*photo\.jpg").mock(
            return_value=httpx.Response(200, content=b"\xff\xd8\xff" + b"x" * 5000)
        )
        await enrich(FakeLLM(), event, MemoryAssets())

    assert event.photos, "the safety check passed the photos"
    opening = best_for_opening(event.photos)
    assert opening is not None
    assert opening.credit is not None, "a press photo is always credited"

    await pooled(store, event)
    llm, opened, _ = await build(store)
    assert opened.state.current_scene.image_credit is not None
    assert llm.usage.images == 0, "News mode should not generate its opening image"


async def test_a_photo_that_fits_nowhere_is_left_unused():
    from app.news.models import Photo

    llm = FakeLLM()
    store = MemoryStore()
    await pooled(store, make_event(EVAL_CASES["spacex_landing"][0]))
    _, opened, _ = await build(store, llm)

    unmatched = [
        Photo(url="u", source_url="s", credit="c", stored_url="/a.jpg", caption="a studio portrait")
    ]

    class Refusing(FakeLLM):
        async def json(self, stage, prompt, schema, *, system=None, temperature=1.0):
            from app.pipeline.photos import Match, Matches

            if schema is Matches:
                return Matches(matches=[Match(photo_index=0, location_index=-1, confidence=0.9)])
            return await super().json(stage, prompt, schema, system=system)

    placed = await match_photos(Refusing(), opened.plan, unmatched)
    assert placed == {}, "a wrong photo of a real event is worse than a generated one"
    assert MIN_CONFIDENCE > 0


# ── refreshing without the player waiting ───────────────────────────────


async def test_a_pool_that_can_still_serve_is_refreshed_behind_the_player():
    """A refresh takes most of a minute; it does not go in front of a game."""
    import asyncio

    from app.news import ingest
    from app.pipeline import news_game as module
    from app.settings import settings

    store = MemoryStore()
    await pooled(store, *(make_event(f"Event number {i} happened", ident=str(i)) for i in range(6)))

    refreshed = asyncio.Event()

    async def fake_refresh(llm, st, region, **kwargs):
        refreshed.set()
        return await st.pool_status(region)

    settings.news_ingest_enabled = True
    original = ingest.refresh
    ingest.refresh = fake_refresh
    try:
        # The pool is deep but stale, so a refresh is wanted - behind the game.
        settings.pool_max_age_hours = 0.0
        _, opened, _ = await build(store)
        assert opened.state.mode == "news", "the game started without waiting"
        await asyncio.wait_for(refreshed.wait(), timeout=2)
    finally:
        ingest.refresh = original
        settings.news_ingest_enabled = False
        settings.pool_max_age_hours = 6.0
        module._refreshing.clear()


async def test_an_empty_pool_leaves_no_choice_but_to_wait():
    from app.news import ingest

    store = MemoryStore()
    calls: list[str] = []

    async def fake_refresh(llm, st, region, **kwargs):
        calls.append(region)
        await pooled(st, make_event(EVAL_CASES["spacex_landing"][0]))
        return await st.pool_status(region)

    from app.settings import settings

    settings.news_ingest_enabled = True
    original = ingest.refresh
    ingest.refresh = fake_refresh
    try:
        _, opened, _ = await build(store)
        assert calls == ["world"], "a cold pool has to be filled before anyone can play"
        assert opened.state.mode == "news"
    finally:
        ingest.refresh = original
        settings.news_ingest_enabled = False


# ── choosing the story ──────────────────────────────────────────────────


def _scored(title: str, *, importance: float, playability: float = 0.8, **kw) -> Event:
    event = make_event(title, **kw)
    event.scores = Scores(
        importance=importance, interest=0.5, playability=playability, roles=["witness"]
    )
    return event


def test_the_shortlist_is_ordered_by_importance_not_rank():
    """The player is choosing, so the useful order is what mattered most.

    `rank` weights playability highest, which is right when the machine picks
    and wrong here - it would put a very playable minor story above the day's
    biggest one.
    """
    events = [
        _scored("A minor story that happens to play well", importance=0.2, playability=1.0),
        _scored("The largest thing that happened today", importance=0.95, playability=0.5),
        _scored("Something in between", importance=0.6),
    ]
    titles = [e.title for e in pool.shortlist(events, [])]
    assert titles[0] == "The largest thing that happened today"
    assert titles[1] == "Something in between"


def test_the_shortlist_hides_what_is_unplayable_or_already_played():
    big = _scored("A story worth playing", importance=0.9)
    unplayable = _scored("Important but nobody can act in it", importance=0.99, playability=0.1)
    played = _scored("Already seen this one", importance=0.95)
    # `make_event` hands out one shared vector, which dedup reads as "the same
    # story"; orthogonal ones are what make these three distinguishable.
    for index, event in enumerate((big, unplayable, played)):
        event.embedding = [1.0 if i == index else 0.0 for i in range(3)]

    offered = pool.shortlist([big, unplayable, played], [record(played)])
    assert [e.title for e in offered] == ["A story worth playing"]


def test_the_shortlist_is_capped():
    events = [_scored(f"Story number {i}", importance=i / 100) for i in range(30)]
    assert len(pool.shortlist(events, [])) == pool.SHORTLIST


@pytest.mark.anyio
async def test_a_chosen_event_is_the_one_played():
    store = MemoryStore()
    wanted = make_event("Divers reach the wreck and recover the bell", ident="wanted")
    await pooled(store, make_event("Something else entirely", ident="other"), wanted)

    picked = await news_game.pick(FakeLLM(), store, "world", "p1", event_id="wanted")
    assert picked is not None and picked.id == "wanted"


@pytest.mark.anyio
async def test_a_chosen_event_that_has_since_expired_reads_as_an_empty_pool():
    """The list and the click are separate requests; a refresh can land between."""
    store = MemoryStore()
    await pooled(store, make_event("Still here", ident="here"))
    assert await news_game.pick(FakeLLM(), store, "world", "p1", event_id="gone") is None


@pytest.mark.anyio
async def test_choosing_never_offers_a_blocked_event():
    store = MemoryStore()
    blocked = make_event("Search continues for missing girl last seen near the canal")
    blocked.scores = Scores(importance=0.9, playability=0.9, safety_class="blocked")
    await pooled(store, blocked)
    assert await news_game.shortlist(FakeLLM(), store, "world", "p1") == []
