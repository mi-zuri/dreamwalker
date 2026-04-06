import type { GameState, WakeCause } from '../../../shared/types.js';
import { applyChange, applyDrift } from './metrics.js';
import { checkWakeConditions } from './wake.js';

export interface DecisionResult {
  success: boolean;
  appliedEffects: { arousal: number; valence: number; selfAwareness: number };
  woke: boolean;
  wakeCause: WakeCause | null;
}

export function applyDecision(
  state: GameState,
  decisionId: string
): DecisionResult | null {
  const step = state.currentStep;
  if (!step) return null;

  const decision = step.decisions.find((d) => d.id === decisionId);
  if (!decision) return null;

  // Roll for success (all decisions are attempts)
  const success = Math.random() * 100 < decision.successChance;
  const effects = success ? decision.successEffects : decision.failureEffects;

  // Apply effects
  state.metrics = {
    arousal: applyChange(state.metrics.arousal, effects.arousal),
    valence: applyChange(state.metrics.valence, effects.valence),
    selfAwareness: applyChange(state.metrics.selfAwareness, effects.selfAwareness),
  };

  // Check wake conditions
  const wakeCheck = checkWakeConditions(state.metrics);
  if (wakeCheck.shouldWake) {
    triggerWake(state, wakeCheck.cause!);
  }

  // Handle location change
  if (decision.leadsToNode) {
    const locationIndex = state.dreamLayer.locations.findIndex(
      (loc) => loc.id === decision.leadsToNode
    );
    if (locationIndex >= 0) {
      state.dreamLayer.currentLocationIndex = locationIndex;
    }
  }

  return {
    success,
    appliedEffects: effects,
    woke: wakeCheck.shouldWake,
    wakeCause: wakeCheck.cause,
  };
}

export function advanceStep(state: GameState): void {
  state.metrics = applyDrift(state.metrics);
  state.dreamLayer.stepCount++;
}

export function triggerWake(state: GameState, cause: WakeCause): void {
  state.isAwake = true;
  state.wakeCause = cause;
}
