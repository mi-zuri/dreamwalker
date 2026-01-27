import express from 'express';
import cors from 'cors';
import { randomUUID } from 'crypto';
import type { GameState, StartSessionResponse, StepResponse } from '../../shared/types.js';
import {
  createInitialMetrics,
  getDerivedMetrics,
  applyDrift,
  applyChange,
  checkWakeConditions,
  updateExtremeSteps,
} from './metrics.js';

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// In-memory session store (will use SQLite in Phase 5)
const sessions = new Map<string, GameState>();

// Create initial game state
function createInitialState(sessionId: string, seed: string): GameState {
  return {
    sessionId,
    masterSeed: seed,
    metrics: createInitialMetrics(),
    extremeSteps: { action: 0, emotion: 0, turbulence: 0 },
    dreamLayer: {
      depth: 1,
      stepCount: 0,
      maxSteps: 87,
      locations: [],
      currentLocationIndex: 0,
      poi: {
        type: 'reach',
        description: 'Find your way forward',
        fulfilled: false,
      },
      atmosphere: 'neutral',
      tension: 'low',
      writingStyle: 'sparse and dreamlike',
      visualStyle: 'soft watercolor dreamscape',
      audioStyle: 'distant ambient hum',
    },
    currentStep: null,
    stepHistory: [],
    inventory: null,
    isAwake: false,
    wakeCause: null,
  };
}

// Health check
app.get('/api/health', (_, res) => {
  res.json({ status: 'ok' });
});

// Start new session
app.post('/api/session/start', (req, res) => {
  const sessionId = randomUUID();
  const seed = randomUUID();
  const state = createInitialState(sessionId, seed);

  sessions.set(sessionId, state);

  const response: StartSessionResponse = {
    sessionId,
    initialState: state,
  };

  res.json(response);
});

// Get session state
app.get('/api/session/:id', (req, res) => {
  const state = sessions.get(req.params.id);
  if (!state) {
    res.status(404).json({ error: 'Session not found' });
    return;
  }
  res.json(state);
});

// Get derived metrics
app.get('/api/session/:id/derived', (req, res) => {
  const state = sessions.get(req.params.id);
  if (!state) {
    res.status(404).json({ error: 'Session not found' });
    return;
  }

  const derived = getDerivedMetrics(
    state.metrics,
    state.dreamLayer.depth,
    state.dreamLayer.tension
  );

  res.json(derived);
});

// Apply metric change (for testing)
app.post('/api/session/:id/metrics', (req, res) => {
  const state = sessions.get(req.params.id);
  if (!state) {
    res.status(404).json({ error: 'Session not found' });
    return;
  }

  const { action = 0, emotion = 0, selfConsciousness = 0 } = req.body;
  const depth = state.dreamLayer.depth;

  // Apply changes with depth amplification
  state.metrics.action = applyChange(state.metrics.action, action, depth);
  state.metrics.emotion = applyChange(state.metrics.emotion, emotion, depth);
  state.metrics.selfConsciousness = applyChange(
    state.metrics.selfConsciousness,
    selfConsciousness,
    depth
  );

  // Update extreme step counters
  state.extremeSteps = updateExtremeSteps(state.metrics, state.extremeSteps);

  // Check wake conditions
  const wake = checkWakeConditions(state.metrics, state.extremeSteps);
  if (wake.shouldWake) {
    state.isAwake = true;
    state.wakeCause = wake.cause;
  }

  res.json(state);
});

// Advance step (applies drift)
app.post('/api/session/:id/step', (req, res) => {
  const state = sessions.get(req.params.id);
  if (!state) {
    res.status(404).json({ error: 'Session not found' });
    return;
  }

  if (state.isAwake) {
    res.status(400).json({ error: 'Session ended - player is awake' });
    return;
  }

  // Apply drift
  state.metrics = applyDrift(state.metrics);
  state.dreamLayer.stepCount++;

  // Check max steps
  if (state.dreamLayer.stepCount >= state.dreamLayer.maxSteps) {
    // Check if stable enough for descent
    const stable =
      Math.abs(state.metrics.action) <= 40 &&
      Math.abs(state.metrics.emotion) <= 40;

    if (stable) {
      // Would trigger descent (Phase 3)
      res.json({ ...state, descentTriggered: true });
      return;
    } else {
      state.isAwake = true;
      state.wakeCause = 'stagnation';
    }
  }

  // Update extreme counters after drift
  state.extremeSteps = updateExtremeSteps(state.metrics, state.extremeSteps);

  // Check wake
  const wake = checkWakeConditions(state.metrics, state.extremeSteps);
  if (wake.shouldWake) {
    state.isAwake = true;
    state.wakeCause = wake.cause;
  }

  res.json(state);
});

app.listen(PORT, () => {
  console.log(`Dreamwalker server running on http://localhost:${PORT}`);
});
