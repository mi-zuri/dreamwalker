import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  depthMultiplier,
  applyDrift,
  calculateLuck,
  calculateTurbulence,
  checkWakeConditions,
  updateExtremeSteps,
  attemptSuccessRate,
  applyChange,
  carryoverMetrics,
} from './metrics.js';
import type { Metrics, ExtremeSteps } from '../../shared/types.js';

describe('Metrics Module', () => {
  describe('depthMultiplier', () => {
    it('returns 1.15 at depth 1', () => {
      assert.strictEqual(depthMultiplier(1), 1.15);
    });

    it('returns 1.75 at depth 5', () => {
      assert.strictEqual(depthMultiplier(5), 1.75);
    });
  });

  describe('applyDrift', () => {
    it('drifts positive values toward 0 by 5', () => {
      const metrics: Metrics = { action: 30, emotion: 20, selfConsciousness: 10 };
      const drifted = applyDrift(metrics);
      assert.strictEqual(drifted.action, 25);
      assert.strictEqual(drifted.emotion, 15);
      assert.strictEqual(drifted.selfConsciousness, 5);
    });

    it('drifts negative values toward 0 by 5', () => {
      const metrics: Metrics = { action: -30, emotion: -20, selfConsciousness: -10 };
      const drifted = applyDrift(metrics);
      assert.strictEqual(drifted.action, -25);
      assert.strictEqual(drifted.emotion, -15);
      assert.strictEqual(drifted.selfConsciousness, -5);
    });

    it('does not overshoot zero', () => {
      const metrics: Metrics = { action: 3, emotion: -2, selfConsciousness: 0 };
      const drifted = applyDrift(metrics);
      assert.strictEqual(drifted.action, 0);
      assert.strictEqual(drifted.emotion, 0);
      assert.strictEqual(drifted.selfConsciousness, 0);
    });
  });

  describe('applyChange', () => {
    it('applies depth amplification', () => {
      // At depth 1: multiplier = 1.15
      const result = applyChange(0, 10, 1);
      assert.strictEqual(result, 11.5);
    });

    it('clamps to max 100', () => {
      const result = applyChange(90, 20, 1);
      assert.strictEqual(result, 100);
    });

    it('clamps to min -100', () => {
      const result = applyChange(-90, -20, 1);
      assert.strictEqual(result, -100);
    });
  });

  describe('calculateLuck', () => {
    it('returns 50 with neutral metrics at depth 1 low tension', () => {
      const metrics: Metrics = { action: 0, emotion: 0, selfConsciousness: 0 };
      const luck = calculateLuck(metrics, 1, 'low');
      // 50 + 0 + 0 - 5 - 0 = 45
      assert.strictEqual(luck, 45);
    });

    it('increases with positive emotion', () => {
      const metrics: Metrics = { action: 0, emotion: 40, selfConsciousness: 0 };
      const luck = calculateLuck(metrics, 1, 'low');
      // 50 + 20 + 0 - 5 - 0 = 65
      assert.strictEqual(luck, 65);
    });

    it('decreases with depth', () => {
      const metrics: Metrics = { action: 0, emotion: 0, selfConsciousness: 0 };
      const luck = calculateLuck(metrics, 5, 'low');
      // 50 + 0 + 0 - 25 - 0 = 25
      assert.strictEqual(luck, 25);
    });

    it('decreases with higher tension', () => {
      const metrics: Metrics = { action: 0, emotion: 0, selfConsciousness: 0 };
      const luckHigh = calculateLuck(metrics, 1, 'high');
      // 50 + 0 + 0 - 5 - 20 = 25
      assert.strictEqual(luckHigh, 25);
    });
  });

  describe('calculateTurbulence', () => {
    it('returns sum of absolute values', () => {
      const metrics: Metrics = { action: 30, emotion: -40, selfConsciousness: 10 };
      assert.strictEqual(calculateTurbulence(metrics), 70);
    });

    it('handles all negative values', () => {
      const metrics: Metrics = { action: -50, emotion: -60, selfConsciousness: 0 };
      assert.strictEqual(calculateTurbulence(metrics), 110);
    });
  });

  describe('checkWakeConditions', () => {
    it('wakes immediately when SC > 70 (positive)', () => {
      const metrics: Metrics = { action: 0, emotion: 0, selfConsciousness: 75 };
      const extreme: ExtremeSteps = { action: 0, emotion: 0, turbulence: 0 };
      const result = checkWakeConditions(metrics, extreme);
      assert.strictEqual(result.shouldWake, true);
      assert.strictEqual(result.cause, 'lucidity_break');
    });

    it('wakes immediately when SC < -70', () => {
      const metrics: Metrics = { action: 0, emotion: 0, selfConsciousness: -75 };
      const extreme: ExtremeSteps = { action: 0, emotion: 0, turbulence: 0 };
      const result = checkWakeConditions(metrics, extreme);
      assert.strictEqual(result.shouldWake, true);
      assert.strictEqual(result.cause, 'dissolution');
    });

    it('wakes after 3 steps of extreme action', () => {
      const metrics: Metrics = { action: 60, emotion: 0, selfConsciousness: 0 };
      const extreme: ExtremeSteps = { action: 3, emotion: 0, turbulence: 0 };
      const result = checkWakeConditions(metrics, extreme);
      assert.strictEqual(result.shouldWake, true);
      assert.strictEqual(result.cause, 'action_overload');
    });

    it('wakes after 3 steps of extreme emotion', () => {
      const metrics: Metrics = { action: 0, emotion: 60, selfConsciousness: 0 };
      const extreme: ExtremeSteps = { action: 0, emotion: 3, turbulence: 0 };
      const result = checkWakeConditions(metrics, extreme);
      assert.strictEqual(result.shouldWake, true);
      assert.strictEqual(result.cause, 'emotional_overload');
    });

    it('wakes after 2 steps of critical turbulence', () => {
      const metrics: Metrics = { action: 80, emotion: 80, selfConsciousness: 0 };
      const extreme: ExtremeSteps = { action: 0, emotion: 0, turbulence: 2 };
      const result = checkWakeConditions(metrics, extreme);
      assert.strictEqual(result.shouldWake, true);
      assert.strictEqual(result.cause, 'turbulence_critical');
    });

    it('does not wake when metrics are stable', () => {
      const metrics: Metrics = { action: 30, emotion: 30, selfConsciousness: 30 };
      const extreme: ExtremeSteps = { action: 0, emotion: 0, turbulence: 0 };
      const result = checkWakeConditions(metrics, extreme);
      assert.strictEqual(result.shouldWake, false);
      assert.strictEqual(result.cause, null);
    });
  });

  describe('updateExtremeSteps', () => {
    it('increments action counter when extreme', () => {
      const metrics: Metrics = { action: 60, emotion: 0, selfConsciousness: 0 };
      const current: ExtremeSteps = { action: 1, emotion: 0, turbulence: 0 };
      const result = updateExtremeSteps(metrics, current);
      assert.strictEqual(result.action, 2);
    });

    it('resets action counter when not extreme', () => {
      const metrics: Metrics = { action: 40, emotion: 0, selfConsciousness: 0 };
      const current: ExtremeSteps = { action: 2, emotion: 0, turbulence: 0 };
      const result = updateExtremeSteps(metrics, current);
      assert.strictEqual(result.action, 0);
    });

    it('increments turbulence counter when > 150', () => {
      const metrics: Metrics = { action: 80, emotion: 80, selfConsciousness: 0 };
      const current: ExtremeSteps = { action: 0, emotion: 0, turbulence: 0 };
      const result = updateExtremeSteps(metrics, current);
      assert.strictEqual(result.turbulence, 1);
    });
  });

  describe('attemptSuccessRate', () => {
    it('returns ~40% at luck 0', () => {
      const rate = attemptSuccessRate(0);
      assert.strictEqual(rate, 50); // 50 + 0*0.3
    });

    it('returns ~65% at luck 50', () => {
      const rate = attemptSuccessRate(50);
      assert.strictEqual(rate, 65); // 50 + 50*0.3
    });
  });

  describe('carryoverMetrics', () => {
    it('carries over 20% of metrics', () => {
      const metrics: Metrics = { action: 50, emotion: -40, selfConsciousness: 30 };
      const result = carryoverMetrics(metrics);
      assert.strictEqual(result.action, 10);
      assert.strictEqual(result.emotion, -8);
      assert.strictEqual(result.selfConsciousness, 6);
    });
  });
});
