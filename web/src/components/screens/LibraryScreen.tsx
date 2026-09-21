import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';
import { Header } from '../Header';

export function LibraryScreen() {
  const { language, saved, busy, openReplay, toMenu } = useStore();

  return (
    <div className={`h-screen flex flex-col p-3 overflow-hidden relative ${busy ? 'loading-state' : ''}`}>
      <Starfield />
      <Header
        language={language}
        subtitle={t(language, 'libraryTitle')}
        right={
          <button onClick={toMenu} className="hover:text-gray-300">
            {t(language, 'back')}
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto min-h-0 relative z-10">
        {saved.length === 0 && !busy ? (
          <div className="ascii-box p-6 text-sm text-gray-500">
            {t(language, 'libraryEmpty')}
          </div>
        ) : (
          <div className="space-y-2">
            {saved.map((g) => (
              <div key={g.game_id} className="ascii-box p-3 flex items-center gap-3">
                {g.image_url && (
                  <img
                    src={g.image_url}
                    alt=""
                    className="w-16 h-12 object-cover pixel-img opacity-80 flex-shrink-0"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 truncate">{g.title}</div>
                  <div className="text-xs text-gray-600 mt-1">
                    {new Date(g.played_at).toLocaleDateString()} ·{' '}
                    {t(language, g.mode === 'news' ? 'modeNews' : 'modeIdea')} ·{' '}
                    {g.language.toUpperCase()}
                    {g.match_score != null && (
                      <>
                        {' · '}
                        <span className="text-indigo-400">
                          {Math.round(g.match_score * 100)}%
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => openReplay(g.game_id)}
                  className="ascii-btn px-3 py-2 text-xs text-gray-400 hover:text-gray-200 flex-shrink-0"
                >
                  {t(language, 'replay')}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
