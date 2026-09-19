import type { Destination, GameMap, Pos } from '../types';

export const WALL = '#';
export const FLOOR = '.';
export const DOOR = '+';
export const START = '@';

export function tileAt(map: GameMap, { x, y }: Pos): string {
  if (y < 0 || y >= map.height || x < 0 || x >= map.width) return WALL;
  return map.tiles[y][x] ?? WALL;
}

export function destinationAt(map: GameMap, pos: Pos): Destination | undefined {
  const c = tileAt(map, pos);
  return map.destinations.find((d) => d.key === c);
}

export function doorAt(map: GameMap, pos: Pos) {
  return map.doors.find((d) => d.pos.x === pos.x && d.pos.y === pos.y);
}

/**
 * A tile can be entered when it is not a wall, and - if it is a door - the
 * destination it depends on has already been reached.
 */
export function isWalkable(map: GameMap, pos: Pos, unlocked: string[]): boolean {
  const c = tileAt(map, pos);
  if (c === WALL) return false;
  if (c === DOOR) {
    const door = doorAt(map, pos);
    return !door || unlocked.includes(door.unlock_from);
  }
  return true;
}

export function samePos(a: Pos, b: Pos): boolean {
  return a.x === b.x && a.y === b.y;
}

const STEPS: Pos[] = [
  { x: 0, y: -1 },
  { x: 0, y: 1 },
  { x: -1, y: 0 },
  { x: 1, y: 0 },
];

/**
 * Shortest walkable path from `from` to `to`, inclusive of `to` and excluding
 * `from`. Empty when unreachable. Used for click-to-move.
 */
export function pathTo(map: GameMap, from: Pos, to: Pos, unlocked: string[]): Pos[] {
  if (samePos(from, to) || !isWalkable(map, to, unlocked)) return [];
  const key = (p: Pos) => `${p.x},${p.y}`;
  const prev = new Map<string, Pos>();
  const seen = new Set<string>([key(from)]);
  const queue: Pos[] = [from];

  while (queue.length) {
    const cur = queue.shift()!;
    for (const s of STEPS) {
      const next = { x: cur.x + s.x, y: cur.y + s.y };
      const k = key(next);
      if (seen.has(k) || !isWalkable(map, next, unlocked)) continue;
      seen.add(k);
      prev.set(k, cur);
      if (samePos(next, to)) {
        const path: Pos[] = [next];
        let step = cur;
        while (!samePos(step, from)) {
          path.unshift(step);
          step = prev.get(key(step))!;
        }
        return path;
      }
      queue.push(next);
    }
  }
  return [];
}
