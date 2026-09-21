"""End-to-end game loop against the real API with LLM_MODE=mock."""

import json

from app.game.map import path_to
from app.models.game import GameMap, Pos

NEW_GAME = {
    "mode": "idea",
    "idea": "a lighthouse keeper receiving letters meant for someone else",
    "language": "en",
}


def _tile_of(game_map: GameMap, key: str) -> Pos:
    for y, row in enumerate(game_map.tiles):
        x = row.find(key)
        if x >= 0:
            return Pos(x=x, y=y)
    raise AssertionError(f"destination {key} is not on the map")


def _play(client, state: dict) -> dict:
    """Walk to every destination in turn and take the first choice there."""
    game_id = state["game_id"]
    game_map = GameMap(**state["map"])

    for dest in game_map.destinations:
        target = _tile_of(game_map, dest.key)
        pos = Pos(**state["player_pos"])
        assert path_to(game_map, pos, target, state["unlocked"]), f"{dest.key} unreachable"

        state = client.post(f"/api/games/{game_id}/move", json={"to": target.model_dump()}).json()
        assert state["player_pos"] == target.model_dump()
        assert state["view"] == "scene"
        assert state["current_scene"]["location_id"] == dest.location_id

        if state.get("open_question"):
            state = client.post(
                f"/api/games/{game_id}/answer", json={"text": "That he was sorry."}
            ).json()
            assert state["open_question"] is None

        choice_id = state["choices"][0]["id"]
        state = client.post(f"/api/games/{game_id}/choose", json={"choice_id": choice_id}).json()
        assert dest.key in state["resolved"]

    return state


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["llm_mode"] == "mock"


def test_full_game(client):
    created = client.post("/api/games", json=NEW_GAME)
    assert created.status_code == 200
    game_id = created.json()["game_id"]

    # The loading stream reports every stage and then readiness.
    with client.stream("GET", f"/api/games/{game_id}/stream") as res:
        events = [line for line in res.iter_lines() if line.startswith("data:")]
    stages = [json.loads(e.removeprefix("data:")) for e in events]
    assert [s["stage"] for s in stages[:-1]] == ["story", "map", "images", "music", "finishing"]
    assert stages[-1] == {"ready": True}

    state = client.get(f"/api/games/{game_id}").json()
    assert state["mode"] == "idea"
    assert state["language"] == "en"
    assert state["finished"] is False

    state = _play(client, state)
    assert state["finished"] is True
    assert len(state["resolved"]) == len(state["map"]["destinations"])

    ending = client.get(f"/api/games/{game_id}/ending").json()
    assert ending["game_id"] == game_id
    assert ending["mode"] == "idea"
    assert ending["match_score"] is None  # idea mode has no canon to score against

    saved = client.get("/api/games").json()
    assert [g["game_id"] for g in saved] == [game_id]

    replay = client.get(f"/api/games/{game_id}/replay").json()
    assert len(replay["turns"]) == len(state["map"]["destinations"])
    assert replay["turns"][0]["chosen"]
    assert any(t["answer"] for t in replay["turns"]), "the open question should be in the replay"


def test_language_comes_from_the_menu_not_the_fixture(client):
    game_id = client.post("/api/games", json={**NEW_GAME, "language": "pl"}).json()["game_id"]
    state = client.get(f"/api/games/{game_id}").json()
    assert state["language"] == "pl"


def test_the_region_never_overrides_the_language(client):
    """A Polish event played in English stays English.

    The recorded Polish run is the closest match on region and the furthest on
    language, and language is the one the player set.
    """
    game_id = client.post(
        "/api/games", json={"mode": "news", "region": "pl", "language": "en"}
    ).json()["game_id"]
    state = client.get(f"/api/games/{game_id}").json()
    assert state["language"] == "en"
    assert "Na podstawie" not in (state["source_note"] or "")


def test_news_mode_scores_and_carries_a_content_note(client):
    game_id = client.post(
        "/api/games",
        json={"mode": "news", "region": "pl", "language": "pl"},
    ).json()["game_id"]
    state = client.get(f"/api/games/{game_id}").json()
    assert state["mode"] == "news"
    assert state["region"] == "pl"

    state = _play(client, state)
    ending = client.get(f"/api/games/{game_id}/ending").json()
    assert isinstance(ending["match_score"], float)
    assert ending["canon"], "news endings compare against canon beats"


def test_unreachable_move_is_ignored(client):
    game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]
    state = client.get(f"/api/games/{game_id}").json()
    before = state["player_pos"]

    # (0, 0) is always the wall border.
    after = client.post(f"/api/games/{game_id}/move", json={"to": {"x": 0, "y": 0}}).json()
    assert after["player_pos"] == before


def test_locked_door_blocks_its_destination_until_unlocked(client):
    game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]
    state = client.get(f"/api/games/{game_id}").json()
    game_map = GameMap(**state["map"])
    assert game_map.doors, "the fixture maps have a gated destination"

    gate = game_map.doors[0]
    behind = [
        d
        for d in game_map.destinations
        if not path_to(game_map, Pos(**state["player_pos"]), _tile_of(game_map, d.key), [])
    ]
    assert behind, "at least one destination should start out gated"

    target = _tile_of(game_map, behind[0].key)
    after = client.post(f"/api/games/{game_id}/move", json={"to": target.model_dump()}).json()
    assert after["player_pos"] == state["player_pos"], "the gated destination is not walkable yet"
    assert gate.unlock_from not in after["unlocked"]


