interface MetricBarProps {
  label: string;
  value: number;
  color: string;
  showWarning?: boolean;
}

export function MetricBar({ label, value, color, showWarning }: MetricBarProps) {
  const absValue = Math.abs(value);
  const isPositive = value >= 0;
  const isExtreme = absValue > 50;

  // ASCII progress bar characters
  const totalWidth = 20;
  const filledCount = Math.round((absValue / 100) * (totalWidth / 2));

  let bar = '';
  for (let i = 0; i < totalWidth; i++) {
    const center = totalWidth / 2;
    if (isPositive) {
      if (i >= center && i < center + filledCount) {
        bar += '#';
      } else if (i === center) {
        bar += '|';
      } else {
        bar += '-';
      }
    } else {
      if (i < center && i >= center - filledCount) {
        bar += '#';
      } else if (i === center) {
        bar += '|';
      } else {
        bar += '-';
      }
    }
  }

  return (
    <div className="mb-2 text-xs">
      <div className="flex justify-between mb-0.5">
        <span className="text-gray-500">{label}</span>
        <span className={isExtreme && showWarning ? 'text-red-400' : 'text-gray-400'}>
          {value > 0 ? '+' : ''}{value}
        </span>
      </div>
      <div
        className={`tracking-wider ${isExtreme && showWarning ? 'animate-pulse text-red-400' : ''}`}
        style={{ color: isExtreme ? '#ef4444' : color }}
      >
        [{bar}]
      </div>
    </div>
  );
}
