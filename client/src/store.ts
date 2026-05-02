import { create } from 'zustand';
import type { GameState, DerivedMetrics, Step } from '../../shared/types';

const API_BASE = '/api';

interface GameStore {
  sessionId: string | null;
  gameState: GameState | null;
  derivedMetrics: DerivedMetrics | null;
  currentStep: Step | null;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;

  startSession: (initialThought?: string) => Promise<void>;
  fetchDerivedMetrics: () => Promise<void>;
  generateStep: (imaginedElement?: string) => Promise<void>;
  makeDecision: (decisionId: string) => Promise<{ woke: boolean } | null>;
  reset: () => void;
}

export const useGameStore = create<GameStore>((set, get) => ({
  sessionId: null,
  gameState: null,
  derivedMetrics: null,
  currentStep: null,
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
      set({ sessionId: data.sessionId, gameState: data.initialState, isLoading: false });
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
    set({ isGenerating: true, error: null });
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
      set({ gameState: data.state, currentStep: data.step, isGenerating: false });
      await get().fetchDerivedMetrics();
    } catch (err) {
      set({ error: (err as Error).message, isGenerating: false });
    }
  },

  makeDecision: async (decisionId: string) => {
    const { sessionId } = get();
    if (!sessionId) return null;
    set({ isLoading: true, error: null });
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
      set({ gameState: data.state, isLoading: false });
      await get().fetchDerivedMetrics();
      return { woke: data.woke };
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
      return null;
    }
  },

  reset: () => {
    set({
      sessionId: null,
      gameState: null,
      derivedMetrics: null,
      currentStep: null,
      isLoading: false,
      isGenerating: false,
      error: null,
    });
  },
}));
