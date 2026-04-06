interface DerivedMetricsProps {
  luck: number;
  turbulence: number;
}

export function DerivedMetrics({ luck, turbulence }: DerivedMetricsProps) {
  const turbulenceHigh = turbulence > 60;
  const turbulenceCritical = turbulence > 150;

  return (
    <div className="flex gap-4 text-xs">
      <div>
        <span className="text-gray-600">LUCK:</span>
        <span className="ml-1 text-blue-400">{Math.round(luck)}%</span>
      </div>
      {turbulenceHigh && (
        <div className={turbulenceCritical ? 'animate-pulse' : ''}>
          <span className="text-gray-600">TURB:</span>
          <span className={`ml-1 ${turbulenceCritical ? 'text-red-400' : 'text-orange-400'}`}>
            {Math.round(turbulence)}
          </span>
        </div>
      )}
    </div>
  );
}
