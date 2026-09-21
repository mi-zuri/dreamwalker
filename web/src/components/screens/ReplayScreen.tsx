import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';
import { Header } from '../Header';
import { HighlightedText } from '../HighlightedText';

export function ReplayScreen() {
  const { language, replay, replayIndex, setReplayIndex, openLibrary } = useStore();
  if (!replay) return null;

  const turn = replay.turns[replayIndex];
  const atStart = replayIndex === 0;
  const atEnd = replayIndex === replay.turns.length - 1;

  return (
    <div className="h-screen flex flex-col p-3 overflow-hidden relative">
      <Starfield />
      <Header
        language={language}
        subtitle={t(language, 'replayTitle')}
        right={
          <button onClick={openLibrary} className="hover:text-gray-300">
            {t(language, 'back')}
          </button>
        }
      />

      <div className="flex-1 grid grid-cols-[280px_1fr] gap-3 min-h-0 relative z-10">
        <div className="ascii-box p-1 h-fit flex items-center justify-center min-h-[180px]">
          {turn.scene.image_url ? (
            <img
              src={turn.scene.image_url}
              alt=""
              className="w-full h-auto max-h-44 object-contain pixel-img opacity-90"
            />
          ) : (
            <div className="text-gray-600 text-xs">{t(language, 'noImage')}</div>
          )}
        </div>

        <div className="ascii-box p-3 flex flex-col min-h-0 overflow-y-auto">
          <div className="text-xs text-gray-500 mb-3">
            {replay.title} · {t(language, 'turn')} {turn.turn}/{replay.turns.length}
          </div>
          <div className="text-gray-200 text-sm leading-relaxed mb-4">
            <HighlightedText text={turn.scene.text} />
          </div>
          {turn.chosen && (
            <div className="ascii-box p-2 mb-2">
              <span className="text-indigo-400 text-xs">{'>'}</span>{' '}
              <span className="text-sm text-gray-300">{turn.chosen}</span>
            </div>
          )}
          {turn.answer && (
            <div className="ascii-box p-2 border-teal-800">
              <div className="text-xs text-gray-600 mb-1">{t(language, 'answerHint')}</div>
              <span className="text-sm text-teal-300 italic">{turn.answer}</span>
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex gap-3 relative z-10">
        <button
          onClick={() => setReplayIndex(replayIndex - 1)}
          disabled={atStart}
          className="ascii-btn px-4 py-2 text-xs text-gray-400"
        >
          {t(language, 'prev')}
        </button>
        <button
          onClick={() => setReplayIndex(replayIndex + 1)}
          disabled={atEnd}
          className="ascii-btn px-4 py-2 text-xs text-gray-400"
        >
          {t(language, 'next')}
        </button>
      </div>
    </div>
  );
}