def test_unknown_game_is_a_404(client):
    res = client.get("/api/games/nope")
    assert res.status_code == 404
    assert res.json()["kind"] == "network"


def test_forced_error_surfaces_the_kind(client):
    client.post("/api/dev/force-error", json={"kind": "budget_exceeded"})
    res = client.post("/api/games", json=NEW_GAME)
    assert res.status_code == 429
    assert res.json()["kind"] == "budget_exceeded"
    # It fires exactly once.
    assert client.post("/api/games", json=NEW_GAME).status_code == 200


def test_an_unexpected_failure_still_answers_in_the_error_contract():
    """A bug must reach the error screen as an error, not as a blank page.

    FastAPI's own 500 body carries no `kind`, so the client would fall back to
    "cannot reach the server" for a server that answered perfectly well.
    """
    from fastapi.testclient import TestClient

    from app.main import app
    from app.storage.memory import MemoryStore

    def explode(self, uid):
        raise RuntimeError("something nobody wrote a handler for")

    original = MemoryStore.list_saved
    MemoryStore.list_saved = explode
    try:
        with TestClient(app, raise_server_exceptions=False) as raw:
            res = raw.get("/api/games")
    finally:
        MemoryStore.list_saved = original

    assert res.status_code == 500
    assert res.json() == {"kind": "generation_failed", "detail": "RuntimeError"}


def test_placeholder_image_is_deterministic_svg(client):
    a = client.get("/api/media/placeholder/moss/harbour.svg")
    b = client.get("/api/media/placeholder/moss/harbour.svg")
    assert a.status_code == 200
    assert a.headers["content-type"].startswith("image/svg+xml")
    assert a.text == b.text
    assert a.text != client.get("/api/media/placeholder/rust/harbour.svg").text
    assert client.get("/api/media/placeholder/neon/harbour.svg").status_code == 404


# ── the generated path ──────────────────────────────────────────────────


def _load_stream(client, game_id: str) -> list[dict]:
    with client.stream("GET", f"/api/games/{game_id}/stream") as res:
        lines = [line for line in res.iter_lines() if line.startswith("data:")]
    return [json.loads(line.removeprefix("data:")) for line in lines]


def test_a_generated_game_is_played_through_the_same_api(client, monkeypatch):
    """`LLM_MODE=fake` runs the real pipeline, so this covers what mock cannot."""
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]

    frames = _load_stream(client, game_id)
    assert [f["stage"] for f in frames[:-1]] == ["story", "map", "images", "music", "finishing"]
    assert frames[-1] == {"ready": True}

    state = client.get(f"/api/games/{game_id}").json()
    assert state["current_scene"]["location_id"] == "start"
    assert state["current_scene"]["image_url"]
    assert not state["choices"], "the opening scene is a SET OFF, not a decision"

    state = client.post(f"/api/games/{game_id}/set-off").json()
    assert state["view"] == "travel"

    state = _play(client, state)
    assert state["finished"] is True

    ending = client.get(f"/api/games/{game_id}/ending").json()
    assert ending["title"] and ending["summary"]
    assert len(ending["player"]) == len(state["beat_progress"])
    assert ending["match_score"] is None


def test_a_generated_opening_image_is_served_back(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]
    _load_stream(client, game_id)

    url = client.get(f"/api/games/{game_id}").json()["current_scene"]["image_url"]
    res = client.get(url)
    assert res.status_code == 200
    assert res.content.startswith(b"\x89PNG")
    assert client.get("/api/media/asset/nope.png").status_code == 404


def test_a_generation_failure_reaches_the_loading_screen(client, monkeypatch):
    from app.llm.fake import FakeLLM
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    monkeypatch.setattr(
        "app.pipeline.orchestrator.make_llm", lambda: FakeLLM(fail_stages=("plan",))
    )

    game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]
    frames = _load_stream(client, game_id)
    assert frames[-1]["kind"] == "generation_failed"
    # The game was never persisted, so the client cannot walk into a half-game.
    assert client.get(f"/api/games/{game_id}").status_code == 404


def test_the_budget_cap_is_checked_before_anything_generates(client, monkeypatch):
    """The cap is a precondition, not a post-hoc check: nothing is spent first."""
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    monkeypatch.setattr(settings, "monthly_budget_usd", 0.0)

    res = client.post("/api/games", json=NEW_GAME)
    assert res.status_code == 429
    assert res.json()["kind"] == "budget_exceeded"


def test_two_games_by_one_player_do_not_draw_the_same_style_card(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    cards = []
    for _ in range(4):
        game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]
        _load_stream(client, game_id)
        cards.append(client.get(f"/api/games/{game_id}").json()["style_card"])
    assert len({json.dumps(c, sort_keys=True) for c in cards}) == len(cards)


