import type { ReactNode } from 'react';

const COLORS: Record<string, string> = {
  POI: 'text-indigo-400',
  LOC: 'text-teal-400',
  KEY: 'text-pink-400',
};

const PATTERN = /\[(POI|LOC|KEY):([^\]]+)\]/g;

/**
 * Renders `[POI:..]`, `[LOC:..]` and `[KEY:..]` markers emitted by the scene
 * prompts as coloured spans. Ported from the original Game.tsx.
 */
export function HighlightedText({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  PATTERN.lastIndex = 0;
  while ((match = PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const [, type, content] = match;
    parts.push(
      <span key={key++} className={COLORS[type] ?? 'text-gray-200'}>
        {content}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return <>{parts.length ? parts : text}</>;
}
