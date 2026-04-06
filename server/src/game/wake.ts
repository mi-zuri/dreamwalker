import type { Metrics, WakeCause } from '../../../shared/types.js';

const EXTREME_THRESHOLD = 90;

export interface WakeCheck {
  shouldWake: boolean;
  cause: WakeCause | null;
}

export function checkWakeConditions(metrics: Metrics): WakeCheck {
  // Priority 1: selfAwareness > 70 → lucidity_break
  if (metrics.selfAwareness > EXTREME_THRESHOLD) {
    return { shouldWake: true, cause: 'lucidity_break' };
  }

  // Priority 2: selfAwareness < -70 → dissolution
  if (metrics.selfAwareness < -EXTREME_THRESHOLD) {
    return { shouldWake: true, cause: 'dissolution' };
  }

  // Priority 3: |arousal| > 80 → action_overload
  if (Math.abs(metrics.arousal) > EXTREME_THRESHOLD) {
    return { shouldWake: true, cause: 'action_overload' };
  }

  // Priority 4: |valence| > 80 → emotional_overload
  if (Math.abs(metrics.valence) > EXTREME_THRESHOLD) {
    return { shouldWake: true, cause: 'emotional_overload' };
  }

  return { shouldWake: false, cause: null };
}
