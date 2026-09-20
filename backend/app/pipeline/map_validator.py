"""Map validation and deterministic repair.

A generated map is never trusted. `validate_map` is a pure function over the
grid that returns structured diagnostics; `repair_map` is a bounded,
deterministic fixer that always returns a map `validate_map` accepts. Together
they mean a bad layout can degrade the map but can never reach the player as
an error.

Both are generator-agnostic on purpose. They validate the procedural layouts
`world_map.py` produces today and would validate a model-authored grid
unchanged.
"""

from collections import deque
from typing import Literal

from pydantic import BaseModel, Field

from app.game.map import (
    DOOR,
    FLOOR,
    START,
    STEPS,
    WALL,
    path_to,
    reachable_from,
    tile_at,
)
from app.models.game import Destination, Door, GameMap, Pos

#: Seconds the client spends animating one tile of movement; must stay in step
#: with the 90ms interval in `web/src/components/game/TileMap.tsx`.
TILE_SECONDS = 0.09

#: Longest first-visit walk to any single destination, in tiles.
MAX_PATH = 120

#: Walking time for the whole tour of every destination. The game itself is
#: budgeted at 2-10 minutes, so walking may not eat more than a slice of it.
MAX_TOUR_SECONDS = 90.0

#: Tiles that mean something other than "this is a destination".
KNOWN_TILES = frozenset({WALL, FLOOR, DOOR, START})

#: Repair does at most this many connectivity passes. Each pass either removes
#: a door or carves a corridor, so it cannot loop.
MAX_REPAIR_ROUNDS = 32

IssueCode = Literal[
    "bad_dimensions",
    "not_rectangular",
    "no_border",
    "start_missing",
    "start_duplicated",
    "no_destinations",
    "destination_missing",
    "destination_duplicated",
    "destination_key_invalid",
    "unknown_tile",
    "door_misplaced",
    "door_orphaned",
    "door_duplicated",
    "door_unknown_unlock",
    "door_decorative",
    "unreachable",
    "deadlock",
    "path_too_long",
    "tour_too_long",
]


class MapIssue(BaseModel):
    """One thing wrong with a grid.

    `blocking` separates "this map is unplayable" from "this map is playable
    but sloppy". Only blocking issues trigger a regeneration or a repair;
    everything else is fed back as a hint and otherwise tolerated.
    """

    code: IssueCode
    detail: str
    blocking: bool = True
    dest_key: str | None = None
    pos: Pos | None = None


class MapReport(BaseModel):
    ok: bool = False
    issues: list[MapIssue] = Field(default_factory=list)
    #: Destination keys in the order they become reachable.
    unlock_order: list[str] = Field(default_factory=list)
    #: Shortest walk from the start to each destination, as first reached.
    first_visit_steps: dict[str, int] = Field(default_factory=dict)
    tour_steps: int = 0
    tour_seconds: float = 0.0

    @property
    def blocking_issues(self) -> list[MapIssue]:
        return [i for i in self.issues if i.blocking]

    def as_diagnostics(self) -> str:
        """Compact, structured feedback for a generator retry."""
        if not self.issues:
            return "map is valid"
        return "\n".join(
            f"- {i.code}"
            + (f" [{i.dest_key}]" if i.dest_key else "")
            + (f" at ({i.pos.x},{i.pos.y})" if i.pos else "")
            + f": {i.detail}"
            for i in self.issues
        )


# ── Grid helpers ────────────────────────────────────────────────────────


def _index(game_map: GameMap) -> dict[str, list[Pos]]:
    """Every character in the grid mapped to where it appears."""
    found: dict[str, list[Pos]] = {}
    for y, row in enumerate(game_map.tiles[: game_map.height]):
        for x, char in enumerate(row[: game_map.width]):
            found.setdefault(char, []).append(Pos(x=x, y=y))
    return found


def _sole(found: dict[str, list[Pos]], char: str) -> Pos | None:
    spots = found.get(char, [])
    return spots[0] if spots else None


