import { todo } from 'node:test';
import type { Metrics, DerivedMetrics } from '../../../shared/types.js';

const DRIFT_PER_STEP = 5;

function clamp(value: number, min = -100, max = 100): number {
  return Math.max(min, Math.min(max, value));
}

export function applyChange(current: number, change: number): number {
  return clamp(current + change);
}

// @TODO emotions have momentum that influences next events
// selfAwareness gravitates up like black hole
export function applyDrift(metrics: Metrics): Metrics {
  const drift = (value: number) => {
    if (value === 0) return 0;
    const direction = value > 0 ? -1 : 1;
    const drifted = value + direction * DRIFT_PER_STEP;
    return (value > 0 && drifted < 0) || (value < 0 && drifted > 0) ? 0 : drifted;
  };

  return {
    arousal: drift(metrics.arousal),
    valence: drift(metrics.valence),
    selfAwareness: drift(metrics.selfAwareness),
  };
}

// @TODO adjust
export function calculateLuck(metrics: Metrics): number {
  const luck = 50 + metrics.valence / 2 + metrics.selfAwareness / 2;
  return clamp(luck, 0, 100);
}

export function calculateTurbulence(metrics: Metrics): number {
  return Math.abs(metrics.arousal) + Math.abs(metrics.valence);
}

export function getDerivedMetrics(metrics: Metrics): DerivedMetrics {
  return {
    luck: calculateLuck(metrics),
    turbulence: calculateTurbulence(metrics),
  };
}
