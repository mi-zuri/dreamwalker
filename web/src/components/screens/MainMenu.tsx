import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';
import { Header } from '../Header';

export function MainMenu() {
  const {
    uiLanguage,
    storyLanguage,
    setUiLanguage,
    setStoryLanguage,
    idea,
    setIdea,
    region,
    setRegion,
    start,
    openLibrary,
    signOut,
  } = useStore();

  const isNews = idea.trim().length === 0;

  return (
    <div className="h-screen flex flex-col p-3 overflow-hidden relative">
      <Starfield />
      <Header
        language={uiLanguage}
        right={
          <button onClick={signOut} className="hover:text-gray-300">
            {t(uiLanguage, 'signOut')}
          </button>
        }
      />

      <div className="flex-1 flex items-center justify-center relative z-10">
        <div className="ascii-box p-6 max-w-lg w-full">
          <label className="block text-xs text-gray-500 mb-2">
            {t(uiLanguage, 'ideaLabel')}
          </label>
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder={t(uiLanguage, 'ideaPlaceholder')}
            className="w-full h-20 resize-none bg-transparent border border-gray-700 px-3 py-2 text-sm text-gray-300 placeholder-gray-600 focus:border-indigo-500 focus:outline-none"
          />
          <div className="text-xs text-gray-600 mt-1">{t(uiLanguage, 'ideaHint')}</div>

          <div className="mt-5 flex items-center gap-3 text-xs">
            <span className="text-gray-600 w-28">
              {isNews ? t(uiLanguage, 'regionLabel') : ''}
            </span>
            {isNews &&
              (['pl', 'world'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRegion(r)}
                  className={
                    region === r ? 'text-indigo-400' : 'text-gray-500 hover:text-gray-300'
                  }
                >
                  [{r === 'pl' ? t(uiLanguage, 'regionPl') : t(uiLanguage, 'regionWorld')}]
                </button>
              ))}
          </div>

          <div className="mt-3 flex items-center gap-3 text-xs">
            <span className="text-gray-600 w-28">{t(uiLanguage, 'languageLabel')}</span>
            {(['en', 'pl'] as const).map((l) => (
              <button
                key={l}
                onClick={() => setStoryLanguage(l)}
                className={
                  storyLanguage === l ? 'text-indigo-400' : 'text-gray-500 hover:text-gray-300'
                }
              >
                [{l.toUpperCase()}]
              </button>
            ))}
          </div>

          <div className="mt-2 flex items-center gap-3 text-xs">
            <span className="text-gray-600 w-28">{t(uiLanguage, 'uiLanguageLabel')}</span>
            {(['en', 'pl'] as const).map((l) => (
              <button
                key={l}
                onClick={() => setUiLanguage(l)}
                className={
                  uiLanguage === l ? 'text-indigo-400' : 'text-gray-500 hover:text-gray-300'
                }
              >
                [{l.toUpperCase()}]
              </button>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={start}
              className="ascii-btn flex-1 p-3 text-sm text-gray-200 border-indigo-800 hover:border-indigo-600"
            >
              {t(uiLanguage, 'start')}
            </button>
            <button
              onClick={openLibrary}
              className="ascii-btn px-3 py-3 text-xs text-gray-400 hover:text-gray-200"
            >
              {t(uiLanguage, 'library')}
            </button>
          </div>

          <div className="mt-3 text-xs text-gray-600">
            {'> '}
            <span className="text-gray-500">
              {isNews ? t(uiLanguage, 'modeNews') : t(uiLanguage, 'modeIdea')}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