def _unlock_waves(game_map: GameMap, start: Pos) -> tuple[list[str], dict[str, int]]:
    """Reach the start, open what that unlocks, reach again, until nothing new.

    Returns the unlock order and, per destination, the length of the walk that
    first reaches it - measured with the doors that were open at that moment,
    which is the walk the player actually takes.
    """
    unlocked: list[str] = []
    first_visit: dict[str, int] = {}
    found = _index(game_map)

    while True:
        reached = reachable_from(game_map, start, unlocked)
        wave: list[str] = []
        for dest in game_map.destinations:
            if dest.key in unlocked:
                continue
            spot = _sole(found, dest.key)
            if spot is None or (spot.x, spot.y) not in reached:
                continue
            wave.append(dest.key)
            first_visit[dest.key] = len(path_to(game_map, start, spot, unlocked))
        if not wave:
            return unlocked, first_visit
        unlocked.extend(wave)


def _greedy_tour(game_map: GameMap, start: Pos) -> tuple[int, list[str]]:
    """Walk to the nearest reachable destination, repeat. An honest lower bound
    on how much walking the player has to do."""
    found = _index(game_map)
    here = start
    unlocked: list[str] = []
    remaining = {d.key for d in game_map.destinations}
    total = 0
    order: list[str] = []

    while remaining:
        best: tuple[str, int, Pos] | None = None
        for key in sorted(remaining):
            spot = _sole(found, key)
            if spot is None:
                continue
            steps = path_to(game_map, here, spot, unlocked)
            if steps and (best is None or len(steps) < best[1]):
                best = (key, len(steps), spot)
        if best is None:
            break
        key, steps, spot = best
        total += steps
        order.append(key)
        remaining.discard(key)
        unlocked.append(key)
        here = spot
    return total, order


def _walled(game_map: GameMap, pos: Pos) -> GameMap:
    """The same map with one tile turned into a wall. Used to ask whether a
    door is actually load-bearing."""
    rows = list(game_map.tiles)
    row = rows[pos.y]
    rows[pos.y] = row[: pos.x] + WALL + row[pos.x + 1 :]
    return game_map.model_copy(update={"tiles": rows})


# ── Validation ──────────────────────────────────────────────────────────


def validate_map(
    game_map: GameMap,
    *,
    max_path: int = MAX_PATH,
    max_tour_seconds: float = MAX_TOUR_SECONDS,
) -> MapReport:
    """Check a grid without touching it. Pure, no I/O, fully unit-testable."""
    issues: list[MapIssue] = []
    found = _index(game_map)
    dest_keys = [d.key for d in game_map.destinations]

    # 1. Structure.
    if game_map.width < 5 or game_map.height < 5 or len(game_map.tiles) != game_map.height:
        issues.append(
            MapIssue(
                code="bad_dimensions",
                detail=f"declared {game_map.width}x{game_map.height}, "
                f"got {len(game_map.tiles)} rows",
            )
        )
    ragged = sorted({len(r) for r in game_map.tiles} - {game_map.width})
    if ragged:
        issues.append(
            MapIssue(
                code="not_rectangular",
                detail=f"rows must all be {game_map.width} chars; also saw {ragged}",
            )
        )

    gaps = _border_gaps(game_map)
    if gaps:
        issues.append(
            MapIssue(
                code="no_border",
                detail=f"{len(gaps)} non-wall tiles on the outer edge",
                pos=gaps[0],
            )
        )

    starts = found.get(START, [])
    if not starts:
        issues.append(MapIssue(code="start_missing", detail=f"no '{START}' tile"))
    elif len(starts) > 1:
        issues.append(
            MapIssue(
                code="start_duplicated",
                detail=f"{len(starts)} '{START}' tiles; there must be exactly one",
                pos=starts[1],
            )
        )

    if not game_map.destinations:
        issues.append(MapIssue(code="no_destinations", detail="the map declares no destinations"))

    seen_keys: set[str] = set()
    for dest in game_map.destinations:
        if len(dest.key) != 1 or dest.key in KNOWN_TILES or dest.key in seen_keys:
            issues.append(
                MapIssue(
                    code="destination_key_invalid",
                    detail=f"'{dest.key}' must be a single character, unique, and not "
                    f"one of {''.join(sorted(KNOWN_TILES))}",
                    dest_key=dest.key,
                )
            )
        seen_keys.add(dest.key)

        spots = found.get(dest.key, [])
        if not spots:
            issues.append(
                MapIssue(
                    code="destination_missing",
                    detail=f"'{dest.key}' ({dest.name}) does not appear in the grid",
                    dest_key=dest.key,
                )
            )
        elif len(spots) > 1:
            issues.append(
                MapIssue(
                    code="destination_duplicated",
                    detail=f"'{dest.key}' appears {len(spots)} times",
                    dest_key=dest.key,
                    pos=spots[1],
                )
            )

    for char, spots in sorted(found.items()):
        if char not in KNOWN_TILES and char not in dest_keys:
            issues.append(
                MapIssue(
                    code="unknown_tile",
                    detail=f"'{char}' is neither terrain nor a declared destination",
                    pos=spots[0],
                )
            )

    issues.extend(_door_issues(game_map, found, dest_keys))

    start = starts[0] if starts else None
    if start is None:
        return MapReport(ok=False, issues=issues)

    # 2-4. Reachability under the door fixpoint.
    unlock_order, first_visit = _unlock_waves(game_map, start)
    stuck = [d for d in game_map.destinations if d.key not in unlock_order]
    if stuck:
        wide_open = reachable_from(game_map, start, dest_keys)
        for dest in stuck:
            spot = _sole(found, dest.key)
            if spot is None:
                continue  # already reported as destination_missing
            if (spot.x, spot.y) in wide_open:
                issues.append(
                    MapIssue(
                        code="deadlock",
                        detail=f"'{dest.key}' sits behind a door whose key is behind it; "
                        f"unlock order stalled at {unlock_order or 'nothing'}",
                        dest_key=dest.key,
                        pos=spot,
                    )
                )
            else:
                issues.append(
                    MapIssue(
                        code="unreachable",
                        detail=f"'{dest.key}' is walled off from the start even with "
                        "every door open",
                        dest_key=dest.key,
                        pos=spot,
                    )
                )

    # 5. Walking budget.
    for key, steps in sorted(first_visit.items()):
        if steps > max_path:
            issues.append(
                MapIssue(
                    code="path_too_long",
                    detail=f"'{key}' is {steps} tiles from the start; the limit is {max_path}",
                    dest_key=key,
                )
            )
    tour_steps, _ = _greedy_tour(game_map, start)
    tour_seconds = round(tour_steps * TILE_SECONDS, 2)
    if tour_seconds > max_tour_seconds:
        issues.append(
            MapIssue(
                code="tour_too_long",
                detail=f"visiting every destination is {tour_steps} tiles "
                f"({tour_seconds}s of walking); the limit is {max_tour_seconds}s",
            )
        )

    issues.extend(_decorative_doors(game_map, dest_keys, start, found))

    return MapReport(
        ok=not any(i.blocking for i in issues),
        issues=issues,
        unlock_order=unlock_order,
        first_visit_steps=first_visit,
        tour_steps=tour_steps,
        tour_seconds=tour_seconds,
    )


