import { t } from '../i18n';
import type { Language } from '../types';

interface Props {
  language: Language;
  right?: React.ReactNode;
  subtitle?: string;
}

export function Header({ language, right, subtitle }: Props) {
  return (
    <header className="ascii-box p-2 mb-3 flex justify-between items-center relative z-10">
      <div className="flex items-center gap-4">
        <span className="text-indigo-400 text-sm tracking-widest">DREAMWALKER</span>
        <span className="text-gray-500 text-xs">{subtitle ?? '// _ ** -^. .. -'}</span>
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-500">
        {right ?? <span>{t(language, 'tagline')}</span>}
      </div>
    </header>
  );
}
