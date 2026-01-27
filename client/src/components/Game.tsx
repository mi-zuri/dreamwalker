import { useEffect } from 'react';
import { useGameStore } from '../stores/gameStore';
import { MetricBar } from './MetricBar';
import { DerivedMetrics } from './DerivedMetrics';
import { WakeScreen } from './WakeScreen';

export function Game() {
  const {
    gameState,
    derivedMetrics,
    isLoading,
    startSession,
    applyMetricChange,
    advanceStep,
    reset,
  } = useGameStore();

  useEffect(() => {
    startSession();
  }, []);

  if (isLoading && !gameState) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400">Entering the dream...</p>
      </div>
    );
  }

  if (!gameState) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <button
          onClick={startSession}
          className="px-8 py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-lg transition-colors"
        >
          Begin Dreaming
        </button>
      </div>
    );
  }

  if (gameState.isAwake && gameState.wakeCause) {
    return (
      <WakeScreen
        cause={gameState.wakeCause}
        depth={gameState.dreamLayer.depth}
        steps={gameState.dreamLayer.stepCount}
        onRestart={() => {
          reset();
          startSession();
        }}
      />
    );
  }

  const { metrics, dreamLayer } = gameState;

  return (
    <div className="min-h-screen p-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-light text-white">Dreamwalker</h1>
          <p className="text-gray-500 text-sm">Depth {dreamLayer.depth}</p>
        </div>
        <div className="text-right text-sm text-gray-500">
          Step {dreamLayer.stepCount} / {dreamLayer.maxSteps}
        </div>
      </div>

      {/* Metrics Panel */}
      <div className="bg-gray-900/50 rounded-xl p-6 mb-6">
        <MetricBar
          label="Action"
          value={metrics.action}
          color="#6366f1"
          showWarning
        />
        <MetricBar
          label="Emotion"
          value={metrics.emotion}
          color="#ec4899"
          showWarning
        />
        <MetricBar
          label="Self-Consciousness"
          value={metrics.selfConsciousness}
          color="#14b8a6"
          showWarning
        />

        {derivedMetrics && (
          <div className="mt-4 pt-4 border-t border-gray-800">
            <DerivedMetrics
              luck={derivedMetrics.luck}
              turbulence={derivedMetrics.turbulence}
            />
          </div>
        )}
      </div>

      {/* POI */}
      <div className="bg-indigo-900/20 border border-indigo-800/30 rounded-lg p-4 mb-6">
        <p className="text-indigo-300 text-sm uppercase tracking-wide mb-1">
          {dreamLayer.poi.type}
        </p>
        <p className="text-white">{dreamLayer.poi.description}</p>
      </div>

      {/* Step Context (placeholder for Phase 2) */}
      <div className="bg-gray-900/30 rounded-lg p-6 mb-6">
        <p className="text-gray-300 leading-relaxed italic">
          The dream awaits. Narrative engine will be connected in Phase 2.
        </p>
      </div>

      {/* Test Controls (will be replaced by actual choices in Phase 2) */}
      <div className="space-y-3">
        <p className="text-gray-500 text-sm">Test Controls (Phase 1)</p>

        <div className="grid grid-cols-3 gap-3">
          <button
            onClick={() => applyMetricChange({ action: 20 })}
            className="px-4 py-3 bg-indigo-600/50 hover:bg-indigo-600 text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            Action +20
          </button>
          <button
            onClick={() => applyMetricChange({ emotion: 20 })}
            className="px-4 py-3 bg-pink-600/50 hover:bg-pink-600 text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            Emotion +20
          </button>
          <button
            onClick={() => applyMetricChange({ selfConsciousness: 25 })}
            className="px-4 py-3 bg-teal-600/50 hover:bg-teal-600 text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            SC +25
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <button
            onClick={() => applyMetricChange({ action: -20 })}
            className="px-4 py-3 bg-indigo-900/50 hover:bg-indigo-900 text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            Action -20
          </button>
          <button
            onClick={() => applyMetricChange({ emotion: -20 })}
            className="px-4 py-3 bg-pink-900/50 hover:bg-pink-900 text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            Emotion -20
          </button>
          <button
            onClick={() => applyMetricChange({ selfConsciousness: -25 })}
            className="px-4 py-3 bg-teal-900/50 hover:bg-teal-900 text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            SC -25
          </button>
        </div>

        <button
          onClick={advanceStep}
          className="w-full px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          disabled={isLoading}
        >
          Advance Step (apply drift)
        </button>
      </div>
    </div>
  );
}
