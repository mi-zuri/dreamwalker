import { useCallback, useState, useEffect, useRef } from 'react';
import { useGameStore } from '../store';
import { useAudioStream } from '../useAudioStream';
import { MetricBar } from './MetricBar';
import { WakeScreen } from './WakeScreen';
import { SpatialMap } from './SpatialMap';
import { StartScreen } from './StartScreen';

// Parse highlighted text markers and render with colors
// [POI:text] indigo, [LOC:text] teal, [KEY:text] pink
function renderHighlightedText(text: string): React.ReactNode[] {
  const pattern = /\[(POI|LOC|KEY):([^\]]+)\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const [, type, content] = match;
    const colorClass = {
      POI: 'text-indigo-400',
      LOC: 'text-teal-400',
      KEY: 'text-pink-400',
    }[type] || 'text-gray-200';
    parts.push(<span key={key++} className={colorClass}>{content}</span>);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length > 0 ? parts : [text];
}

export function Game() {
  const {
    sessionId,
    gameState,
    derivedMetrics,
    currentStep,
    isLoading,
    isGenerating,
    error,
    startSession,
    generateStep,
    makeDecision,
    reset,
  } = useGameStore();

  const { resume: resumeAudio } = useAudioStream(sessionId);
  const [pendingThought, setPendingThought] = useState('');
  const [showOutcome, setShowOutcome] = useState(false);
  const audioStartedRef = useRef(false);

  // Auto-generate first step once a session exists and nothing is in flight
  useEffect(() => {
    if (gameState && !currentStep && !isGenerating && !isLoading && !gameState.isAwake) {
      generateStep();
    }
  }, [gameState, currentStep, isGenerating, isLoading, generateStep]);

  // Start audio once first step has rendered
  useEffect(() => {
    if (currentStep && !audioStartedRef.current && !isGenerating) {
      audioStartedRef.current = true;
      resumeAudio();
    }
  }, [currentStep, isGenerating, resumeAudio]);

  const handleStart = useCallback(
    (initialThought?: string) => {
      audioStartedRef.current = false;
      setShowOutcome(false);
      startSession(initialThought);
    },
    [startSession]
  );

  const handleDecision = useCallback(
    async (decisionId: string) => {
      resumeAudio();
      const thought = pendingThought.trim();
      setPendingThought('');
      setShowOutcome(false);
      const result = await makeDecision(decisionId);
      if (result) setShowOutcome(true);
      if (result && !result.woke) {
        await generateStep(thought || undefined);
      }
    },
    [makeDecision, resumeAudio, pendingThought, generateStep]
  );

  if (!gameState) {
    return <StartScreen onStart={handleStart} isLoading={isLoading} />;
  }

  const currentLocation = gameState.dreamLayer.locations[gameState.dreamLayer.currentLocationIndex];

  if (gameState.isAwake && gameState.wakeCause) {
    return <WakeScreen cause={gameState.wakeCause} steps={gameState.dreamLayer.stepCount} onRestart={reset} />;
  }

  if (!currentStep) {
    return <StartScreen onStart={handleStart} isLoading={true} />;
  }

  const { metrics, dreamLayer } = gameState;

  const getEffectIndicator = (effects: { arousal: number; valence: number; selfAwareness: number }) => {
    const labels: Record<string, string> = { arousal: 'ACT', valence: 'EMO', selfAwareness: 'SC' };
    return Object.entries(effects)
      .filter(([, v]) => v !== 0)
      .map(([k, v]) => `[${labels[k]}${v > 0 ? '+' : '-'}]`)
      .join(' ');
  };

  const turbulence = derivedMetrics?.turbulence ?? 0;
  const turbulenceHigh = turbulence > 60;
  const turbulenceCritical = turbulence > 150;

  return (
    <div
      className={`h-screen flex flex-col p-3 overflow-hidden relative ${isGenerating || isLoading ? 'loading-state' : ''}`}
      onClick={resumeAudio}
    >
      {/* Starfield background */}
      <div className="starfield" />

      {/* Header */}
      <header className="ascii-box p-2 mb-3 flex justify-between items-center relative z-10">
        <div className="flex items-center gap-4">
          <span className="text-indigo-400 text-sm tracking-widest">DREAMWALKER</span>
          <span className="text-gray-500 text-xs">// _ ** -^. .. -</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-gray-500 text-xs">
            step [{dreamLayer.stepCount}/{dreamLayer.maxSteps}]
          </span>
          <button onClick={reset} className="ascii-btn px-2 py-1 text-xs text-gray-400 hover:text-white">
            [WAKE]
          </button>
        </div>
      </header>

      {/* Error */}
      {error && (
        <div className="ascii-box p-2 mb-3 border-red-800 bg-red-950/50 relative z-10">
          <span className="text-red-400 text-xs">ERROR: {error}</span>
        </div>
      )}

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-[280px_1fr] gap-3 min-h-0 relative z-10">
        {/* Left column */}
        <div className="flex flex-col gap-3 min-h-0">
          {/* Location Image */}
          <div className="ascii-box p-1 flex-shrink-0 min-h-[270px] flex items-center justify-center">
            {currentLocation?.imageUrl ? (
              <img
                src={currentLocation.imageUrl}
                alt={currentLocation.name}
                className="w-full h-auto max-h-60 object-contain pixel-img opacity-90"
              />
            ) : (
              <div className="text-gray-600 text-xs">[no image]</div>
            )}
          </div>

          {/* Metrics */}
          <div className="ascii-box p-3 flex-shrink-0">
            <div className="text-xs text-gray-500 mb-2">-- METRICS --</div>
            <MetricBar label="ACT" value={metrics.arousal} color="#6366f1" />
            <MetricBar label="EMO" value={metrics.valence} color="#ec4899" />
            <MetricBar label="SC" value={metrics.selfAwareness} color="#14b8a6" />
            {derivedMetrics && (
              <div className="mt-2 pt-2 border-t border-gray-800 flex gap-4 text-xs">
                <div>
                  <span className="text-gray-600">LUCK:</span>
                  <span className="ml-1 text-blue-400">{Math.round(derivedMetrics.luck)}%</span>
                </div>
                {turbulenceHigh && (
                  <div className={turbulenceCritical ? 'animate-pulse' : ''}>
                    <span className="text-gray-600">TURB:</span>
                    <span className={`ml-1 ${turbulenceCritical ? 'text-red-400' : 'text-orange-400'}`}>
                      {Math.round(turbulence)}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="ascii-box p-2 flex-shrink-0">
            <div className="text-xs text-gray-500 animate-pulse">discovering purpose...</div>
          </div>

          {/* Spatial Map */}
          <div className="flex-shrink-0">
            <SpatialMap dreamLayer={dreamLayer} />
          </div>
        </div>

        {/* Right column - scrollable */}
        <div className="ascii-box p-3 flex flex-col min-h-0 overflow-hidden">
          {showOutcome && (
            <div className="ascii-box p-2 mb-3 flex-shrink-0 border-green-700">
              <span className="text-xs text-green-400">{'>> SUCCESS'}</span>
            </div>
          )}

          {isGenerating ? (
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <span className="animate-pulse">...</span>
              <span className="italic">the dream shifts</span>
            </div>
          ) : currentStep ? (
            <div className="flex flex-col min-h-0 overflow-hidden">
              <div className="text-gray-200 text-sm leading-relaxed mb-4 flex-shrink-0">
                {renderHighlightedText(currentStep.context)}
              </div>

              <div className="flex-1 overflow-y-auto min-h-0 space-y-2">
                {currentStep.decisions.map((decision, i) => (
                  <button
                    key={decision.id}
                    onClick={() => handleDecision(decision.id)}
                    disabled={isLoading}
                    className="ascii-btn w-full p-2 text-left text-sm"
                  >
                    <span className="text-indigo-400">[{i + 1}]</span>{' '}
                    <span className="text-gray-200">{decision.text}</span>
                    <span className="block text-xs mt-1 ml-4 text-gray-600">
                      {getEffectIndicator(decision.effects)}
                    </span>
                  </button>
                ))}

                <div className="mt-4 pt-3 border-t border-gray-800">
                  <input
                    type="text"
                    value={pendingThought}
                    onChange={(e) => setPendingThought(e.target.value)}
                    placeholder="any thoughts?"
                    className="w-full bg-transparent border border-gray-700 px-3 py-2 text-sm text-gray-300 placeholder-gray-600 focus:border-indigo-500 focus:outline-none"
                  />
                  <div className="text-xs text-gray-600 mt-1">
                    (optional - influences next scene)
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm">
              <span className="animate-pulse">loading dream...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
