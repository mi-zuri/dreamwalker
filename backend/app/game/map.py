"""Pure tile-grid logic.

Mirrors `web/src/game/map.ts` exactly: the client animates movement locally,
but the server is authoritative, so both sides must agree on what is walkable.
No I/O, no settings, no models beyond the game schema - Phase 3's validator
builds on top of this.
"""

from collections import deque

from app.models.game import Destination, Door, GameMap, Pos

WALL = "#"
FLOOR = "."
DOOR = "+"
START = "@"

#: Von Neumann neighbourhood, in the same order as the TypeScript port.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def tile_at(game_map: GameMap, pos: Pos) -> str:
    """Anything outside the grid - or off the end of a ragged row - is a wall.

    Declared `width`/`height` are not trusted to match `tiles`, because this
    also runs over unvalidated, freshly generated grids.
    """
    if not (0 <= pos.y < game_map.height and 0 <= pos.x < game_map.width):
        return WALL
    if pos.y >= len(game_map.tiles):
        return WALL
    row = game_map.tiles[pos.y]
    return row[pos.x] if pos.x < len(row) else WALL


def destination_at(game_map: GameMap, pos: Pos) -> Destination | None:
    char = tile_at(game_map, pos)
    return next((d for d in game_map.destinations if d.key == char), None)


def door_at(game_map: GameMap, pos: Pos) -> Door | None:
    return next((d for d in game_map.doors if d.pos.x == pos.x and d.pos.y == pos.y), None)


def is_walkable(game_map: GameMap, pos: Pos, unlocked: list[str]) -> bool:
    """Not a wall, and - for a door - its prerequisite destination is reached."""
    char = tile_at(game_map, pos)
    if char == WALL:
        return False
    if char == DOOR:
        door = door_at(game_map, pos)
        return door is None or door.unlock_from in unlocked
    return True


def reachable_from(game_map: GameMap, start: Pos, unlocked: list[str]) -> set[tuple[int, int]]:
    """Every tile walkable from `start`, honouring locked doors."""
    seen = {(start.x, start.y)}
    queue = deque([(start.x, start.y)])
    while queue:
        x, y = queue.popleft()
        for dx, dy in STEPS:
            nxt = (x + dx, y + dy)
            if nxt in seen or not is_walkable(game_map, Pos(x=nxt[0], y=nxt[1]), unlocked):
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def path_to(game_map: GameMap, start: Pos, target: Pos, unlocked: list[str]) -> list[Pos]:
    """Shortest walkable path, including `target` and excluding `start`.

    Empty when the target is unreachable, which is how the server rejects a
    move without having to trust anything the client sent.
    """
    if (start.x, start.y) == (target.x, target.y):
        return []
    if not is_walkable(game_map, target, unlocked):
        return []

    goal = (target.x, target.y)
    origin = (start.x, start.y)
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    seen = {origin}
    queue = deque([origin])

    while queue:
        cur = queue.popleft()
        for dx, dy in STEPS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in seen or not is_walkable(game_map, Pos(x=nxt[0], y=nxt[1]), unlocked):
                continue
            seen.add(nxt)
            prev[nxt] = cur
            if nxt == goal:
                path = [nxt]
                step = cur
                while step != origin:
                    path.insert(0, step)
                    step = prev[step]
                return [Pos(x=p[0], y=p[1]) for p in path]
            queue.append(nxt)
    return []
