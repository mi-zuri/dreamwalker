import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';

export function LoginScreen() {
  const { language, setLanguage, signIn, signingIn } = useStore();

  return (
    <div className="h-screen flex items-center justify-center p-3 relative">
      <Starfield />
      <div className="ascii-box p-6 max-w-md w-full relative z-10 text-center">
        <div className="text-2xl tracking-widest text-indigo-400 mb-2">DREAMWALKER</div>
        <div className="text-xs text-gray-500 mb-6">{t(language, 'tagline')}</div>

        <button
          onClick={signIn}
          disabled={signingIn}
          className="ascii-btn w-full p-3 text-sm text-gray-200 border-indigo-800 hover:border-indigo-600"
        >
          {signingIn ? t(language, 'signingIn') : t(language, 'signIn')}
        </button>

        <div className="text-xs text-gray-600 mt-3">{t(language, 'signInBlurb')}</div>

        <div className="mt-6 pt-4 border-t border-gray-800 flex items-center justify-center gap-3 text-xs">
          <span className="text-gray-600">{t(language, 'languageLabel')}:</span>
          {(['en', 'pl'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLanguage(l)}
              className={language === l ? 'text-indigo-400' : 'text-gray-500 hover:text-gray-300'}
            >
              [{l.toUpperCase()}]
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
