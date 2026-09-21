"""The generator, held to the Phase 3 bar: nothing it produces is ever rejected."""

from random import Random

import pytest

from app.game.map import reachable_from
from app.models.game import Destination, Pos
from app.pipeline.map_validator import MAX_PATH, MAX_TOUR_SECONDS, validate_map
from app.pipeline.world_map import DoorSpec, build_map, generate_map

LAYOUTS = ("tight", "sprawling", "linear")


def dests(count: int) -> list[Destination]:
    return [
        Destination(key=key, location_id=f"loc-{key.lower()}", name=f"Room {key}")
        for key in "ABCDE"[:count]
    ]


def spec(count: int, locks: int) -> list[DoorSpec]:
    """Lock the last `locks` destinations behind the first one."""
    keys = [d.key for d in dests(count)]
    return [DoorSpec(gates=key, unlock_from=keys[0]) for key in keys[1:][-locks:]] if locks else []


def cases() -> list[tuple[int, int, int, str]]:
    """100 distinct requests spread over every layout, size and lock count."""
    out = []
    seed = 0
    while len(out) < 100:
        for layout in LAYOUTS:
            for count in (1, 2, 3, 4, 5):
                locks = min(seed % 3, max(0, count - 1))
                out.append((seed, count, locks, layout))
                seed += 1
    return out[:100]


def start_of(game_map) -> Pos:
    for y, row in enumerate(game_map.tiles):
        if "@" in row:
            return Pos(x=row.index("@"), y=y)
    raise AssertionError("generated map has no start")


def where(game_map, key: str) -> Pos:
    for y, row in enumerate(game_map.tiles):
        if key in row:
            return Pos(x=row.index(key), y=y)
    raise AssertionError(f"generated map has no '{key}'")


# ── The exit criterion ──────────────────────────────────────────────────


def test_a_hundred_generated_maps_are_valid_without_repair():
    cosmetic = 0
    for seed, count, locks, layout in cases():
        raw = generate_map(dests(count), spec(count, locks), layout=layout, rng=Random(seed))
        report = validate_map(raw)
        assert report.ok, (
            f"seed={seed} layout={layout} destinations={count} locks={locks}\n"
            f"{report.as_diagnostics()}\n" + "\n".join(raw.tiles)
        )
        cosmetic += bool(report.issues)
    # Cosmetic complaints are allowed; `build_map` retries past them.
    assert cosmetic <= 10, f"{cosmetic}/100 maps had a lock that gated nothing"


def test_every_generated_map_fits_the_walking_budget():
    for seed, count, locks, layout in cases()[:30]:
        game_map = build_map(dests(count), spec(count, locks), layout=layout, seed=seed)
        report = validate_map(game_map)
        assert max(report.first_visit_steps.values()) <= MAX_PATH
        assert report.tour_seconds <= MAX_TOUR_SECONDS


# ── Locks ───────────────────────────────────────────────────────────────


def test_a_locked_room_cannot_be_reached_until_its_key_is():
    for seed in range(20):
        game_map = build_map(
            dests(5), [DoorSpec(gates="E", unlock_from="A")], layout="tight", seed=seed
        )
        report = validate_map(game_map)
        assert report.unlock_order.index("A") < report.unlock_order.index("E")

        start, target = start_of(game_map), where(game_map, "E")
        assert (target.x, target.y) not in reachable_from(game_map, start, [])
        assert (target.x, target.y) in reachable_from(game_map, start, ["A"])


def test_two_locks_both_hold():
    game_map = build_map(
        dests(5),
        [DoorSpec(gates="D", unlock_from="A"), DoorSpec(gates="E", unlock_from="B")],
        layout="tight",
        seed=4,
    )
    report = validate_map(game_map)
    assert len(game_map.doors) == 2
    assert report.unlock_order.index("A") < report.unlock_order.index("D")
    assert report.unlock_order.index("B") < report.unlock_order.index("E")


def test_an_impossible_lock_still_produces_a_playable_map():
    # A room whose own key is inside it: unsatisfiable, so the bounded loop
    # gives up on the lock rather than on the game.
    game_map = build_map(dests(4), [DoorSpec(gates="C", unlock_from="C")], layout="tight", seed=2)
    report = validate_map(game_map)
    assert report.ok
    assert sorted(report.unlock_order) == ["A", "B", "C", "D"]


# ── Shape ───────────────────────────────────────────────────────────────


def test_the_same_seed_gives_the_same_map():
    first = build_map(dests(4), spec(4, 1), layout="tight", seed=99)
    second = build_map(dests(4), spec(4, 1), layout="tight", seed=99)
    assert first.tiles == second.tiles
    assert first.doors == second.doors


def test_different_seeds_give_different_maps():
    made = {tuple(build_map(dests(4), layout="tight", seed=s).tiles) for s in range(10)}
    assert len(made) == 10


def test_layouts_have_visibly_different_footprints():
    shapes = {layout: build_map(dests(5), layout=layout, seed=1) for layout in LAYOUTS}
    assert shapes["linear"].height < shapes["sprawling"].height
    assert len({(m.width, m.height) for m in shapes.values()}) > 1


def test_maps_are_cropped_to_what_is_walkable():
    game_map = build_map(dests(5), layout="tight", seed=6)
    assert any(tile != "#" for tile in game_map.tiles[1])
    assert any(row[1] != "#" for row in game_map.tiles)


def test_a_one_room_errand_is_a_legal_map():
    report = validate_map(build_map(dests(1), layout="tight", seed=0))
    assert report.ok
    assert report.unlock_order == ["A"]


def test_a_map_needs_somewhere_to_go():
    with pytest.raises(ValueError):
        generate_map([])


def test_a_mock_game_can_be_played_on_a_generated_map(monkeypatch):
    """The generator's route into the UI: same fixture story, new floor plan."""
    from app.llm.mock import build_game
    from app.models.game import NewGameRequest
    from app.pipeline.map_validator import gated_destinations
    from app.settings import settings

    monkeypatch.setattr(settings, "mock_map_source", "generated")
    state, _ = build_game(
        "phase3000000test",
        NewGameRequest(mode="idea", idea="a lighthouse", language="en"),
    )

    report = validate_map(state.map)
    assert report.ok, report.as_diagnostics()
    assert state.map.tiles[state.player_pos.y][state.player_pos.x] == "@"
    assert sorted(report.unlock_order) == [d.key for d in state.map.destinations]
    # The lock the fixture recorded survives the rebuild, gating the same room.
    assert [gated_destinations(state.map, d) for d in state.map.doors] == [["E"]]
