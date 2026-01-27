interface MetricBarProps {
  label: string;
  value: number;
  color: string;
  showWarning?: boolean;
}

export function MetricBar({ label, value, color, showWarning }: MetricBarProps) {
  // Metric range: -100 to +100
  // Bar fills from center (0) outward
  const absValue = Math.abs(value);
  const isPositive = value >= 0;
  const isExtreme = absValue > 50;

  return (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-400">{label}</span>
        <span className={isExtreme && showWarning ? 'text-red-400' : 'text-gray-300'}>
          {value > 0 ? '+' : ''}{value}
        </span>
      </div>
      <div className="h-3 bg-gray-800 rounded-full overflow-hidden relative">
        {/* Center line */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-600" />

        {/* Stable zone indicators */}
        <div className="absolute left-[25%] top-0 bottom-0 w-px bg-gray-700/50" />
        <div className="absolute left-[75%] top-0 bottom-0 w-px bg-gray-700/50" />

        {/* Value bar */}
        <div
          className={`absolute top-0 bottom-0 transition-all duration-300 ${
            isExtreme ? 'animate-pulse' : ''
          }`}
          style={{
            backgroundColor: isExtreme ? '#ef4444' : color,
            left: isPositive ? '50%' : `${50 - absValue / 2}%`,
            width: `${absValue / 2}%`,
          }}
        />
      </div>
    </div>
  );
}