def test_a_player_who_outruns_the_scenes_waits_for_them(client, monkeypatch):
    """Scenes are written behind the loading screen, so a fast walk can beat them."""
    import asyncio

    from app.pipeline import live
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    real = live.fill_scenes

    async def slow(*args, **kwargs):
        await asyncio.sleep(0.4)
        return await real(*args, **kwargs)

    monkeypatch.setattr(live, "fill_scenes", slow)

    game_id = client.post("/api/games", json=NEW_GAME).json()["game_id"]
    _load_stream(client, game_id)
    state = client.post(f"/api/games/{game_id}/set-off").json()

    game_map = GameMap(**state["map"])
    first = game_map.destinations[0]
    state = client.post(
        f"/api/games/{game_id}/move", json={"to": _tile_of(game_map, first.key).model_dump()}
    ).json()

    assert state["view"] == "scene"
    assert state["current_scene"]["location_id"] == first.location_id
    assert state["choices"], "the scene the player waited for has to have choices"


def test_a_generated_news_game_is_played_and_scored(client, monkeypatch):
    """The whole News path through the real API, from a seeded pool."""
    import asyncio

    from app.settings import settings
    from app.storage import get_store
    from tests.test_news_mode import EVAL_CASES, make_event

    monkeypatch.setattr(settings, "llm_mode", "fake")
    store = get_store()
    pool = [
        make_event(title, ident=str(index))
        for index, (title, safety) in enumerate(EVAL_CASES.values())
        if safety == "allowed"
    ]
    for index, event in enumerate(pool):
        event.embedding = [1.0 if i == index else 0.0 for i in range(len(pool))]
    asyncio.run(store.put_pool("world", pool))

    created = client.post(
        "/api/games",
        json={"mode": "news", "region": "world", "language": "en"},
    )
    game_id = created.json()["game_id"]
    assert _load_stream(client, game_id)[-1] == {"ready": True}

    state = client.get(f"/api/games/{game_id}").json()
    assert state["mode"] == "news"
    assert state["source_note"], "a real-events disclaimer runs for the whole game"
    assert state["beat_progress"], "news games are scored against canon beats"

    state = client.post(f"/api/games/{game_id}/set-off").json()
    state = _play(client, state)
    assert state["finished"] is True

    ending = client.get(f"/api/games/{game_id}/ending").json()
    assert isinstance(ending["match_score"], float)
    assert ending["canon"], "the player can see what actually happened"
    assert ending["sources"], "and go and read it"


def test_an_exhausted_news_pool_is_a_friendly_error(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    res = client.post(
        "/api/games",
        json={"mode": "news", "region": "pl", "language": "pl"},
    )
    game_id = res.json()["game_id"]
    frames = _load_stream(client, game_id)
    assert frames[-1]["kind"] == "pool_empty"
    assert frames[-1]["detail"], "the message is shown to the player, so it must say something"


def _seed_world_pool(titles: list[str]) -> None:
    """A pool the API can serve, with vectors dedup can tell apart."""
    import asyncio

    from app.storage import get_store
    from tests.test_news_mode import make_event

    events = [make_event(title, ident=str(i)) for i, title in enumerate(titles)]
    for i, event in enumerate(events):
        event.embedding = [1.0 if j == i else 0.0 for j in range(len(events))]
    asyncio.run(get_store().put_pool("world", events))


def test_the_news_list_offers_stories_to_choose_from(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    _seed_world_pool(
        [
            "SpaceX lands a booster on the drone ship after night launch",
            "Brawl in the Sejm as opposition MPs storm the rostrum",
        ]
    )
    stories = client.get("/api/news", params={"region": "world"}).json()
    assert len(stories) == 2
    assert all(s["id"] and s["title"] for s in stories)
    assert all(s["safety_class"] != "blocked" for s in stories)


def test_mock_mode_offers_no_list_because_it_never_reaches_the_pool(client):
    """`picks_stories` tells the frontend this, so the menu skips the screen."""
    assert client.get("/api/config").json()["picks_stories"] is False
    assert client.get("/api/news", params={"region": "world"}).json() == []


def test_the_chosen_story_is_the_one_that_gets_played(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    titles = [
        "SpaceX lands a booster on the drone ship after night launch",
        "Brawl in the Sejm as opposition MPs storm the rostrum",
    ]
    _seed_world_pool(titles)
    stories = client.get("/api/news", params={"region": "world"}).json()
    wanted = stories[-1]

    created = client.post(
        "/api/games",
        json={"mode": "news", "region": "world", "language": "en", "event_id": wanted["id"]},
    )
    game_id = created.json()["game_id"]
    assert _load_stream(client, game_id)[-1] == {"ready": True}
    assert client.get(f"/api/games/{game_id}").json()["mode"] == "news"


def test_choosing_a_story_that_has_gone_is_a_friendly_error(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_mode", "fake")
    _seed_world_pool(["SpaceX lands a booster on the drone ship after night launch"])
    created = client.post(
        "/api/games",
        json={"mode": "news", "region": "world", "language": "en", "event_id": "not-there"},
    )
    frames = _load_stream(client, created.json()["game_id"])
    assert frames[-1]["kind"] == "pool_empty"
