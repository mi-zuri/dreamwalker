import { create } from 'zustand';
import type { GameState, Metrics, DerivedMetrics } from '../../../shared/types';

const API_BASE = '/api';

interface GameStore {
  // State
  sessionId: string | null;
  gameState: GameState | null;
  derivedMetrics: DerivedMetrics | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  startSession: () => Promise<void>;
  fetchDerivedMetrics: () => Promise<void>;
  applyMetricChange: (changes: Partial<Metrics>) => Promise<void>;
  advanceStep: () => Promise<void>;
  reset: () => void;
}

export const useGameStore = create<GameStore>((set, get) => ({
  sessionId: null,
  gameState: null,
  derivedMetrics: null,
  isLoading: false,
  error: null,

  startSession: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      set({
        sessionId: data.sessionId,
        gameState: data.initialState,
        isLoading: false,
      });
      // Fetch derived metrics
      get().fetchDerivedMetrics();
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

  applyMetricChange: async (changes) => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/metrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(changes),
      });
      const data = await res.json();
      set({ gameState: data, isLoading: false });
      get().fetchDerivedMetrics();
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  advanceStep: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      set({ gameState: data, isLoading: false });
      get().fetchDerivedMetrics();
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  reset: () => {
    set({
      sessionId: null,
      gameState: null,
      derivedMetrics: null,
      isLoading: false,
      error: null,
    });
  },
}));