def _border_gaps(game_map: GameMap) -> list[Pos]:
    gaps: list[Pos] = []
    for x in range(game_map.width):
        for y in (0, game_map.height - 1):
            pos = Pos(x=x, y=y)
            if tile_at(game_map, pos) != WALL:
                gaps.append(pos)
    for y in range(1, max(1, game_map.height - 1)):
        for x in (0, game_map.width - 1):
            pos = Pos(x=x, y=y)
            if tile_at(game_map, pos) != WALL:
                gaps.append(pos)
    return gaps


def _door_issues(
    game_map: GameMap, found: dict[str, list[Pos]], dest_keys: list[str]
) -> list[MapIssue]:
    issues: list[MapIssue] = []
    claimed: set[tuple[int, int]] = set()

    for door in game_map.doors:
        spot = (door.pos.x, door.pos.y)
        if spot in claimed:
            issues.append(
                MapIssue(
                    code="door_duplicated",
                    detail="two doors claim the same tile",
                    pos=door.pos,
                )
            )
            continue
        claimed.add(spot)

        if tile_at(game_map, door.pos) != DOOR:
            issues.append(
                MapIssue(
                    code="door_misplaced",
                    detail=f"door record points at '{tile_at(game_map, door.pos)}', not '{DOOR}'",
                    pos=door.pos,
                )
            )
        if door.unlock_from not in dest_keys:
            issues.append(
                MapIssue(
                    code="door_unknown_unlock",
                    detail=f"unlock_from '{door.unlock_from}' is not a destination key",
                    pos=door.pos,
                )
            )

    for spot in found.get(DOOR, []):
        if (spot.x, spot.y) not in claimed:
            issues.append(
                MapIssue(
                    code="door_orphaned",
                    detail=f"'{DOOR}' tile with no door record, so nothing can ever open it",
                    pos=spot,
                )
            )
    return issues


