import { useCallback, useState, useEffect } from 'react';
import { useGameStore } from '../stores/gameStore';
import { useAudioStream } from '../hooks/useAudioStream';
import { MetricBar } from './MetricBar';
import { DerivedMetrics } from './DerivedMetrics';
import { WakeScreen } from './WakeScreen';
import { TimedEvent } from './TimedEvent';
import { SpatialMap } from './SpatialMap';
import { StartScreen } from './StyleSelector';

// Parse highlighted text markers and render with colors
// [POI:text] - indigo for objectives
// [LOC:text] - teal for locations
// [KEY:text] - pink for key elements
function renderHighlightedText(text: string): React.ReactNode[] {
  const pattern = /\[(POI|LOC|KEY):([^\]]+)\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    // Add the highlighted span
    const [, type, content] = match;
    const colorClass = {
      POI: 'text-indigo-400',
      LOC: 'text-teal-400',
      KEY: 'text-pink-400',
    }[type] || 'text-gray-200';

    parts.push(
      <span key={key++} className={colorClass}>
        {content}
      </span>
    );

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

export function Game() {
  const {
    sessionId,
    gameState,
    derivedMetrics,
    currentStep,
    attemptOutcome,
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
  const [hasGeneratedInitial, setHasGeneratedInitial] = useState(false);
  const [hasStartedAudio, setHasStartedAudio] = useState(false);

  // After session starts, immediately generate first step
  useEffect(() => {
    // Don't auto-generate if we're in the middle of a decision (isLoading)
    if (gameState && !currentStep && !isGenerating && !isLoading && !hasGeneratedInitial && !gameState.isAwake) {
      setHasGeneratedInitial(true);
      generateStep();
    }
  }, [gameState, currentStep, isGenerating, isLoading, hasGeneratedInitial, generateStep]);

  // Start audio only after first step generates (so scene data is ready)
  useEffect(() => {
    if (currentStep && !hasStartedAudio && !isGenerating) {
      setHasStartedAudio(true);
      resumeAudio();
    }
  }, [currentStep, hasStartedAudio, isGenerating, resumeAudio]);

  const handleStart = useCallback(
    (initialThought?: string) => {
      setHasGeneratedInitial(false);
      setHasStartedAudio(false);
      startSession(initialThought);
      // Audio will start after first step generates
    },
    [startSession]
  );

  const handleDecision = useCallback(
    async (decisionId: string) => {
      resumeAudio();
      const thought = pendingThought.trim();
      setPendingThought('');
      await makeDecision(decisionId);
      // After decision completes, generate next step with pending thought
      if (thought) {
        await generateStep(thought);
      } else {
        await generateStep();
      }
    },
    [makeDecision, resumeAudio, pendingThought, generateStep]
  );

  // Show start screen if no game state exists
  if (!gameState) {
    return (
      <StartScreen
        onStart={handleStart}
        isLoading={isLoading}
        isWaitingForImage={false}
      />
    );
  }

  // Calculate current location after we know gameState exists
  const currentLocation = gameState.dreamLayer.locations[gameState.dreamLayer.currentLocationIndex];

  // Show wake screen if awake
  if (gameState.isAwake && gameState.wakeCause) {
    return (
      <WakeScreen
        cause={gameState.wakeCause}
        steps={gameState.dreamLayer.stepCount}
        onRestart={reset}
      />
    );
  }

  // Show start screen with loading if waiting for first step
  if (!currentStep) {
    return (
      <StartScreen
        onStart={handleStart}
        isLoading={isLoading}
        isWaitingForImage={true}
      />
    );
  }

  const { metrics, dreamLayer } = gameState;

  const getEffectIndicator = (effects: { arousal: number; valence: number; selfAwareness: number }) => {
    const labels: Record<string, string> = { arousal: 'ACT', valence: 'EMO', selfAwareness: 'SC' };
    return Object.entries(effects)
      .filter(([, v]) => v !== 0)
      .map(([k, v]) => `[${labels[k]}${v > 0 ? '+' : '-'}]`)
      .join(' ');
  };

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
          <button
            onClick={reset}
            className="ascii-btn px-2 py-1 text-xs text-gray-400 hover:text-white"
          >
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
              <div className="text-gray-600 text-xs">
                [no image]
              </div>
            )}
          </div>

          {/* Metrics */}
          <div className="ascii-box p-3 flex-shrink-0">
            <div className="text-xs text-gray-500 mb-2">-- METRICS --</div>
            <MetricBar label="ACT" value={metrics.arousal} color="#6366f1" showWarning />
            <MetricBar label="EMO" value={metrics.valence} color="#ec4899" showWarning />
            <MetricBar label="SC" value={metrics.selfAwareness} color="#14b8a6" showWarning />
            {derivedMetrics && (
              <div className="mt-2 pt-2 border-t border-gray-800">
                <DerivedMetrics luck={derivedMetrics.luck} turbulence={derivedMetrics.turbulence} />
              </div>
            )}
          </div>

          {/* POI */}
          <div className="ascii-box p-2 flex-shrink-0">
            {dreamLayer.poi ? (
              <>
                <div className="text-xs text-indigo-400 uppercase">{dreamLayer.poi.type}</div>
                <div className="text-xs text-gray-300 mt-1">{dreamLayer.poi.description}</div>
              </>
            ) : (
              <div className="text-xs text-gray-500 animate-pulse">discovering purpose...</div>
            )}
          </div>

          {/* Spatial Map */}
          <div className="flex-shrink-0">
            <SpatialMap dreamLayer={dreamLayer} />
          </div>
        </div>

        {/* Right column - scrollable */}
        <div className="ascii-box p-3 flex flex-col min-h-0 overflow-hidden">
          {/* Risky Outcome */}
          {attemptOutcome && (
            <div
              className={`ascii-box p-2 mb-3 flex-shrink-0 ${
                attemptOutcome.success ? 'border-green-700' : 'border-red-700'
              }`}
            >
              <span className={`text-xs ${attemptOutcome.success ? 'text-green-400' : 'text-red-400'}`}>
                {attemptOutcome.success ? '>> SUCCESS' : '>> FAILED'}
              </span>
            </div>
          )}

          {/* Step Content */}
          {isGenerating ? (
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <span className="animate-pulse">...</span>
              <span className="italic">the dream shifts</span>
            </div>
          ) : currentStep ? (
            <div className="flex flex-col min-h-0 overflow-hidden">
              {/* Context with highlighted text */}
              <div className="text-gray-200 text-sm leading-relaxed mb-4 flex-shrink-0">
                {renderHighlightedText(currentStep.context)}
              </div>

              {/* Decisions - scrollable */}
              <div className="flex-1 overflow-y-auto min-h-0 space-y-2">
                {currentStep.isTimed && currentStep.timedDeadline ? (
                  <TimedEvent
                    decisions={currentStep.decisions}
                    deadline={currentStep.timedDeadline}
                    onDecision={handleDecision}
                  />
                ) : (
                  <>
                    {currentStep.decisions.map((decision, i) => {
                      const isRisky = decision.successChance < 1;
                      return (
                        <button
                          key={decision.id}
                          onClick={() => handleDecision(decision.id)}
                          disabled={isLoading}
                          className={`ascii-btn w-full p-2 text-left text-sm ${
                            isRisky ? 'border-yellow-900/50' : ''
                          }`}
                        >
                          <span className={isRisky ? 'text-yellow-500' : 'text-indigo-400'}>
                            [{i + 1}]
                          </span>{' '}
                          <span className={isRisky ? 'text-yellow-100' : 'text-gray-200'}>
                            {decision.text}
                          </span>
                          <span className={`block text-xs mt-1 ml-4 ${
                            isRisky ? 'text-yellow-700' : 'text-gray-600'
                          }`}>
                            {isRisky
                              ? `${Math.round(decision.successChance * 100)}% chance`
                              : getEffectIndicator(decision.successEffects)}
                          </span>
                        </button>
                      );
                    })}

                    {/* Thought input under choices */}
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
                  </>
                )}
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
