import { useEffect, useState } from 'react';
import { useStore } from '../../store';
import { t } from '../../i18n';
import { destinationAt } from '../../game/map';
import { Starfield } from '../Starfield';
import { HighlightedText } from '../HighlightedText';
import { TileMap } from '../game/TileMap';
import { LocationImage } from '../game/LocationImage';

/** Tiles shown around the player in the minimised sidebar map. */
const SIDEBAR_VIEWPORT = { cols: 27, rows: 13 };

export function GameScreen() {
  const { uiLanguage, game, localPos, busy, moveTo, choose, answer, setOff, toMenu } =
    useStore();
  const [draft, setDraft] = useState('');
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    if (!blocked) return;
    const id = setTimeout(() => setBlocked(false), 2500);
    return () => clearTimeout(id);
  }, [blocked]);

  if (!game) return null;

  const openQuestion = game.open_question;
  const travelling = game.view === 'travel';
  // The player is drawn where they have walked to; the scene only changes
  // once the server has confirmed the move.
  const shownPos = localPos ?? game.player_pos;
  const here = destinationAt(game.map, game.player_pos);
  const placeName = here ? here.name : t(uiLanguage, 'inTransit');
  const left = game.map.destinations.length - game.resolved.length;

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
          <span className="text-gray-500 text-xs">
            {travelling ? t(uiLanguage, 'travel') : `// ${placeName}`}
          </span>
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
        {/* Left rail. Travel shows where you are; a scene also keeps a minimap. */}
        <div className="flex flex-col gap-3 min-h-0">
          <LocationImage scene={game.current_scene} language={uiLanguage} />

          <div className="ascii-box p-2 flex-shrink-0">
            <div className="text-xs text-gray-500 mb-1">{t(uiLanguage, 'youAreHere')}</div>
            <div className="text-sm text-gray-200">{placeName}</div>
            <div className="text-xs text-gray-600 mt-2">
              {left} {t(uiLanguage, 'remaining')}
            </div>
          </div>

          {!travelling && (
            <div className="ascii-box p-2 flex-shrink-0">
              <div className="text-xs text-gray-500 mb-2">{t(uiLanguage, 'map')}</div>
              <TileMap
                map={game.map}
                playerPos={shownPos}
                resolved={game.resolved}
                unlocked={game.unlocked}
                onMove={moveTo}
                disabled
                cell={14}
                viewport={SIDEBAR_VIEWPORT}
              />
            </div>
          )}

          {game.source_note && (
            <div className="ascii-box p-2 flex-shrink-0">
              <div className="text-[10px] text-gray-600 leading-snug">{game.source_note}</div>
            </div>
          )}
        </div>

        {/* Main pane: the map while travelling, the scene once you arrive. */}
        {travelling ? (
          <div className="ascii-box p-3 flex flex-col min-h-0 overflow-hidden">
            <div className="flex-1 flex items-center justify-center min-h-0">
              <TileMap
                map={game.map}
                playerPos={shownPos}
                resolved={game.resolved}
                unlocked={game.unlocked}
                onMove={moveTo}
                disabled={busy}
                fit
                onBlocked={() => setBlocked(true)}
              />
            </div>
            <div className="text-xs mt-2 flex-shrink-0">
              {blocked ? (
                <span className="text-red-400">{t(uiLanguage, 'blockedHint')}</span>
              ) : (
                <span className="text-gray-600">{t(uiLanguage, 'moveHint')}</span>
              )}
            </div>
          </div>
        ) : (
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
              ) : (
                /* The opening scene, before the player has anywhere to be. */
                <button
                  onClick={setOff}
                  className="ascii-btn w-full p-3 text-sm text-gray-200 border-indigo-800 hover:border-indigo-600"
                >
                  {t(uiLanguage, 'setOff')}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