def gated_destinations(game_map: GameMap, door: Door) -> list[str]:
    """Which destinations this door actually stands between the player and.

    Answered by walling the door off and seeing who disappears, which works for
    any grid - including a hand-authored fixture whose door records never said
    what they were for.
    """
    found = _index(game_map)
    start = _sole(found, START)
    if start is None or tile_at(game_map, door.pos) != DOOR:
        return []
    keys = [d.key for d in game_map.destinations]
    behind = reachable_from(_walled(game_map, door.pos), start, keys)
    return [
        key
        for key in keys
        if (spot := _sole(found, key)) is not None and (spot.x, spot.y) not in behind
    ]


def _decorative_doors(
    game_map: GameMap, dest_keys: list[str], start: Pos, found: dict[str, list[Pos]]
) -> list[MapIssue]:
    """A door that gates nothing. Not a defect the player can see, but it means
    the generator wasted a lock, so it is worth telling the generator about."""
    issues: list[MapIssue] = []
    for door in game_map.doors:
        if tile_at(game_map, door.pos) != DOOR:
            continue
        if not gated_destinations(game_map, door):
            issues.append(
                MapIssue(
                    code="door_decorative",
                    detail="every destination stays reachable with this door walled off, "
                    "so the lock gates nothing",
                    blocking=False,
                    pos=door.pos,
                )
            )
    return issues


# ── Repair ──────────────────────────────────────────────────────────────


class MapRepairError(RuntimeError):
    """Raised when a grid is too degenerate to fix in place.

    Callers recover by generating a fresh map rather than by surfacing this,
    so it never reaches the player. See `world_map.build_map`.
    """


def repair_map(
    game_map: GameMap,
    *,
    max_path: int = MAX_PATH,
    max_tour_seconds: float = MAX_TOUR_SECONDS,
) -> tuple[GameMap, list[str]]:
    """Deterministically turn any grid into one `validate_map` accepts.

    The order matters: shape, then the border, then the special tiles, then
    doors, then connectivity, then the walking budget - each step assumes the
    earlier ones already hold. Nothing here is random, so the same broken map
    always repairs to the same playable map.
    """
    if game_map.width < 7 or game_map.height < 7:
        raise MapRepairError(f"{game_map.width}x{game_map.height} is too small to hold a game")

    log: list[str] = []
    destinations, remap = _sanitise_keys(game_map, log)
    grid = _normalise(game_map, remap, log)
    _scrub_unknown(grid, destinations, log)
    doors = _repair_doors(grid, game_map.doors, destinations, remap, log)

    _enforce_border(grid, log)
    _ensure_open_space(grid, log)
    start = _repair_start(grid, log)
    _repair_destinations(grid, destinations, start, log)

    doors = _repair_connectivity(grid, destinations, doors, start, log)
    _repair_walking_budget(
        grid, destinations, doors, start, log, max_path=max_path, max_tour=max_tour_seconds
    )

    repaired = _rebuild(grid, destinations, doors)
    report = validate_map(repaired, max_path=max_path, max_tour_seconds=max_tour_seconds)
    if not report.ok:
        raise MapRepairError(f"repair left blocking issues:\n{report.as_diagnostics()}")
    return repaired, log


def _rebuild(grid: list[list[str]], destinations: list[Destination], doors: list[Door]) -> GameMap:
    return GameMap(
        width=len(grid[0]),
        height=len(grid),
        tiles=["".join(row) for row in grid],
        destinations=destinations,
        doors=doors,
    )


def _sanitise_keys(game_map: GameMap, log: list[str]) -> tuple[list[Destination], dict[str, str]]:
    """Give every destination a unique, single-character, non-terrain key.

    A key that was merely *invalid* is remapped in the grid too, since its old
    character cannot have meant anything else. A key that was a *duplicate* is
    not: which of the two tiles belonged to which destination is unknowable, so
    the second one is simply re-placed later.
    """
    reserved = {
        d.key for d in game_map.destinations if len(d.key) == 1 and d.key not in KNOWN_TILES
    }
    pool = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in KNOWN_TILES and c not in reserved]

    used: set[str] = set()
    remap: dict[str, str] = {}
    fixed: list[Destination] = []

    for dest in game_map.destinations:
        key = dest.key
        if len(key) != 1 or key in KNOWN_TILES:
            key = pool.pop(0)
            remap[dest.key] = key
            log.append(f"destination key '{dest.key}' was not usable terrain, renamed to '{key}'")
        elif key in used:
            key = pool.pop(0)
            log.append(f"destination key '{dest.key}' was already taken, renamed to '{key}'")
        used.add(key)
        fixed.append(dest.model_copy(update={"key": key}))
    return fixed, remap


