import type { GameMap } from '../types';

/**
 * Two hand-authored grids, both verified reachable by BFS with the door
 * dependency resolved (the Phase 3 validator will assert this automatically).
 * `#` wall, `.` floor, `+` locked door, `@` start, `A`-`D` destinations.
 */

export function mapNews(names: [string, string, string, string]): GameMap {
  return {
    width: 14,
    height: 9,
    tiles: [
      '##############',
      '#@....#....A.#',
      '#.###.#.####.#',
      '#.#B#.#.#....#',
      '#.#.#.#.#.##.#',
      '#...#...#.+C.#',
      '#.#######.##.#',
      '#D.........#.#',
      '##############',
    ],
    destinations: [
      { key: 'A', location_id: 'loc-a', name: names[0] },
      { key: 'B', location_id: 'loc-b', name: names[1] },
      { key: 'C', location_id: 'loc-c', name: names[2] },
      { key: 'D', location_id: 'loc-d', name: names[3] },
    ],
    doors: [{ key: '+', pos: { x: 10, y: 5 }, unlock_from: 'A' }],
  };
}

export function mapIdea(names: [string, string, string, string]): GameMap {
  return {
    width: 14,
    height: 9,
    tiles: [
      '##############',
      '#@...#..B....#',
      '#.##.#.####.##',
      '#..#.#.#...#.#',
      '##.#.#.#.#.#.#',
      '#A.......#.+.#',
      '#.#####.##.#C#',
      '#.....D....#.#',
      '##############',
    ],
    destinations: [
      { key: 'A', location_id: 'loc-a', name: names[0] },
      { key: 'B', location_id: 'loc-b', name: names[1] },
      { key: 'C', location_id: 'loc-c', name: names[2] },
      { key: 'D', location_id: 'loc-d', name: names[3] },
    ],
    doors: [{ key: '+', pos: { x: 11, y: 5 }, unlock_from: 'B' }],
  };
}

/** Grid position of the authored `@`. */
export function startPos(map: GameMap): { x: number; y: number } {
  for (let y = 0; y < map.tiles.length; y++) {
    const x = map.tiles[y].indexOf('@');
    if (x !== -1) return { x, y };
  }
  throw new Error('map has no start tile');
}
