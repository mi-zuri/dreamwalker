import type { DreamLayer } from '../../../shared/types';

interface SpatialMapProps {
  dreamLayer: DreamLayer;
}

export function SpatialMap({ dreamLayer }: SpatialMapProps) {
  const { locations, currentLocationIndex } = dreamLayer;

  if (locations.length === 0) {
    return null;
  }

  return (
    <div className="ascii-box p-2">
      <div className="text-xs text-gray-500 mb-2">-- MAP --</div>

      <div className="flex items-center gap-1 overflow-x-auto text-xs">
        {locations.map((location, index) => (
          <LocationNode
            key={location.id}
            index={index}
            isCurrent={index === currentLocationIndex}
            isLast={index === locations.length - 1}
          />
        ))}
      </div>

      <div className="mt-2 text-xs">
        <span className="text-gray-500">&gt; </span>
        <span className="text-gray-300">{locations[currentLocationIndex]?.name || '???'}</span>
      </div>
    </div>
  );
}

interface LocationNodeProps {
  index: number;
  isCurrent: boolean;
  isLast: boolean;
}

function LocationNode({ index, isCurrent, isLast }: LocationNodeProps) {
  return (
    <div className="flex items-center">
      <span
        className={`px-1 ${
          isCurrent ? 'text-indigo-400 bg-indigo-900/50' : 'text-gray-500'
        }`}
      >
        [{index + 1}]
      </span>
      {!isLast && <span className="text-gray-600">--</span>}
    </div>
  );
}
