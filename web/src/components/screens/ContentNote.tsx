import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';

/** Shown before play when the event was classified `safe_mode`. */
export function ContentNote() {
  const { language, game, acceptContentNote, declineContentNote } = useStore();
  if (!game) return null;

  return (
    <div className="h-screen flex items-center justify-center p-3 relative">
      <Starfield />
      <div className="ascii-box p-6 max-w-lg w-full relative z-10">
        <div className="text-xs text-gray-500 mb-3">{t(language, 'contentNoteTitle')}</div>
        <p className="text-sm text-gray-300 leading-relaxed">{game.content_note}</p>
        {game.source_note && (
          <p className="text-xs text-gray-600 mt-3">{game.source_note}</p>
        )}
        <div className="mt-6 flex items-center gap-3">
          <button
            onClick={acceptContentNote}
            className="ascii-btn flex-1 p-3 text-sm text-gray-200 border-indigo-800 hover:border-indigo-600"
          >
            {t(language, 'contentNoteAccept')}
          </button>
          <button
            onClick={declineContentNote}
            className="ascii-btn px-4 py-3 text-xs text-gray-400 hover:text-gray-200"
          >
            {t(language, 'contentNoteBack')}
          </button>
        </div>
      </div>
    </div>
  );
}
