import { useStore } from '../../store';
import { t } from '../../i18n';
import type { BeatStatus, Language } from '../../types';
import { Starfield } from '../Starfield';

const STATUS_KEY = {
  matched: 'beatMatched',
  diverged: 'beatDiverged',
  skipped: 'beatSkipped',
  pending: 'beatPending',
} as const;

const STATUS_COLOR: Record<BeatStatus, string> = {
  matched: 'text-teal-400',
  diverged: 'text-pink-400',
  skipped: 'text-gray-600',
  pending: 'text-gray-600',
};

function StatusTag({ status, language }: { status: BeatStatus; language: Language }) {
  return (
    <span className={`text-xs ${STATUS_COLOR[status]}`}>
      [{t(language, STATUS_KEY[status])}]
    </span>
  );
}

export function EndingScreen() {
  const { uiLanguage, ending, toMenu, openLibrary } = useStore();
  if (!ending) return null;

  const isNews = ending.mode === 'news';

  return (
    <div className="h-screen flex flex-col p-3 overflow-hidden relative">
      <Starfield />

      <header className="ascii-box p-2 mb-3 flex justify-between items-center relative z-10">
        <span className="text-indigo-400 text-sm tracking-widest">
          {t(uiLanguage, 'endingTitle')}
        </span>
        {ending.match_score != null && (
          <span className="text-xs text-gray-500">
            {t(uiLanguage, 'matchScore')}:{' '}
            <span className="text-indigo-400">{Math.round(ending.match_score * 100)}%</span>
          </span>
        )}
      </header>

      <div className="flex-1 overflow-y-auto min-h-0 relative z-10 space-y-3">
        <div className="ascii-box p-4">
          <div className="text-sm text-gray-200 mb-2">{ending.title}</div>
          <p className="text-sm text-gray-400 leading-relaxed">{ending.summary}</p>
        </div>

        <div className={`grid gap-3 ${isNews ? 'grid-cols-2' : 'grid-cols-1'}`}>
          {isNews && (
            <div className="ascii-box p-3">
              <div className="text-xs text-gray-500 mb-3">
                {t(uiLanguage, 'whatHappened')}
              </div>
              <div className="space-y-3">
                {ending.canon.map((beat) => (
                  <div key={beat.id}>
                    <div className="text-sm text-gray-300">{beat.title}</div>
                    <div className="text-xs text-gray-500 mt-1 leading-relaxed">
                      {beat.summary}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="ascii-box p-3">
            <div className="text-xs text-gray-500 mb-3">
              {t(uiLanguage, isNews ? 'whatYouDid' : 'yourStory')}
            </div>
            <div className="space-y-3">
              {ending.player.map((beat) => (
                <div key={beat.beat_id}>
                  <StatusTag status={beat.status} language={uiLanguage} />
                  <div className="text-xs text-gray-400 mt-1 leading-relaxed">
                    {beat.what_you_did}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="ascii-box p-3">
          <div className="text-xs text-gray-500 mb-2">-- STYLE --</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            {/* Labels come translated from the backend, which owns the catalog;
                the raw enum ids are the fallback for a game saved before that. */}
            {(ending.style_labels.length
              ? ending.style_labels
              : Object.entries(ending.style_card).map(([axis, label]) => ({ axis, label }))
            ).map(({ axis, label }) => (
              <span key={axis}>
                {axis.replace(/_/g, ' ')}: <span className="text-gray-400">{label}</span>
              </span>
            ))}
          </div>
        </div>

        {ending.sources.length > 0 && (
          <div className="ascii-box p-3">
            <div className="text-xs text-gray-500 mb-2">{t(uiLanguage, 'sources')}</div>
            <div className="space-y-1">
              {ending.sources.map((s) => (
                <a
                  key={s.url}
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-xs text-gray-500 hover:text-indigo-400 truncate"
                >
                  {s.title}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-3 flex gap-3 relative z-10">
        <button
          onClick={toMenu}
          className="ascii-btn flex-1 p-3 text-sm text-gray-200 border-indigo-800 hover:border-indigo-600"
        >
          {t(uiLanguage, 'playAgain')}
        </button>
        <button
          onClick={openLibrary}
          className="ascii-btn px-4 py-3 text-xs text-gray-400 hover:text-gray-200"
        >
          {t(uiLanguage, 'toLibrary')}
        </button>
      </div>
    </div>
  );
}
