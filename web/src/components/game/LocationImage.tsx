import { t } from '../../i18n';
import type { Language, Scene } from '../../types';

/** Fixed-width image panel at the top of the left rail, as in the original UI. */
export function LocationImage({ scene, language }: { scene: Scene; language: Language }) {
  return (
    <div className="flex-shrink-0">
      <div className="ascii-box p-1 min-h-[180px] flex items-center justify-center">
        {scene.image_url ? (
          <img
            src={scene.image_url}
            alt=""
            className="w-full h-auto max-h-44 object-contain pixel-img opacity-90"
          />
        ) : (
          <div className="text-gray-600 text-xs">{t(language, 'noImage')}</div>
        )}
      </div>
      {scene.image_credit && (
        <div className="text-[10px] text-gray-600 mt-1 truncate" title={scene.image_credit.credit}>
          {scene.image_credit.credit}
        </div>
      )}
    </div>
  );
}
