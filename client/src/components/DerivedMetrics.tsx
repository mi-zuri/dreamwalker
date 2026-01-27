interface DerivedMetricsProps {
  luck: number;
  turbulence: number;
}

export function DerivedMetrics({ luck, turbulence }: DerivedMetricsProps) {
  const turbulenceHigh = turbulence > 60;
  const turbulenceCritical = turbulence > 150;

  return (
    <div className="flex gap-6 text-sm">
      <div>
        <span className="text-gray-500">Luck</span>
        <span className="ml-2 text-blue-400">{Math.round(luck)}%</span>
      </div>
      {turbulenceHigh && (
        <div className={turbulenceCritical ? 'animate-pulse' : ''}>
          <span className="text-gray-500">Turbulence</span>
          <span className={`ml-2 ${turbulenceCritical ? 'text-red-400' : 'text-orange-400'}`}>
            {Math.round(turbulence)}
          </span>
        </div>
      )}
    </div>
  );
}
