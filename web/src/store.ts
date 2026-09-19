import { create } from 'zustand';
import * as api from './mocks/api';
import { MockApiError } from './mocks/api';
import type {
  AppError,
  EndingComparison,
  GameState,
  Language,
  Pos,
  Region,
  Replay,
  SavedGame,
  Stage,
} from './types';

export type Screen =
  | 'login'
  | 'menu'
  | 'contentNote'
  | 'loading'
  | 'game'
  | 'ending'
  | 'library'
  | 'replay'
  | 'error';

interface User {
  name: string;
  email: string;
}

interface AppStore {
  screen: Screen;
  user: User | null;
  signingIn: boolean;

  uiLanguage: Language;
  storyLanguage: Language;
  idea: string;
  region: Region;

  stage: Stage | null;
  game: GameState | null;
  ending: EndingComparison | null;
  saved: SavedGame[];
  replay: Replay | null;
  replayIndex: number;
  error: AppError | null;
  busy: boolean;

  setUiLanguage: (l: Language) => void;
  setStoryLanguage: (l: Language) => void;
  setIdea: (v: string) => void;
  setRegion: (r: Region) => void;

  signIn: () => Promise<void>;
  signOut: () => void;
  start: () => Promise<void>;
  acceptContentNote: () => void;
  declineContentNote: () => void;
  moveTo: (pos: Pos) => Promise<void>;
  choose: (choiceId: string) => Promise<void>;
  answer: (text: string) => Promise<void>;
  openLibrary: () => Promise<void>;
  openReplay: (gameId: string) => Promise<void>;
  setReplayIndex: (i: number) => void;
  toMenu: () => void;
  dismissError: () => void;
}

function toAppError(e: unknown): AppError {
  if (e instanceof MockApiError) return { kind: e.kind, detail: e.message };
  return { kind: 'network', detail: e instanceof Error ? e.message : String(e) };
}

export const useStore = create<AppStore>((set, get) => ({
  screen: 'login',
  user: null,
  signingIn: false,

  uiLanguage: 'en',
  storyLanguage: 'en',
  idea: '',
  region: 'world',

  stage: null,
  game: null,
  ending: null,
  saved: [],
  replay: null,
  replayIndex: 0,
  error: null,
  busy: false,

  setUiLanguage: (uiLanguage) => set({ uiLanguage }),
  setStoryLanguage: (storyLanguage) => set({ storyLanguage }),
  setIdea: (idea) => set({ idea }),
  setRegion: (region) => set({ region }),

  signIn: async () => {
    set({ signingIn: true });
    await new Promise((r) => setTimeout(r, 700));
    set({
      signingIn: false,
      user: { name: 'Gracz', email: 'player@example.com' },
      screen: 'menu',
    });
  },

  signOut: () => set({ user: null, screen: 'login', game: null, ending: null }),

  start: async () => {
    const { idea, region, storyLanguage, uiLanguage } = get();
    const trimmed = idea.trim();
    const request = {
      mode: (trimmed ? 'idea' : 'news') as 'idea' | 'news',
      idea: trimmed || undefined,
      region: trimmed ? undefined : region,
      story_language: storyLanguage,
      ui_language: uiLanguage,
    };

    set({ screen: 'loading', stage: 'story', error: null, ending: null });
    try {
      const { game_id } = await api.createGame(request);
      await new Promise<void>((resolve) => {
        api.streamStages(
          game_id,
          (stage) => set({ stage }),
          () => resolve(),
        );
      });
      const game = await api.getGame(game_id);
      set({
        game,
        stage: null,
        screen: game.safety_class === 'safe_mode' ? 'contentNote' : 'game',
      });
    } catch (e) {
      set({ error: toAppError(e), screen: 'error', stage: null });
    }
  },

  acceptContentNote: () => set({ screen: 'game' }),
  declineContentNote: () => set({ screen: 'menu', game: null }),

  moveTo: async (pos) => {
    const game = get().game;
    if (!game || game.finished) return;
    try {
      set({ game: await api.move(game.game_id, pos) });
    } catch (e) {
      set({ error: toAppError(e), screen: 'error' });
    }
  },

  choose: async (choiceId) => {
    const game = get().game;
    if (!game) return;
    set({ busy: true });
    try {
      const next = await api.choose(game.game_id, choiceId);
      set({ game: next, busy: false });
      if (next.finished) {
        const ending = await api.getEnding(next.game_id);
        set({ ending, screen: 'ending' });
      }
    } catch (e) {
      set({ error: toAppError(e), screen: 'error', busy: false });
    }
  },

  answer: async (text) => {
    const game = get().game;
    if (!game) return;
    set({ busy: true });
    try {
      set({ game: await api.answer(game.game_id, text), busy: false });
    } catch (e) {
      set({ error: toAppError(e), screen: 'error', busy: false });
    }
  },

  openLibrary: async () => {
    set({ screen: 'library', busy: true });
    try {
      set({ saved: await api.listGames(), busy: false });
    } catch (e) {
      set({ error: toAppError(e), screen: 'error', busy: false });
    }
  },

  openReplay: async (gameId) => {
    set({ busy: true });
    try {
      const replay = await api.getReplay(gameId);
      set({ replay, replayIndex: 0, screen: 'replay', busy: false });
    } catch (e) {
      set({ error: toAppError(e), screen: 'error', busy: false });
    }
  },

  setReplayIndex: (replayIndex) => set({ replayIndex }),

  toMenu: () =>
    set({ screen: 'menu', game: null, ending: null, replay: null, error: null, stage: null }),

  dismissError: () => set({ error: null, screen: get().user ? 'menu' : 'login' }),
}));
