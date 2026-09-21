import { useState } from 'react';
import { forceError } from '../api/client';
import { useStore } from '../store';
import type { AppErrorKind } from '../types';

const KINDS: AppErrorKind[] = [
  'network',
  'generation_failed',
  'pool_empty',
  'budget_exceeded',
  'blocked_event',
  'auth',
];

/**
 * Dev only: jump to any screen and arm the backend's next call to fail, so
 * every state in the plan's screen list stays reachable by hand.
 */
export function DevPanel() {
  const [open, setOpen] = useState(false);
  const store = useStore();

  if (!import.meta.env.DEV) return null;

  return (
    <div className="fixed bottom-2 right-2 z-50 text-xs">
      {open ? (
        <div className="ascii-box p-2 space-y-2 max-w-[260px]">
          <div className="flex justify-between items-center">
            <span className="text-gray-500">-- DEV --</span>
            <button onClick={() => setOpen(false)} className="text-gray-500 hover:text-gray-300">
              [x]
            </button>
          </div>

          <div className="text-gray-600">force next error:</div>
          <div className="flex flex-wrap gap-1">
            {KINDS.map((k) => (
              <button
                key={k}
                onClick={() => void forceError(k)}
                className="ascii-btn px-1 py-0.5 text-[10px] text-gray-400 hover:text-gray-200"
              >
                {k}
              </button>
            ))}
          </div>

          <div className="text-gray-600 pt-1">jump to:</div>
          <div className="flex flex-wrap gap-1">
            {(['login', 'menu', 'library'] as const).map((s) => (
              <button
                key={s}
                onClick={() => useStore.setState({ screen: s })}
                className="ascii-btn px-1 py-0.5 text-[10px] text-gray-400 hover:text-gray-200"
              >
                {s}
              </button>
            ))}
            <button
              onClick={() => useStore.setState({ user: { name: 'Gracz', email: 'p@e.com' }, screen: 'menu' })}
              className="ascii-btn px-1 py-0.5 text-[10px] text-gray-400 hover:text-gray-200"
            >
              skip login
            </button>
          </div>

          <div className="text-gray-600 pt-1">
            {store.screen} · ui:{store.uiLanguage} · story:{store.storyLanguage}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="ascii-btn px-2 py-1 text-[10px] text-gray-600 hover:text-gray-400"
        >
          [dev]
        </button>
      )}
    </div>
  );
}
