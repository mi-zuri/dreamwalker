import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { GameMap, Pos } from '../../types';
import { DOOR, WALL, destinationAt, isWalkable, pathTo, reachableFrom, tileAt } from '../../game/map';

interface Props {
  map: GameMap;
  playerPos: Pos;
  resolved: string[];
  unlocked: string[];
  onMove: (pos: Pos) => void;
  disabled?: boolean;
  /** Tile height in px. Ignored when `fit` is set. */
  cell?: number;
  /** Scale tiles to fill the parent element (the travel view). */
  fit?: boolean;
  /** Crop to a window of this many tiles around the player (sidebar view). */
  viewport?: { cols: number; rows: number };
  className?: string;
  /** Called when the player clicks somewhere they cannot currently walk to. */
  onBlocked?: (dest?: { name: string }) => void;
}

/** Width-to-height ratio of a monospace glyph. */
const ASPECT = 0.6;

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

function tileClass(
  char: string,
  isPlayer: boolean,
  done: boolean,
  locked: boolean,
  outOfReach: boolean,
): string {
  if (isPlayer) return 'text-indigo-300 bg-indigo-900/50';
  if (char === WALL) return 'text-gray-600';
  if (char === DOOR) return locked ? 'text-red-400' : 'text-green-500';
  if (char >= 'A' && char <= 'Z') {
    if (done) return 'text-gray-500';
    // Still gated: show it, but do not pretend the player can go there yet.
    return outOfReach ? 'text-red-900' : 'text-pink-400';
  }
  return 'text-gray-800';
}

/** Window of the grid to draw, clamped to the map bounds. */
function cropWindow(map: GameMap, player: Pos, viewport?: { cols: number; rows: number }) {
  if (!viewport) return { x0: 0, y0: 0, x1: map.width, y1: map.height };
  const cols = Math.min(viewport.cols, map.width);
  const rows = Math.min(viewport.rows, map.height);
  const x0 = Math.max(0, Math.min(player.x - (cols >> 1), map.width - cols));
  const y0 = Math.max(0, Math.min(player.y - (rows >> 1), map.height - rows));
  return { x0, y0, x1: x0 + cols, y1: y0 + rows };
}

export function TileMap({
  map,
  playerPos,
  resolved,
  unlocked,
  onMove,
  disabled,
  cell = 9,
  fit = false,
  viewport,
  className = '',
  onBlocked,
}: Props) {
  // A click-to-move walk is a queue of timers, one per tile. They are held
  // here so the next click can cancel them: without that, two overlapping
  // walks both keep stepping and the player appears to be in several places
  // at once, because each timer moves them along a route computed from a
  // position they have since left.
  const walk = useRef<ReturnType<typeof setTimeout>[]>([]);

  function cancelWalk() {
    walk.current.forEach(clearTimeout);
    walk.current = [];
  }

  useEffect(() => cancelWalk, []);
  useEffect(() => {
    if (disabled) cancelWalk();
  }, [disabled]);

  useEffect(() => {
    if (disabled) return;
    function onKey(e: KeyboardEvent) {
      const step = KEY_STEPS[e.key];
      if (!step) return;
      e.preventDefault();
      // A keypress takes over from a walk rather than fighting it.
      cancelWalk();
      const next = { x: playerPos.x + step.x, y: playerPos.y + step.y };
      if (isWalkable(map, next, unlocked)) onMove(next);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [map, playerPos, unlocked, onMove, disabled]);

  const win = useMemo(() => cropWindow(map, playerPos, viewport), [map, playerPos, viewport]);

  // Monospace glyphs are about 0.6x as wide as they are tall, so square tiles
  // leave big horizontal gaps. Size from the container and keep that ratio.
  const boxRef = useRef<HTMLDivElement>(null);
  const [fitted, setFitted] = useState(cell);
  useLayoutEffect(() => {
    if (!fit) return;
    const el = boxRef.current?.parentElement;
    if (!el) return;
    const cols = win.x1 - win.x0;
    const rows = win.y1 - win.y0;
    const recompute = () => {
      const h = el.clientHeight;
      const w = el.clientWidth;
      if (!h || !w) return;
      setFitted(Math.max(6, Math.floor(Math.min(h / rows, w / cols / ASPECT))));
    };
    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit, cell, win.x0, win.x1, win.y0, win.y1]);

  const reachable = useMemo(
    () => reachableFrom(map, playerPos, unlocked),
    [map, playerPos, unlocked],
  );

  const cellH = fit ? fitted : cell;
  const cellW = Math.max(3, Math.round(cellH * ASPECT));

  function walkTo(target: Pos) {
    if (disabled) return;
    // Whatever was queued is abandoned; the new route starts from where the
    // player is now, which is what makes a second click change direction
    // rather than start a second walk.
    cancelWalk();
    const path = pathTo(map, playerPos, target, unlocked);
    // Stop as soon as the route reaches somewhere the player still has to act,
    // otherwise walking past a location would silently skip its scene.
    const stopAt = path.findIndex((step) => {
      const dest = destinationAt(map, step);
      return dest && !resolved.includes(dest.key);
    });
    const route = stopAt === -1 ? path : path.slice(0, stopAt + 1);
    walk.current = route.map((step, i) => setTimeout(() => onMove(step), i * 90));
  }

  const rows = [];
  for (let y = win.y0; y < win.y1; y++) {
    const cells = [];
    for (let x = win.x0; x < win.x1; x++) {
      const char = tileAt(map, { x, y });
      const isPlayer = playerPos.x === x && playerPos.y === y;
      const dest = destinationAt(map, { x, y });
      const done = !!dest && resolved.includes(dest.key);
      const door = map.doors.find((dr) => dr.pos.x === x && dr.pos.y === y);
      const locked = !!door && !unlocked.includes(door.unlock_from);
      const walkable = char !== WALL;
      const outOfReach = !reachable.has(`${x},${y}`);
      cells.push(
        <span
          key={x}
          data-tile={`${x},${y}`}
          onClick={() => walkable && (outOfReach ? onBlocked?.(dest) : walkTo({ x, y }))}
          style={{ width: cellW, height: cellH, lineHeight: `${cellH}px`, fontSize: cellH }}
          className={`inline-block text-center ${tileClass(char, isPlayer, done, locked, outOfReach)} ${
            walkable && !disabled && !outOfReach ? 'cursor-pointer' : ''
          }`}
        >
          {isPlayer ? '@' : char === '@' ? '.' : char}
        </span>,
      );
    }
    rows.push(
      <div key={y} className="flex">
        {cells}
      </div>,
    );
  }

  return (
    <div ref={boxRef} className={`leading-none select-none ${className}`}>
      {rows}
    </div>
  );
}
