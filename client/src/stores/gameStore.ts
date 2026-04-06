import { create } from 'zustand';
import type { GameState, DerivedMetrics, Step } from '../../../shared/types';

const API_BASE = '/api';

interface AttemptOutcome {
  success: boolean;
  text: string;
  metricsChanged: { action: number; emotion: number };
}

interface GameStore {
  // State
  sessionId: string | null;
  gameState: GameState | null;
  derivedMetrics: DerivedMetrics | null;
  currentStep: Step | null;
  attemptOutcome: AttemptOutcome | null;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;

  // Actions
  startSession: (initialThought?: string) => Promise<void>;
  fetchDerivedMetrics: () => Promise<void>;
  generateStep: (imaginedElement?: string) => Promise<void>;
  makeDecision: (decisionId: string) => Promise<void>;
  reset: () => void;
}

export const useGameStore = create<GameStore>((set, get) => ({
  sessionId: null,
  gameState: null,
  derivedMetrics: null,
  currentStep: null,
  attemptOutcome: null,
  isLoading: false,
  isGenerating: false,
  error: null,

  startSession: async (initialThought?: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initialThought: initialThought || '' }),
      });
      const data = await res.json();
      set({
        sessionId: data.sessionId,
        gameState: data.initialState,
        isLoading: false,
      });
      await get().fetchDerivedMetrics();
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  fetchDerivedMetrics: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/derived`);
      const data = await res.json();
      set({ derivedMetrics: data });
    } catch (err) {
      console.error('Failed to fetch derived metrics:', err);
    }
  },

  generateStep: async (imaginedElement?: string) => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({
      isGenerating: true,
      error: null,
      // Don't clear attemptOutcome - it should persist to show success/failure
    });

    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imaginedElement }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to generate step');
      }

      const data = await res.json();
      set({
        gameState: data.state,
        currentStep: data.step,
        isGenerating: false,
      });
      await get().fetchDerivedMetrics();
    } catch (err) {
      set({ error: (err as Error).message, isGenerating: false });
    }
  },

  makeDecision: async (decisionId: string) => {
    const { sessionId } = get();
    if (!sessionId) return;

    // Clear previous outcomes when making a new decision
    set({ isLoading: true, error: null, attemptOutcome: null });
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decisionId }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to make decision');
      }

      const data = await res.json();

      // Handle new response structure
      set({
        gameState: data.state,
        attemptOutcome: {
          success: data.success,
          text: data.success ? 'Success!' : 'Failed!',
          metricsChanged: {
            action: data.appliedEffects.arousal,
            emotion: data.appliedEffects.valence,
          },
        },
        isLoading: false,
      });

      await get().fetchDerivedMetrics();

      // Check if game ended
      if (data.woke) {
        // Game ended, WakeScreen will render based on gameState.isAwake
        return;
      }

      // Note: generateStep should be called by the component after makeDecision
      // to allow passing optional thought/imaginedElement
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  reset: () => {
    set({
      sessionId: null,
      gameState: null,
      derivedMetrics: null,
      currentStep: null,
      attemptOutcome: null,
      isLoading: false,
      isGenerating: false,
      error: null,
    });
  },
}));
