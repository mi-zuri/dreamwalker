import { create } from 'zustand';
import * as api from './api/client';
import { ApiError } from './api/client';
import * as auth from './auth/firebase';
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

/**
 * How long movement must settle before it is committed to the server.
 * Click-to-move steps every 90ms, so one walk becomes one request.
 */
const MOVE_SETTLE_MS = 140;

interface AppStore {
  screen: Screen;
  user: User | null;
  signingIn: boolean;
  restoring: boolean;

  uiLanguage: Language;
  storyLanguage: Language;
  idea: string;
  region: Region;

  stage: Stage | null;
  game: GameState | null;
  /** Where the player looks like they are, ahead of the server confirming. */
  localPos: Pos | null;
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

  restoreSession: () => Promise<void>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  start: () => Promise<void>;
  acceptContentNote: () => void;
  declineContentNote: () => void;
  moveTo: (pos: Pos) => void;
  choose: (choiceId: string) => Promise<void>;
  answer: (text: string) => Promise<void>;
  setOff: () => Promise<void>;
  openLibrary: () => Promise<void>;
  openReplay: (gameId: string) => Promise<void>;
  setReplayIndex: (i: number) => void;
  toMenu: () => void;
  dismissError: () => void;
}

function toAppError(e: unknown): AppError {
  if (e instanceof ApiError) return { kind: e.kind, detail: e.message };
  return { kind: 'network', detail: e instanceof Error ? e.message : String(e) };
}

/** Pending move commit, kept outside the store so it never triggers a render. */
let moveTimer: ReturnType<typeof setTimeout> | undefined;

export const useStore = create<AppStore>((set, get) => ({
  screen: 'login',
  user: null,
  signingIn: false,
  restoring: true,

  uiLanguage: 'en',
  storyLanguage: 'en',
  idea: '',
  region: 'world',

  stage: null,
  game: null,
  localPos: null,
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

  restoreSession: async () => {
    const account = await auth.restore();
    if (!account) return set({ restoring: false });
    try {
      // Confirms the token verifies and the account is on the invite list.
      await api.me();
      set({ user: account, screen: 'menu', restoring: false });
    } catch {
      await auth.signOut();
      set({ restoring: false });
    }
  },

  signIn: async () => {
    set({ signingIn: true, error: null });
    try {
      const account = await auth.signIn();
      await api.me();
      set({ signingIn: false, user: account, screen: 'menu' });
    } catch (e) {
      await auth.signOut().catch(() => {});
      set({ signingIn: false, error: toAppError(e), screen: 'error' });
    }
  },

  signOut: async () => {
    await auth.signOut();
    set({ user: null, screen: 'login', game: null, ending: null, localPos: null });
  },

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

    set({ screen: 'loading', stage: 'story', error: null, ending: null, localPos: null });
    try {
      const { game_id } = await api.createGame(request);
      await new Promise<void>((resolve, reject) => {
        api.streamStages(game_id, (stage) => set({ stage }), resolve, reject);
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

  /**
   * Movement is shown immediately and committed once the player stops, so a
   * ten-tile walk is one request. The server re-validates the destination
   * against its own map and its answer overwrites the optimistic position.
   */
  moveTo: (pos) => {
    const game = get().game;
    if (!game || game.finished) return;
    set({ localPos: pos });

    clearTimeout(moveTimer);
    moveTimer = setTimeout(async () => {
      const target = get().localPos;
      const current = get().game;
      if (!target || !current) return;
      try {
        const next = await api.move(current.game_id, target);
        set({ game: next, localPos: null });
      } catch (e) {
        set({ localPos: null, error: toAppError(e), screen: 'error' });
      }
    }, MOVE_SETTLE_MS);
  },

  choose: async (choiceId) => {
    const game = get().game;
    if (!game) return;
    set({ busy: true });
    try {
      const next = await api.choose(game.game_id, choiceId);
      set({ game: next, busy: false, localPos: null });
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

  setOff: async () => {
    const game = get().game;
    if (!game) return;
    try {
      set({ game: await api.setOff(game.game_id) });
    } catch (e) {
      set({ error: toAppError(e), screen: 'error' });
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
    set({
      screen: 'menu',
      game: null,
      localPos: null,
      ending: null,
      replay: null,
      error: null,
      stage: null,
    }),

  dismissError: () => set({ error: null, screen: get().user ? 'menu' : 'login' }),
}));
