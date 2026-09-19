/**
 * Phase 0 placeholder: proves the ported visual system renders.
 * Replaced by the real screen router in Phase 1.
 */
export function App() {
  return (
    <div className="h-screen flex flex-col p-3 overflow-hidden relative">
      <div className="starfield" />

      <header className="ascii-box p-2 mb-3 flex justify-between items-center relative z-10">
        <div className="flex items-center gap-4">
          <span className="text-indigo-400 text-sm tracking-widest">DREAMWALKER</span>
          <span className="text-gray-500 text-xs">// _ ** -^. .. -</span>
        </div>
        <span className="text-gray-500 text-xs">phase 0</span>
      </header>

      <div className="flex-1 grid grid-cols-[280px_1fr] gap-3 min-h-0 relative z-10">
        <div className="ascii-box p-3 flex-shrink-0">
          <div className="text-xs text-gray-500 mb-2">-- MAP --</div>
          <pre className="text-xs text-gray-300 leading-tight">
{`##############
#...#....@...#
#.#.#.####.#.#
#.#......#.+.#
#.####.###.#.#
#....B.......#
####.#####.###
#..C.....#..D#
##############`}
          </pre>
        </div>

        <div className="ascii-box p-3 flex flex-col min-h-0">
          <p className="text-gray-200 text-sm leading-relaxed mb-4">
            Visual system ported. Starfield, ascii boxes, buttons and the monospace
            palette are live; screens arrive in Phase 1.
          </p>
          <button className="ascii-btn w-full p-2 text-left text-sm max-w-xs">
            <span className="text-indigo-400">[1]</span>{' '}
            <span className="text-gray-200">Continue</span>
          </button>
        </div>
      </div>
    </div>
  );
}