def _normalise(game_map: GameMap, remap: dict[str, str], log: list[str]) -> list[list[str]]:
    """Square the grid off: pad ragged rows, add missing ones, never truncate."""
    rows = list(game_map.tiles)
    width = max([game_map.width, *(len(r) for r in rows)]) if rows else game_map.width
    height = max(game_map.height, len(rows))

    # `len(rows) != height` belongs here as much as the rest: a grid that
    # declares nine rows and ships seven is padded below, and the repair log
    # is the only record of what was changed.
    if (
        width != game_map.width
        or height != game_map.height
        or len(rows) != height
        or any(len(r) != width for r in rows)
    ):
        log.append(f"grid squared off to {width}x{height}")

    grid = [[remap.get(c, c) for c in row.ljust(width, WALL)] for row in rows]
    while len(grid) < height:
        grid.append([WALL] * width)
    return grid


def _scrub_unknown(grid: list[list[str]], destinations: list[Destination], log: list[str]) -> None:
    """Turn characters that are neither terrain nor a declared destination into
    plain floor. They already behave as floor when walked, so leaving them in
    would just render as noise the player cannot interpret."""
    allowed = KNOWN_TILES | {d.key for d in destinations}
    strays: set[str] = set()
    for row in grid:
        for x, tile in enumerate(row):
            if tile not in allowed:
                strays.add(tile)
                row[x] = FLOOR
    if strays:
        log.append(f"cleared unrecognised tiles {sorted(strays)}")


def _enforce_border(grid: list[list[str]], log: list[str]) -> None:
    height, width = len(grid), len(grid[0])
    breached = 0
    for x in range(width):
        for y in (0, height - 1):
            if grid[y][x] != WALL:
                grid[y][x] = WALL
                breached += 1
    for y in range(1, height - 1):
        for x in (0, width - 1):
            if grid[y][x] != WALL:
                grid[y][x] = WALL
                breached += 1
    if breached:
        log.append(f"sealed {breached} tiles on the outer wall")


def _interior(grid: list[list[str]]) -> list[Pos]:
    return [Pos(x=x, y=y) for y in range(1, len(grid) - 1) for x in range(1, len(grid[0]) - 1)]


def _ensure_open_space(grid: list[list[str]], log: list[str]) -> None:
    """A grid of solid wall has nowhere to stand. Carve a room in the middle."""
    if any(grid[p.y][p.x] != WALL for p in _interior(grid)):
        return
    cy, cx = len(grid) // 2, len(grid[0]) // 2
    for y in range(max(1, cy - 2), min(len(grid) - 1, cy + 3)):
        for x in range(max(1, cx - 3), min(len(grid[0]) - 1, cx + 4)):
            grid[y][x] = FLOOR
    log.append("grid was solid wall; carved a starting room")


