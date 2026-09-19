import { useEffect, useMemo } from 'react';
import type { GameMap, Pos } from '../../types';
import { DOOR, WALL, destinationAt, isWalkable, pathTo, tileAt } from '../../game/map';
import { t } from '../../i18n';
import type { Language } from '../../types';

interface Props {
  map: GameMap;
  playerPos: Pos;
  resolved: string[];
  unlocked: string[];
  language: Language;
  onMove: (pos: Pos) => void;
  disabled?: boolean;
}

const KEY_STEPS: Record<string, Pos> = {
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
  w: { x: 0, y: -1 },
  s: { x: 0, y: 1 },
  a: { x: -1, y: 0 },
  d: { x: 1, y: 0 },
};

function tileClass(char: string, isPlayer: boolean, done: boolean, locked: boolean): string {
  if (isPlayer) return 'text-indigo-300 bg-indigo-900/50';
  if (char === WALL) return 'text-gray-700';
  if (char === DOOR) return locked ? 'text-red-400' : 'text-green-500';
  if (char >= 'A' && char <= 'Z') return done ? 'text-gray-500' : 'text-pink-400';
  return 'text-gray-700';
}

/**
 * The walkable grid. Arrow/WASD steps one tile; clicking a reachable tile walks
 * the shortest path to it one step at a time.
 */
export function TileMap({
  map,
  playerPos,
  resolved,
  unlocked,
  language,
  onMove,
  disabled,
}: Props) {
  useEffect(() => {
    if (disabled) return;
    function onKey(e: KeyboardEvent) {
      const step = KEY_STEPS[e.key];
      if (!step) return;
      e.preventDefault();
      const next = { x: playerPos.x + step.x, y: playerPos.y + step.y };
      if (isWalkable(map, next, unlocked)) onMove(next);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [map, playerPos, unlocked, onMove, disabled]);

  const here = useMemo(() => destinationAt(map, playerPos), [map, playerPos]);

  function walkTo(target: Pos) {
    if (disabled) return;
    const path = pathTo(map, playerPos, target, unlocked);
    // Stop as soon as the route reaches somewhere the player still has to act,
    // otherwise walking past a location would silently skip its scene.
    const stopAt = path.findIndex((step) => {
      const dest = destinationAt(map, step);
      return dest && !resolved.includes(dest.key);
    });
    const route = stopAt === -1 ? path : path.slice(0, stopAt + 1);
    route.forEach((step, i) => setTimeout(() => onMove(step), i * 110));
  }

  return (
    <div className="ascii-box p-2 flex-shrink-0">
      <div className="text-xs text-gray-500 mb-2">{t(language, 'map')}</div>

      <div className="leading-none select-none" style={{ fontSize: '13px' }}>
        {map.tiles.map((row, y) => (
          <div key={y} className="flex">
            {row.split('').map((char, x) => {
              const isPlayer = playerPos.x === x && playerPos.y === y;
              const dest = destinationAt(map, { x, y });
              const done = !!dest && resolved.includes(dest.key);
              const door = map.doors.find((dr) => dr.pos.x === x && dr.pos.y === y);
              const locked = !!door && !unlocked.includes(door.unlock_from);
              const walkable = tileAt(map, { x, y }) !== WALL;
              return (
                <span
                  key={x}
                  data-tile={`${x},${y}`}
                  onClick={() => walkable && walkTo({ x, y })}
                  className={`inline-block w-[9px] text-center ${tileClass(char, isPlayer, done, locked)} ${
                    walkable && !disabled ? 'cursor-pointer' : ''
                  }`}
                >
                  {isPlayer ? '@' : char === '@' ? '.' : char}
                </span>
              );
            })}
          </div>
        ))}
      </div>

      <div className="mt-2 text-xs">
        <span className="text-gray-500">&gt; </span>
        <span className="text-gray-300">
          {here ? here.name : t(language, 'youAreHere')}
        </span>
      </div>
      <div className="mt-1 text-xs text-gray-600">{t(language, 'moveHint')}</div>
    </div>
  );
}
