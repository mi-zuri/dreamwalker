import { useStore } from '../../store';
import { ERROR_KEYS, t } from '../../i18n';
import { Starfield } from '../Starfield';

export function ErrorScreen() {
  const { uiLanguage, error, dismissError } = useStore();

  return (
    <div className="h-screen flex items-center justify-center p-3 relative">
      <Starfield />
      <div className="ascii-box p-6 max-w-md w-full relative z-10 border-red-800 bg-red-950/30">
        <div className="text-xs text-red-400 mb-3">-- ERROR --</div>
        <p className="text-sm text-gray-300">
          {error ? t(uiLanguage, ERROR_KEYS[error.kind]) : ''}
        </p>
        {/* `detail` is a diagnostic, not a message: it carries exception
            text, dollar amounts and endpoint names. Useful while developing,
            nothing a player should be handed. */}
        {import.meta.env.DEV && error?.detail && (
          <p className="text-xs text-gray-600 mt-2 break-all">{error.detail}</p>
        )}
        <button
          onClick={dismissError}
          className="ascii-btn w-full mt-6 p-2 text-sm text-gray-300"
        >
          {t(uiLanguage, 'retry')}
        </button>
      </div>
    </div>
  );
}
