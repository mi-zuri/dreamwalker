"""Fixture grids for the validator and the deterministic repair loop.

Every grid here is 17x9 and derived from `BASE`, so each case differs from a
known-good map in exactly one way and the assertion names the defect.
"""

import json
from pathlib import Path

import pytest

from app.models.game import Destination, Door, GameMap, Pos
from app.pipeline.map_validator import (
    MAX_PATH,
    TILE_SECONDS,
    MapRepairError,
    repair_map,
    validate_map,
)

#: `C` sits behind the door at (7,2), which `A` unlocks.
BASE = [
    "#################",
    "#@.....#....C...#",
    "#......+........#",
    "#......#........#",
    "#......##########",
    "#...............#",
    "#..A........B...#",
    "#...............#",
    "#################",
]

DESTS = [
    Destination(key="A", location_id="loc-a", name="Yard"),
    Destination(key="B", location_id="loc-b", name="Shed"),
    Destination(key="C", location_id="loc-c", name="Attic"),
]

DOOR_C = Door(key="+", pos=Pos(x=7, y=2), unlock_from="A")


def make_map(tiles: list[str], doors: list[Door] | None = None, **overrides) -> GameMap:
    fields = {
        "width": len(tiles[0]),
        "height": len(tiles),
        "tiles": tiles,
        "destinations": DESTS,
        "doors": [] if doors is None else doors,
    }
    return GameMap(**{**fields, **overrides})


def swap(tiles: list[str], x: int, y: int, char: str) -> list[str]:
    rows = list(tiles)
    rows[y] = rows[y][:x] + char + rows[y][x + 1 :]
    return rows


def codes(game_map: GameMap, **kwargs) -> set[str]:
    return {issue.code for issue in validate_map(game_map, **kwargs).issues}


# ── Validation ──────────────────────────────────────────────────────────


def test_a_good_map_has_nothing_to_say():
    report = validate_map(make_map(BASE, [DOOR_C]))
    assert report.ok
    assert report.issues == []
    # C is only reachable after A, which is the whole point of the door.
    assert report.unlock_order == ["A", "B", "C"]
    assert report.tour_seconds > 0


def test_a_walled_off_destination_is_unreachable():
    sealed = swap(BASE, 7, 2, "#")
    report = validate_map(make_map(sealed))
    assert not report.ok
    assert [i.code for i in report.issues] == ["unreachable"]
    assert report.issues[0].dest_key == "C"
    assert report.unlock_order == ["A", "B"]


def test_a_key_locked_behind_its_own_door_is_a_deadlock():
    self_gated = Door(key="+", pos=Pos(x=7, y=2), unlock_from="C")
    report = validate_map(make_map(BASE, [self_gated]))
    assert not report.ok
    assert [i.code for i in report.issues] == ["deadlock"]
    assert report.issues[0].dest_key == "C"


def test_a_ragged_grid_is_not_rectangular():
    ragged = list(BASE)
    ragged[3] = ragged[3][:-1]
    assert "not_rectangular" in codes(make_map(ragged, [DOOR_C], width=17))


def test_a_hole_in_the_outer_wall_is_caught():
    leaky = swap(BASE, 8, 0, ".")
    assert "no_border" in codes(make_map(leaky, [DOOR_C]))


def test_a_map_with_no_start_cannot_be_walked():
    report = validate_map(make_map(swap(BASE, 1, 1, "."), [DOOR_C]))
    assert not report.ok
    assert [i.code for i in report.issues] == ["start_missing"]
    # Without a start there is nothing to measure, so no reachability noise.
    assert report.unlock_order == []


def test_two_starts_are_one_too_many():
    assert "start_duplicated" in codes(make_map(swap(BASE, 5, 7, "@"), [DOOR_C]))


def test_a_destination_missing_from_the_grid_is_reported():
    assert "destination_missing" in codes(make_map(swap(BASE, 12, 1, "."), [DOOR_C]))


def test_a_destination_appearing_twice_is_ambiguous():
    assert "destination_duplicated" in codes(make_map(swap(BASE, 5, 7, "B"), [DOOR_C]))


def test_a_stray_letter_is_not_terrain():
    assert "unknown_tile" in codes(make_map(swap(BASE, 5, 7, "Z"), [DOOR_C]))


def test_a_door_tile_nothing_owns_can_never_open():
    assert "door_orphaned" in codes(make_map(BASE))


def test_a_door_keyed_to_a_non_destination_is_rejected():
    bogus = Door(key="+", pos=Pos(x=7, y=2), unlock_from="Q")
    assert "door_unknown_unlock" in codes(make_map(BASE, [bogus]))


def test_a_door_record_pointing_at_floor_is_misplaced():
    stray = Door(key="+", pos=Pos(x=5, y=7), unlock_from="A")
    assert "door_misplaced" in codes(make_map(BASE, [DOOR_C, stray]))


def test_a_lock_that_gates_nothing_is_flagged_but_still_playable():
    # A second door out in the open: the map stays winnable, the lock is decor.
    open_ground = swap(BASE, 5, 7, "+")
    report = validate_map(
        make_map(open_ground, [DOOR_C, Door(key="+", pos=Pos(x=5, y=7), unlock_from="A")])
    )
    assert report.ok, "a pointless lock must not make the map unplayable"
    assert [i.code for i in report.issues] == ["door_decorative"]


def test_walks_longer_than_the_budget_are_rejected():
    assert "path_too_long" in codes(make_map(BASE, [DOOR_C]), max_path=3)


def test_a_tour_that_eats_the_clock_is_rejected():
    assert "tour_too_long" in codes(make_map(BASE, [DOOR_C]), max_tour_seconds=0.5)


