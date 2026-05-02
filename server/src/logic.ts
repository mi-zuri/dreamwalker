import type { GameState, Metrics, DerivedMetrics, WakeCause } from '../../shared/types.js';

const DRIFT_PER_STEP = 5;
const EXTREME_THRESHOLD = 90;

function clamp(value: number, min = -100, max = 100): number {
  return Math.max(min, Math.min(max, value));
}

function applyChange(current: number, change: number): number {
  return clamp(current + change);
}

function applyDrift(metrics: Metrics): Metrics {
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

export function getDerivedMetrics(metrics: Metrics): DerivedMetrics {
  return {
    luck: clamp(50 + metrics.valence / 2 + metrics.selfAwareness / 2, 0, 100),
    turbulence: Math.abs(metrics.arousal) + Math.abs(metrics.valence),
  };
}

function checkWakeCause(metrics: Metrics): WakeCause | null {
  if (metrics.selfAwareness > EXTREME_THRESHOLD) return 'lucidity_break';
  if (metrics.selfAwareness < -EXTREME_THRESHOLD) return 'dissolution';
  if (Math.abs(metrics.arousal) > EXTREME_THRESHOLD) return 'action_overload';
  if (Math.abs(metrics.valence) > EXTREME_THRESHOLD) return 'emotional_overload';
  return null;
}

export interface DecisionResult {
  appliedEffects: Metrics;
  woke: boolean;
  wakeCause: WakeCause | null;
}

export function applyDecision(state: GameState, decisionId: string): DecisionResult | null {
  const step = state.currentStep;
  if (!step) return null;
  const decision = step.decisions.find((d) => d.id === decisionId);
  if (!decision) return null;

  const effects = decision.effects;
  state.metrics = {
    arousal: applyChange(state.metrics.arousal, effects.arousal),
    valence: applyChange(state.metrics.valence, effects.valence),
    selfAwareness: applyChange(state.metrics.selfAwareness, effects.selfAwareness),
  };

  const wakeCause = checkWakeCause(state.metrics);
  if (wakeCause) {
    state.isAwake = true;
    state.wakeCause = wakeCause;
  }

  return { appliedEffects: effects, woke: wakeCause !== null, wakeCause };
}

export function advanceStep(state: GameState): void {
  state.metrics = applyDrift(state.metrics);
  state.dreamLayer.stepCount++;
}