def _find(grid: list[list[str]], char: str) -> list[Pos]:
    return [
        Pos(x=x, y=y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == char
    ]


def _repair_start(grid: list[list[str]], log: list[str]) -> Pos:
    spots = _find(grid, START)
    for extra in spots[1:]:
        grid[extra.y][extra.x] = FLOOR
    if len(spots) > 1:
        log.append(f"removed {len(spots) - 1} duplicate start tiles")
    if spots:
        return spots[0]

    centre_y, centre_x = len(grid) // 2, len(grid[0]) // 2
    free = [p for p in _interior(grid) if grid[p.y][p.x] == FLOOR]
    spot = min(free, key=lambda p: (abs(p.y - centre_y) + abs(p.x - centre_x), p.y, p.x))
    grid[spot.y][spot.x] = START
    log.append(f"no start tile; placed one at ({spot.x},{spot.y})")
    return spot


def _open_set(grid: list[list[str]], start: Pos) -> set[tuple[int, int]]:
    """Every tile walkable from `start` when all doors are treated as open."""
    seen = {(start.x, start.y)}
    queue = deque([(start.x, start.y)])
    height, width = len(grid), len(grid[0])
    while queue:
        x, y = queue.popleft()
        for dx, dy in STEPS:
            nxt = (x + dx, y + dy)
            if nxt in seen or not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            if grid[nxt[1]][nxt[0]] == WALL:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _repair_destinations(
    grid: list[list[str]], destinations: list[Destination], start: Pos, log: list[str]
) -> None:
    for dest in destinations:
        spots = _find(grid, dest.key)
        for extra in spots[1:]:
            grid[extra.y][extra.x] = FLOOR
        if len(spots) > 1:
            log.append(f"'{dest.key}' appeared {len(spots)} times; kept the first")
        if spots:
            continue

        spot = _free_tile(grid, start)
        grid[spot.y][spot.x] = dest.key
        log.append(f"'{dest.key}' ({dest.name}) was missing; placed it at ({spot.x},{spot.y})")


def _free_tile(grid: list[list[str]], start: Pos) -> Pos:
    """The plain floor tile furthest from the start, carving one if need be."""
    reachable = _open_set(grid, start)
    free = [
        p
        for p in _interior(grid)
        if grid[p.y][p.x] == FLOOR and (p.x, p.y) in reachable and (p.x, p.y) != (start.x, start.y)
    ]
    if free:
        return max(free, key=lambda p: (abs(p.y - start.y) + abs(p.x - start.x), p.y, p.x))

    # Nowhere to stand: push one tile out from the edge of the open region.
    for pos in _interior(grid):
        if grid[pos.y][pos.x] != WALL:
            continue
        if any((pos.x + dx, pos.y + dy) in reachable for dx, dy in STEPS):
            grid[pos.y][pos.x] = FLOOR
            return pos
    raise MapRepairError("no room left in the grid to place a destination")


def _repair_doors(
    grid: list[list[str]],
    doors: list[Door],
    destinations: list[Destination],
    remap: dict[str, str],
    log: list[str],
) -> list[Door]:
    """Drop doors that cannot mean anything, and erase locks nothing owns."""
    height, width = len(grid), len(grid[0])
    keys = {d.key for d in destinations}
    specials = keys | {START}
    kept: list[Door] = []
    claimed: set[tuple[int, int]] = set()

    for door in doors:
        unlock_from = remap.get(door.unlock_from, door.unlock_from)
        spot = (door.pos.x, door.pos.y)
        reason = None
        if not (0 < door.pos.x < width - 1 and 0 < door.pos.y < height - 1):
            reason = "off the grid or on the outer wall"
        elif spot in claimed:
            reason = "a second door on the same tile"
        elif unlock_from not in keys:
            reason = f"unlock_from '{door.unlock_from}' is not a destination"
        elif grid[door.pos.y][door.pos.x] in specials:
            reason = f"it sits on '{grid[door.pos.y][door.pos.x]}'"

        if reason:
            on_grid = 0 <= door.pos.y < height and 0 <= door.pos.x < width
            # A tile an earlier door already claimed is not this one's to
            # erase. Dropping the duplicate used to take the lock with it,
            # which left the kept record pointing at floor and made the
            # repair - the thing that is supposed to always succeed - throw.
            owned = spot in claimed
            if on_grid and not owned and grid[door.pos.y][door.pos.x] == DOOR:
                grid[door.pos.y][door.pos.x] = FLOOR
            log.append(f"dropped door at ({door.pos.x},{door.pos.y}): {reason}")
            continue

        claimed.add(spot)
        grid[door.pos.y][door.pos.x] = DOOR
        kept.append(door.model_copy(update={"unlock_from": unlock_from}))

    for pos in _find(grid, DOOR):
        if (pos.x, pos.y) not in claimed:
            grid[pos.y][pos.x] = FLOOR
            log.append(f"unlocked orphan door at ({pos.x},{pos.y}) that nothing could open")
    return kept


def _carve_route(grid: list[list[str]], start: Pos, goal: set[tuple[int, int]]) -> list[Pos]:
    """Shortest route from `start` to any goal tile, tunnelling through walls
    but never through the outer wall or an existing door."""
    height, width = len(grid), len(grid[0])
    origin = (start.x, start.y)
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    seen = {origin}
    queue = deque([origin])

    while queue:
        cur = queue.popleft()
        if cur != origin and cur in goal:
            route: list[Pos] = []
            step = cur
            while step != origin:
                route.append(Pos(x=step[0], y=step[1]))
                step = prev[step]
            return list(reversed(route))
        for dx, dy in STEPS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in seen or not (0 < nxt[0] < width - 1 and 0 < nxt[1] < height - 1):
                continue
            if grid[nxt[1]][nxt[0]] == DOOR:
                continue
            seen.add(nxt)
            prev[nxt] = cur
            queue.append(nxt)
    return []


def _carve(grid: list[list[str]], route: list[Pos]) -> int:
    carved = 0
    for pos in route:
        if grid[pos.y][pos.x] == WALL:
            grid[pos.y][pos.x] = FLOOR
            carved += 1
    return carved


def _carve_line(grid: list[list[str]], a: Pos, b: Pos) -> int:
    """An L-shaped corridor: horizontal first, then vertical."""
    route = [Pos(x=x, y=a.y) for x in range(min(a.x, b.x), max(a.x, b.x) + 1)]
    route += [Pos(x=b.x, y=y) for y in range(min(a.y, b.y), max(a.y, b.y) + 1)]
    inside = [p for p in route if 0 < p.x < len(grid[0]) - 1 and 0 < p.y < len(grid) - 1]
    return _carve(grid, inside)


def _repair_connectivity(
    grid: list[list[str]],
    destinations: list[Destination],
    doors: list[Door],
    start: Pos,
    log: list[str],
) -> list[Door]:
    """Make every destination reachable in turn.

    Each round fixes the closest still-unreachable destination and then starts
    over, because opening one route often unblocks several. A round either
    removes a door or carves a corridor, so progress is monotonic and the loop
    is bounded.
    """
    keys = [d.key for d in destinations]

    for _ in range(MAX_REPAIR_ROUNDS):
        game_map = _rebuild(grid, destinations, doors)
        unlocked, _ = _unlock_waves(game_map, start)
        stuck = [k for k in keys if k not in unlocked]
        if not stuck:
            return doors

        found = _index(game_map)
        # Deterministic order: nearest first with every door held open.
        candidates = [(key, spot) for key in stuck if (spot := _sole(found, key)) is not None]
        if not candidates:
            return doors
        key, spot = min(
            candidates,
            key=lambda c: (len(path_to(game_map, start, c[1], keys)) or 10**6, c[0]),
        )

        blocked_by = _first_locked_door(game_map, start, spot, keys, unlocked, doors)
        if blocked_by is not None:
            doors = [d for d in doors if d is not blocked_by]
            grid[blocked_by.pos.y][blocked_by.pos.x] = FLOOR
            log.append(
                f"unlocked the door at ({blocked_by.pos.x},{blocked_by.pos.y}) - its key "
                f"'{blocked_by.unlock_from}' was itself behind it"
            )
            continue

        reached = reachable_from(game_map, start, unlocked)
        route = _carve_route(grid, spot, reached)
        carved = _carve(grid, route) if route else _carve_line(grid, spot, start)
        log.append(f"carved {carved} tiles to reach '{key}'")

    raise MapRepairError("connectivity repair did not converge")


def _first_locked_door(
    game_map: GameMap,
    start: Pos,
    target: Pos,
    keys: list[str],
    unlocked: list[str],
    doors: list[Door],
) -> Door | None:
    """The door standing between the start and `target` when everything else is
    already as open as it will get."""
    route = path_to(game_map, start, target, keys)
    by_pos = {(d.pos.x, d.pos.y): d for d in doors}
    for step in route:
        door = by_pos.get((step.x, step.y))
        if door is not None and door.unlock_from not in unlocked:
            return door
    return None


def _repair_walking_budget(
    grid: list[list[str]],
    destinations: list[Destination],
    doors: list[Door],
    start: Pos,
    log: list[str],
    *,
    max_path: int,
    max_tour: float,
) -> None:
    """Straight corridors from the start bound every walk by width + height,
    which is comfortably inside both limits on any grid we generate."""
    for _ in range(MAX_REPAIR_ROUNDS):
        game_map = _rebuild(grid, destinations, doors)
        report = validate_map(game_map, max_path=max_path, max_tour_seconds=max_tour)
        over = [i for i in report.issues if i.code in ("path_too_long", "tour_too_long")]
        if not over:
            return

        found = _index(game_map)
        targets = (
            [i.dest_key for i in over if i.dest_key]
            if any(i.code == "path_too_long" for i in over)
            else [d.key for d in destinations]
        )
        carved = 0
        for key in targets:
            spot = _sole(found, key)
            if spot is not None:
                carved += _carve_line(grid, start, spot)
        log.append(f"walking budget exceeded; carved {carved} tiles of direct corridor")
        if not carved:
            return

    raise MapRepairError("walking-budget repair did not converge")