def test_diagnostics_name_every_problem():
    report = validate_map(make_map(swap(BASE, 7, 2, "#")))
    text = report.as_diagnostics()
    assert "unreachable" in text and "[C]" in text


# ── Repair ──────────────────────────────────────────────────────────────

BROKEN = {
    "unreachable": (swap(BASE, 7, 2, "#"), []),
    "deadlock": (BASE, [Door(key="+", pos=Pos(x=7, y=2), unlock_from="C")]),
    "no_start": (swap(BASE, 1, 1, "."), [DOOR_C]),
    "two_starts": (swap(BASE, 5, 7, "@"), [DOOR_C]),
    "missing_dest": (swap(BASE, 12, 1, "."), [DOOR_C]),
    "duplicate_dest": (swap(BASE, 5, 7, "B"), [DOOR_C]),
    "leaky_border": (swap(BASE, 8, 0, "."), [DOOR_C]),
    "orphan_door": (BASE, []),
    "bogus_unlock": (BASE, [Door(key="+", pos=Pos(x=7, y=2), unlock_from="Q")]),
    "stray_tile": (swap(BASE, 5, 7, "Z"), [DOOR_C]),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_every_broken_grid_repairs_into_a_playable_one(name):
    tiles, doors = BROKEN[name]
    repaired, log = repair_map(make_map(tiles, doors))
    report = validate_map(repaired)
    assert report.ok, f"{name} still broken: {report.as_diagnostics()}"
    assert log, f"{name} was repaired silently"
    # Repair may re-route the map but never drops a location.
    assert [d.key for d in repaired.destinations] == ["A", "B", "C"]
    assert sorted(report.unlock_order) == ["A", "B", "C"]


def test_repair_is_deterministic():
    broken = make_map(swap(BASE, 7, 2, "#"))
    first, first_log = repair_map(broken)
    second, second_log = repair_map(broken)
    assert first.tiles == second.tiles
    assert first_log == second_log


def test_repairing_a_good_map_changes_nothing():
    good = make_map(BASE, [DOOR_C])
    repaired, log = repair_map(good)
    assert repaired.tiles == good.tiles
    assert repaired.doors == good.doors
    assert log == []


def test_a_ragged_grid_is_squared_off_not_truncated():
    ragged = list(BASE)
    ragged[6] = ragged[6][:-4]  # chops the right wall off the row holding B
    repaired, log = repair_map(make_map(ragged, [DOOR_C], width=17))
    assert all(len(row) == repaired.width for row in repaired.tiles)
    assert validate_map(repaired).ok
    assert any("squared off" in line for line in log)


def test_an_unusable_destination_key_is_renamed():
    dests = [DESTS[0], DESTS[1], DESTS[2].model_copy(update={"key": "#"})]
    repaired, log = repair_map(make_map(BASE, [DOOR_C], destinations=dests))
    assert validate_map(repaired).ok
    assert repaired.destinations[2].key not in ("#", "A", "B")
    assert any("not usable terrain" in line for line in log)


def test_a_solid_wall_grid_still_yields_a_game():
    solid = ["#" * 17] * 9
    repaired, log = repair_map(make_map(solid, []))
    report = validate_map(repaired)
    assert report.ok
    assert sorted(report.unlock_order) == ["A", "B", "C"]
    assert any("solid wall" in line for line in log)


def test_a_grid_too_small_to_play_is_refused_rather_than_mangled():
    with pytest.raises(MapRepairError):
        repair_map(make_map(["#####", "#@..#", "#####"]))


# ── The maps we actually ship ───────────────────────────────────────────

FIXTURES = sorted((Path(__file__).parent.parent / "app/fixtures/games").glob("*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_recorded_game_fixtures_hold_valid_maps(path):
    raw = json.loads(path.read_text())
    report = validate_map(GameMap.model_validate(raw["state"]["map"]))
    assert report.ok, report.as_diagnostics()
    assert report.first_visit_steps
    assert max(report.first_visit_steps.values()) <= MAX_PATH


#: The only way to `A` is all the way round; as the crow flies it is two tiles.
DETOUR = [
    "#################",
    "#@..............#",
    "###############.#",
    "#A..............#",
    "#################",
    "#################",
    "#################",
]


def test_a_long_way_round_is_given_a_shortcut():
    """Forced with a tight budget: the real limit is far above anything the
    generator produces, so this branch needs coaxing to run at all."""
    detour = make_map(DETOUR, destinations=DESTS[:1])
    assert validate_map(detour).first_visit_steps == {"A": 30}

    repaired, log = repair_map(detour, max_path=6)
    report = validate_map(repaired, max_path=6)
    assert report.ok, report.as_diagnostics()
    assert report.first_visit_steps["A"] == 2, "the shortcut should be the direct line"
    assert any("direct corridor" in line for line in log)


def test_a_tour_that_runs_over_the_clock_gets_shortcuts():
    # Generous per-room limit, tight tour limit, so only the tour check fires.
    budget = TILE_SECONDS * 24
    assert validate_map(make_map(BASE, [DOOR_C])).tour_seconds > budget

    repaired, log = repair_map(make_map(BASE, [DOOR_C]), max_path=10**6, max_tour_seconds=budget)
    report = validate_map(repaired, max_path=10**6, max_tour_seconds=budget)
    assert report.ok, report.as_diagnostics()
    assert any("direct corridor" in line for line in log)


def test_a_budget_no_layout_could_meet_is_refused():
    # `B` is 16 tiles away in a straight line; no amount of carving beats that.
    with pytest.raises(MapRepairError):
        repair_map(make_map(BASE, [DOOR_C]), max_path=8)
