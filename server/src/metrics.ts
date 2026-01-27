import type { Metrics, DerivedMetrics, TensionLevel, WakeCause } from '../../shared/types.js';

const STABLE_ZONE = 50;
const SC_IMMEDIATE_WAKE = 70;
const DRIFT_PER_STEP = 5;
const TURBULENCE_CRITICAL = 150;

// Clamp value to metric range
function clamp(value: number, min = -100, max = 100): number {
  return Math.max(min, Math.min(max, value));
}

// Calculate depth amplification multiplier
export function depthMultiplier(depth: number): number {
  return 1 + depth * 0.15;
}

// Apply a metric change with depth amplification
export function applyChange(
  current: number,
  change: number,
  depth: number
): number {
  const amplified = change * depthMultiplier(depth);
  return clamp(current + amplified);
}

// Drift metrics toward 0
export function applyDrift(metrics: Metrics): Metrics {
  const drift = (value: number) => {
    if (value === 0) return 0;
    const direction = value > 0 ? -1 : 1;
    const drifted = value + direction * DRIFT_PER_STEP;
    // Don't overshoot zero
    return (value > 0 && drifted < 0) || (value < 0 && drifted > 0)
      ? 0
      : drifted;
  };

  return {
    action: drift(metrics.action),
    emotion: drift(metrics.emotion),
    selfConsciousness: drift(metrics.selfConsciousness),
  };
}

// Calculate luck
export function calculateLuck(
  metrics: Metrics,
  depth: number,
  tension: TensionLevel
): number {
  const tensionMod = tension === 'low' ? 0 : tension === 'medium' ? 10 : 20;
  const luck =
    50 +
    metrics.emotion / 2 +
    metrics.selfConsciousness / 2 -
    depth * 5 -
    tensionMod;
  return clamp(luck, 0, 100);
}

// Calculate turbulence
export function calculateTurbulence(metrics: Metrics): number {
  return Math.abs(metrics.action) + Math.abs(metrics.emotion);
}

// Get all derived metrics
export function getDerivedMetrics(
  metrics: Metrics,
  depth: number,
  tension: TensionLevel
): DerivedMetrics {
  return {
    luck: calculateLuck(metrics, depth, tension),
    turbulence: calculateTurbulence(metrics),
  };
}

// Check if metric is in extreme zone
function isExtreme(value: number, threshold = STABLE_ZONE): boolean {
  return Math.abs(value) > threshold;
}

// Wake condition checking
export interface WakeCheck {
  shouldWake: boolean;
  cause: WakeCause | null;
}

export interface ExtremeSteps {
  action: number;
  emotion: number;
  turbulence: number;
}

export function checkWakeConditions(
  metrics: Metrics,
  extremeSteps: ExtremeSteps
): WakeCheck {
  // Immediate wake: SC > 70
  if (Math.abs(metrics.selfConsciousness) > SC_IMMEDIATE_WAKE) {
    return {
      shouldWake: true,
      cause: metrics.selfConsciousness > 0 ? 'lucidity_break' : 'dissolution',
    };
  }

  // 3 consecutive steps with |Action| > 50
  if (extremeSteps.action >= 3) {
    return {
      shouldWake: true,
      cause: metrics.action > 0 ? 'action_overload' : 'stagnation',
    };
  }

  // 3 consecutive steps with |Emotion| > 50
  if (extremeSteps.emotion >= 3) {
    return {
      shouldWake: true,
      cause: metrics.emotion > 0 ? 'emotional_overload' : 'dissolution',
    };
  }

  // 2 consecutive steps with turbulence > 150
  if (extremeSteps.turbulence >= 2) {
    return {
      shouldWake: true,
      cause: 'turbulence_critical',
    };
  }

  return { shouldWake: false, cause: null };
}

// Update extreme step counters
export function updateExtremeSteps(
  metrics: Metrics,
  current: ExtremeSteps
): ExtremeSteps {
  const turbulence = calculateTurbulence(metrics);

  return {
    action: isExtreme(metrics.action) ? current.action + 1 : 0,
    emotion: isExtreme(metrics.emotion) ? current.emotion + 1 : 0,
    turbulence: turbulence > TURBULENCE_CRITICAL ? current.turbulence + 1 : 0,
  };
}

// Calculate attempt success rate based on luck
export function attemptSuccessRate(luck: number): number {
  // Range: ~40% to 65%
  return 50 + luck * 0.3;
}

// Roll attempt success
export function rollAttempt(luck: number): boolean {
  const rate = attemptSuccessRate(luck);
  return Math.random() * 100 < rate;
}

// Create initial metrics
export function createInitialMetrics(): Metrics {
  return {
    action: 0,
    emotion: 0,
    selfConsciousness: 0,
  };
}

// Momentum carryover for descent (20%)
export function carryoverMetrics(metrics: Metrics): Metrics {
  return {
    action: Math.round(metrics.action * 0.2),
    emotion: Math.round(metrics.emotion * 0.2),
    selfConsciousness: Math.round(metrics.selfConsciousness * 0.2),
  };
}
