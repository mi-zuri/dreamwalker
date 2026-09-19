import { useState } from 'react';
import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';
import { HighlightedText } from '../HighlightedText';
import { TileMap } from '../game/TileMap';
import { LocationImage } from '../game/LocationImage';

export function GameScreen() {
  const { uiLanguage, game, busy, moveTo, choose, answer, toMenu } = useStore();
  const [draft, setDraft] = useState('');

  if (!game) return null;
  const openQuestion = game.open_question;

  async function submitAnswer() {
    const text = draft.trim();
    if (!text) return;
    setDraft('');
    await answer(text);
  }

  return (
    <div
      className={`h-screen flex flex-col p-3 overflow-hidden relative ${busy ? 'loading-state' : ''}`}
    >
      <Starfield />

      <header className="ascii-box p-2 mb-3 flex justify-between items-center relative z-10">
        <div className="flex items-center gap-4">
          <span className="text-indigo-400 text-sm tracking-widest">DREAMWALKER</span>
          <span className="text-gray-500 text-xs">// _ ** -^. .. -</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-gray-500 text-xs">
            {t(uiLanguage, 'turn')} [{game.turn}] · {game.resolved.length}/
            {game.map.destinations.length}
          </span>
          <button
            onClick={toMenu}
            className="ascii-btn px-2 py-1 text-xs text-gray-400 hover:text-white"
          >
            {t(uiLanguage, 'quit')}
          </button>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-[280px_1fr] gap-3 min-h-0 relative z-10">
        {/* Left rail: image on top, map below - as in the original layout. */}
        <div className="flex flex-col gap-3 min-h-0">
          <LocationImage scene={game.current_scene} language={uiLanguage} />
          <TileMap
            map={game.map}
            playerPos={game.player_pos}
            resolved={game.resolved}
            unlocked={game.unlocked}
            language={uiLanguage}
            onMove={moveTo}
            disabled={busy || !!openQuestion}
          />
          {game.source_note && (
            <div className="ascii-box p-2 flex-shrink-0">
              <div className="text-[10px] text-gray-600 leading-snug">{game.source_note}</div>
            </div>
          )}
        </div>

        {/* Right pane: story, then choices, then the free-text input. */}
        <div className="ascii-box p-3 flex flex-col min-h-0 overflow-hidden">
          <div className="text-gray-200 text-sm leading-relaxed mb-4 flex-shrink-0">
            <HighlightedText text={game.current_scene.text} />
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 space-y-2">
            {openQuestion ? (
              <div>
                <div className="text-sm text-gray-300 mb-2">{openQuestion.prompt}</div>
                <input
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submitAnswer()}
                  placeholder={t(uiLanguage, 'answerPlaceholder')}
                  className="w-full bg-transparent border border-gray-700 px-3 py-2 text-sm text-gray-300 placeholder-gray-600 focus:border-indigo-500 focus:outline-none"
                />
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-gray-600">{t(uiLanguage, 'answerHint')}</span>
                  <button
                    onClick={submitAnswer}
                    disabled={!draft.trim()}
                    className="ascii-btn px-3 py-1 text-xs text-gray-300"
                  >
                    {t(uiLanguage, 'submit')}
                  </button>
                </div>
              </div>
            ) : game.choices.length ? (
              game.choices.map((choice, i) => (
                <button
                  key={choice.id}
                  onClick={() => choose(choice.id)}
                  disabled={busy}
                  className="ascii-btn w-full p-2 text-left text-sm"
                >
                  <span className="text-indigo-400">[{i + 1}]</span>{' '}
                  <span className="text-gray-200">{choice.text}</span>
                </button>
              ))
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
