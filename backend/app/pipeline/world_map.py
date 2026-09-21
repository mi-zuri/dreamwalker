"""Map generation.

The grid is built procedurally, not by a model. The story decides *what* the
locations are, how many there are and which one gates which - that is the part
that carries meaning, and it comes in as arguments. The arrangement of rooms
and corridors carries none: at 53x27 monospace characters, one valid layout
reads exactly like another, and asking a model to draw one would add seconds of
latency and a grid that fails validation more often than not.

So generation is deterministic, instant, free, and valid by construction:
rooms are carved one per lattice cell, joined along a random spanning tree, and
a gated room is always a leaf whose single corridor carries the lock. The
validator still runs over the result - see `map_validator` - because "valid by
construction" is a claim worth checking, and because the same validator has to
hold for any future generator.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from typing import Literal

from app.game.map import DOOR, FLOOR, START, WALL
from app.models.game import Destination, Door, GameMap, Pos
from app.pipeline.map_validator import MapRepairError, repair_map, validate_map

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 53
DEFAULT_HEIGHT = 27

#: One generation plus two retries, then deterministic repair - the bounded
#: loop from the design. Retries are free here, so this is about shaking off a
#: layout with a lock that gates nothing rather than about correctness.
MAX_GENERATION_ATTEMPTS = 3

#: How many times to reshuffle the spanning tree looking for enough leaves to
#: hang the locked rooms off.
MAX_TREE_ATTEMPTS = 24

#: A coarse shape hint. Phase 4 threads this off the style card so a noir has a
#: different footprint from a folk tale.
Layout = Literal["tight", "sprawling", "linear"]

_LATTICE: dict[Layout, dict[int, tuple[int, int]]] = {
    "tight": {2: (2, 1), 3: (3, 1), 4: (2, 2), 5: (3, 2), 6: (3, 2)},
    "sprawling": {2: (2, 1), 3: (3, 1), 4: (2, 2), 5: (3, 2), 6: (3, 2)},
    "linear": {2: (2, 1), 3: (3, 1), 4: (4, 1), 5: (5, 1), 6: (6, 1)},
}

#: Per layout: how much of its cell a room fills (low, high), and hard caps on
#: width and height. Sizing by fraction rather than by a flat cap is what keeps
#: a map from leaving wide dead bands of wall around the edges.
_ROOM_SHAPE: dict[Layout, tuple[float, float, int, int]] = {
    "tight": (0.45, 0.70, 11, 7),
    "sprawling": (0.60, 0.85, 17, 11),
    "linear": (0.40, 0.75, 9, 11),
}
_LOOP_CHANCE: dict[Layout, float] = {"tight": 0.35, "sprawling": 0.2, "linear": 0.0}


#: How the story's pacing reads as a floor plan. Phase 4 hands the style card's
#: pacing axis straight to `build_map`; anything unrecognised falls back to a
#: middling footprint.
_LAYOUT_FOR_PACING: dict[str, Layout] = {
    "slow_burn": "sprawling",
    "staccato": "tight",
    "escalating": "linear",
}


def layout_for(pacing: str) -> Layout:
    return _LAYOUT_FOR_PACING.get(pacing, "tight")


@dataclass(frozen=True)
class DoorSpec:
    """`gates` can only be entered once `unlock_from` has been visited."""

    gates: str
    unlock_from: str


@dataclass(frozen=True)
class _Room:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def centre(self) -> Pos:
        return Pos(x=(self.x0 + self.x1) // 2, y=(self.y0 + self.y1) // 2)

    def holds(self, x: int, y: int) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


# ── Public API ──────────────────────────────────────────────────────────


def build_map(
    destinations: Sequence[Destination],
    doors: Sequence[DoorSpec] = (),
    *,
    layout: Layout = "tight",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    seed: int | None = None,
) -> GameMap:
    """Generate, validate, and if need be repair. Always returns a valid map.

    A candidate with only cosmetic complaints is kept as a fallback and
    returned if no later attempt comes back clean, so retries can only improve
    the result.
    """
    fallback: GameMap | None = None
    candidate: GameMap | None = None

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        rng = Random(seed * 1000 + attempt) if seed is not None else Random()
        candidate = generate_map(
            destinations, doors, layout=layout, width=width, height=height, rng=rng
        )
        report = validate_map(candidate)
        if not report.issues:
            return candidate
        if report.ok and fallback is None:
            fallback = candidate
        logger.info("map attempt %d rejected:\n%s", attempt + 1, report.as_diagnostics())

    if fallback is not None:
        return fallback

    assert candidate is not None
    try:
        repaired, log = repair_map(candidate)
    except MapRepairError:
        # Last resort: no locks at all, which makes the layout a plain tree.
        plain = generate_map(
            destinations, (), layout=layout, width=width, height=height, rng=Random(seed or 0)
        )
        repaired, log = repair_map(plain)
    logger.warning("map repaired deterministically: %s", "; ".join(log))
    return repaired


def generate_map(
    destinations: Sequence[Destination],
    doors: Sequence[DoorSpec] = (),
    *,
    layout: Layout = "tight",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    rng: Random | None = None,
) -> GameMap:
    """One raw candidate. Not validated - `build_map` is the supported entry."""
    if not destinations:
        raise ValueError("a map needs at least one destination")
    rng = rng or Random()

    rooms_needed = len(destinations) + 1  # one per destination, plus the start
    cols, rows = _LATTICE[layout].get(rooms_needed, (3, 2))
    grid = [[WALL] * width for _ in range(height)]

    cells = _snake(cols, rows)[:rooms_needed]
    rooms = {
        cell: _carve_room(grid, cell, cols, rows, width, height, layout, rng) for cell in cells
    }

    gated = {spec.gates for spec in doors}
    tree, leaves = _spanning_tree(cells, rng, len(gated))
    placement = _assign(cells, leaves, destinations, gated, rng)

    door_tiles = _join(grid, tree, rooms, placement, gated, rng)
    _add_loops(grid, cells, tree, rooms, placement, gated, layout, rng)

    for cell, key in placement.items():
        centre = rooms[cell].centre
        grid[centre.y][centre.x] = key

    built_doors = [
        Door(key=DOOR, pos=door_tiles[spec.gates], unlock_from=spec.unlock_from)
        for spec in doors
        if spec.gates in door_tiles
    ]
    for door in built_doors:
        grid[door.pos.y][door.pos.x] = DOOR

    grid, dx, dy = _crop(grid)
    return GameMap(
        width=len(grid[0]),
        height=len(grid),
        tiles=["".join(row) for row in grid],
        destinations=list(destinations),
        doors=[
            door.model_copy(update={"pos": Pos(x=door.pos.x - dx, y=door.pos.y - dy)})
            for door in built_doors
        ],
    )


def _crop(grid: list[list[str]]) -> tuple[list[list[str]], int, int]:
    """Trim the map down to what is actually walkable, plus one ring of wall.

    Rooms are placed inside lattice cells with slack, so a raw grid usually
    carries dead bands of wall around the edge. The travel view scales the
    whole grid to fit, so trimming them is free resolution.
    """
    used = [(x, y) for y, row in enumerate(grid) for x, t in enumerate(row) if t != WALL]
    if not used:
        return grid, 0, 0
    x0 = min(x for x, _ in used) - 1
    x1 = max(x for x, _ in used) + 1
    y0 = min(y for _, y in used) - 1
    y1 = max(y for _, y in used) + 1
    return [row[x0 : x1 + 1] for row in grid[y0 : y1 + 1]], x0, y0


# ── Layout ──────────────────────────────────────────────────────────────


def _snake(cols: int, rows: int) -> list[tuple[int, int]]:
    """Lattice cells in boustrophedon order, so any prefix stays contiguous and
    therefore always has a spanning tree."""
    order: list[tuple[int, int]] = []
    for cy in range(rows):
        span = range(cols) if cy % 2 == 0 else reversed(range(cols))
        order.extend((cx, cy) for cx in span)
    return order


def _bounds(cell: tuple[int, int], cols: int, rows: int, width: int, height: int):
    """The interior slice of the grid this lattice cell owns."""
    cx, cy = cell
    span_w = (width - 2) // cols
    span_h = (height - 2) // rows
    x0 = 1 + cx * span_w
    y0 = 1 + cy * span_h
    x1 = width - 2 if cx == cols - 1 else x0 + span_w - 1
    y1 = height - 2 if cy == rows - 1 else y0 + span_h - 1
    return x0, y0, x1, y1


def _centred(rng: Random, slack: int) -> int:
    """An offset in [0, slack], biased towards the middle of the range."""
    if slack <= 0:
        return 0
    return (rng.randint(0, slack) + rng.randint(0, slack)) // 2


def _carve_room(
    grid: list[list[str]],
    cell: tuple[int, int],
    cols: int,
    rows: int,
    width: int,
    height: int,
    layout: Layout,
    rng: Random,
) -> _Room:
    """A rectangle with at least one wall tile of margin inside its own cell, so
    neighbouring rooms can never touch."""
    x0, y0, x1, y1 = _bounds(cell, cols, rows, width, height)
    low, high, cap_w, cap_h = _ROOM_SHAPE[layout]
    avail_w, avail_h = x1 - x0 - 1, y1 - y0 - 1
    room_w = max(3, min(cap_w, avail_w, int(avail_w * rng.uniform(low, high))))
    room_h = max(3, min(cap_h, avail_h, int(avail_h * rng.uniform(low, high))))

    rx = x0 + 1 + _centred(rng, avail_w - room_w)
    ry = y0 + 1 + _centred(rng, avail_h - room_h)
    room = _Room(rx, ry, min(rx + room_w - 1, x1 - 1), min(ry + room_h - 1, y1 - 1))

    for y in range(room.y0, room.y1 + 1):
        for x in range(room.x0, room.x1 + 1):
            grid[y][x] = FLOOR
    return room


def _adjacent(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def _root(parent: dict, cell: tuple[int, int]) -> tuple[int, int]:
    """Union-find lookup with path halving."""
    while parent[cell] != cell:
        parent[cell] = parent[parent[cell]]
        cell = parent[cell]
    return cell


def _spanning_tree(
    cells: list[tuple[int, int]], rng: Random, gated_count: int
) -> tuple[list[tuple[tuple[int, int], tuple[int, int]]], list[tuple[int, int]]]:
    """A random spanning tree with enough leaves to hang every locked room off.

    Leaves are what make a lock honest: a leaf has exactly one corridor, so
    putting the door on that corridor is the only way in by construction.
    """
    edges = [(a, b) for i, a in enumerate(cells) for b in cells[i + 1 :] if _adjacent(a, b)]
    best: tuple[list, list] | None = None

    for _ in range(MAX_TREE_ATTEMPTS):
        shuffled = edges[:]
        rng.shuffle(shuffled)
        parent = {c: c for c in cells}

        tree: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for a, b in shuffled:
            ra, rb = _root(parent, a), _root(parent, b)
            if ra != rb:
                parent[ra] = rb
                tree.append((a, b))

        degree = {c: 0 for c in cells}
        for a, b in tree:
            degree[a] += 1
            degree[b] += 1
        leaves = [c for c in cells if degree[c] == 1]

        if best is None or len(leaves) > len(best[1]):
            best = (tree, leaves)
        if len(leaves) >= gated_count + 1:
            return tree, leaves

    assert best is not None
    return best


def _assign(
    cells: list[tuple[int, int]],
    leaves: list[tuple[int, int]],
    destinations: Sequence[Destination],
    gated: set[str],
    rng: Random,
) -> dict[tuple[int, int], str]:
    """Locked destinations go to leaf cells; the start avoids them."""
    free = cells[:]
    placement: dict[tuple[int, int], str] = {}

    usable = [c for c in leaves if c in free]
    rng.shuffle(usable)
    for key in sorted(gated):
        if not usable:
            break
        cell = usable.pop()
        placement[cell] = key
        free.remove(cell)

    rest = [d.key for d in destinations if d.key not in placement.values()]
    rng.shuffle(free)
    # Prefer a non-leaf cell for the start so it is not itself tucked away.
    start_cell = next((c for c in free if c not in leaves), free[0])
    placement[start_cell] = START
    free.remove(start_cell)

    for cell, key in zip(free, rest, strict=False):
        placement[cell] = key
    return placement


# ── Corridors ───────────────────────────────────────────────────────────


def _corridor(a: _Room, b: _Room, rng: Random) -> list[Pos]:
    """An L-shaped path from inside room `a` to inside room `b`.

    Both segments stay within the two cells the rooms occupy, which is what
    keeps a corridor from ever cutting through a third room and quietly
    bypassing its lock.
    """
    horizontal_first = abs(a.centre.x - b.centre.x) >= abs(a.centre.y - b.centre.y)
    if horizontal_first:
        y = rng.randint(a.y0, a.y1)
        bend_x = rng.randint(b.x0, b.x1)
        end_y = rng.randint(b.y0, b.y1)
        start_x = rng.randint(a.x0, a.x1)
        step = 1 if bend_x >= start_x else -1
        path = [Pos(x=x, y=y) for x in range(start_x, bend_x + step, step)]
        step = 1 if end_y >= y else -1
        path += [Pos(x=bend_x, y=py) for py in range(y + step, end_y + step, step)]
    else:
        x = rng.randint(a.x0, a.x1)
        bend_y = rng.randint(b.y0, b.y1)
        end_x = rng.randint(b.x0, b.x1)
        start_y = rng.randint(a.y0, a.y1)
        step = 1 if bend_y >= start_y else -1
        path = [Pos(x=x, y=y) for y in range(start_y, bend_y + step, step)]
        step = 1 if end_x >= x else -1
        path += [Pos(x=px, y=bend_y) for px in range(x + step, end_x + step, step)]
    return path


def _dig(grid: list[list[str]], path: Sequence[Pos]) -> None:
    for pos in path:
        if grid[pos.y][pos.x] == WALL:
            grid[pos.y][pos.x] = FLOOR


def _join(
    grid: list[list[str]],
    tree: Sequence[tuple[tuple[int, int], tuple[int, int]]],
    rooms: dict[tuple[int, int], _Room],
    placement: dict[tuple[int, int], str],
    gated: set[str],
    rng: Random,
) -> dict[str, Pos]:
    """Carve every tree edge, and note where each locked room's door goes."""
    door_tiles: dict[str, Pos] = {}

    for a, b in tree:
        # Always carve away from the locked room, so the path's first tile
        # outside it is the tile that seals it.
        if placement.get(a) in gated:
            source, target = a, b
        elif placement.get(b) in gated:
            source, target = b, a
        else:
            source, target = a, b

        path = _corridor(rooms[source], rooms[target], rng)
        _dig(grid, path)

        key = placement.get(source)
        if key in gated:
            room = rooms[source]
            outside = next((p for p in path if not room.holds(p.x, p.y)), None)
            if outside is not None:
                door_tiles[key] = outside
    return door_tiles


def _add_loops(
    grid: list[list[str]],
    cells: Sequence[tuple[int, int]],
    tree: Sequence[tuple[tuple[int, int], tuple[int, int]]],
    rooms: dict[tuple[int, int], _Room],
    placement: dict[tuple[int, int], str],
    gated: set[str],
    layout: Layout,
    rng: Random,
) -> None:
    """Extra corridors so the map is not a bare tree. Never near a locked room,
    which would hand the player a way around its door."""
    chance = _LOOP_CHANCE[layout]
    in_tree = {frozenset(edge) for edge in tree}
    for i, a in enumerate(cells):
        for b in cells[i + 1 :]:
            if not _adjacent(a, b) or frozenset((a, b)) in in_tree:
                continue
            if placement.get(a) in gated or placement.get(b) in gated:
                continue
            if rng.random() < chance:
                _dig(grid, _corridor(rooms[a], rooms[b], rng))
