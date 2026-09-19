import { useEffect, useState } from 'react';
import { useStore } from '../../store';
import { STAGE_KEYS, t } from '../../i18n';
import { Starfield } from '../Starfield';

/** Vague stage labels only - the pipeline's real stage list is not exposed. */
export function LoadingScreen() {
  const { uiLanguage, stage } = useStore();
  const [dots, setDots] = useState(1);

  useEffect(() => {
    const id = setInterval(() => setDots((d) => (d % 4) + 1), 600);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="h-screen flex items-center justify-center relative loading-state">
      <Starfield />
      <div
        className="absolute inset-0 z-10"
        style={{
          background:
            'radial-gradient(circle, #05050a 0%, #05050a 30%, rgba(5,5,10,0.6) 60%, transparent 100%)',
        }}
      />
      <div className="relative z-20 text-center">
        <div className="text-indigo-400 text-2xl tracking-widest mb-4">
          {'z'.repeat(dots)}
        </div>
        <div className="text-gray-500 text-xs">
          {stage ? t(uiLanguage, STAGE_KEYS[stage]) : ''}
        </div>
      </div>
    </div>
  );
}
