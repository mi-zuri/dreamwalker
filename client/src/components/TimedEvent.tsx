import { useState, useEffect, useCallback } from 'react';
import type { Decision } from '../../../shared/types';

interface TimedEventProps {
  decisions: Decision[];
  deadline: number;
  onDecision: (decisionId: string) => void;
}

export function TimedEvent({ decisions, deadline, onDecision }: TimedEventProps) {
  const [timeLeft, setTimeLeft] = useState(deadline);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    if (timeLeft <= 0) {
      setIsExpired(true);
      onDecision(decisions[0].id);
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 100);
    }, 100);

    return () => clearInterval(timer);
  }, [timeLeft, decisions, onDecision]);

  const handleDecision = useCallback(
    (decisionId: string) => {
      if (isExpired) return;
      onDecision(decisionId);
    },
    [isExpired, onDecision]
  );

  const progress = (timeLeft / deadline) * 100;
  const seconds = Math.ceil(timeLeft / 1000);

  // ASCII progress bar
  const barWidth = 20;
  const filled = Math.round((progress / 100) * barWidth);
  let bar = '';
  for (let i = 0; i < barWidth; i++) {
    bar += i < filled ? '#' : '-';
  }

  const getBarColor = () => {
    if (progress > 60) return 'text-green-400';
    if (progress > 30) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="relative">
      {/* Countdown */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-red-400 text-xs uppercase tracking-wide">
            !! DECIDE NOW !!
          </span>
          <span className={`text-sm ${progress < 30 ? 'text-red-400 animate-pulse' : 'text-gray-300'}`}>
            {seconds}s
          </span>
        </div>
        <div className={`text-xs tracking-wider ${getBarColor()} ${progress < 30 ? 'animate-pulse' : ''}`}>
          [{bar}]
        </div>
      </div>

      {/* Decision buttons */}
      <div className="space-y-2">
        {decisions.map((decision, i) => (
          <button
            key={decision.id}
            onClick={() => handleDecision(decision.id)}
            disabled={isExpired}
            className={`
              ascii-btn w-full p-2 text-left text-sm
              ${isExpired
                ? 'opacity-40 cursor-not-allowed'
                : 'border-red-800 hover:border-red-600'
              }
              ${progress < 30 && !isExpired ? 'animate-pulse' : ''}
            `}
          >
            <span className="text-red-400">[{i + 1}]</span>{' '}
            <span className="text-gray-200">{decision.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
