import type {
  AppErrorKind,
  EndingComparison,
  GameState,
  NewGameRequest,
  Pos,
  Replay,
  SavedGame,
  Stage,
} from '../types';
import { destinationAt } from '../game/map';
import type { MockGame } from './types';
import { ideaEn } from './games/idea-en';
import { ideaPl } from './games/idea-pl';
import { newsPl } from './games/news-pl';
import { newsWorldEn } from './games/news-world-en';

const FIXTURES: MockGame[] = [ideaEn, ideaPl, newsPl, newsWorldEn];

const STAGE_SCRIPT: [Stage, number][] = [
  ['story', 900],
  ['map', 700],
  ['images', 1100],
  ['music', 600],
  ['finishing', 500],
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Set from the dev panel to exercise the error screens. */
let forcedError: AppErrorKind | null = null;
export function forceError(kind: AppErrorKind | null) {
  forcedError = kind;
}

export class MockApiError extends Error {
  kind: AppErrorKind;

  constructor(kind: AppErrorKind, detail?: string) {
    super(detail ?? kind);
    this.kind = kind;
  }
}

function raiseIfForced() {
  if (forcedError) {
    const kind = forcedError;
    forcedError = null;
    throw new MockApiError(kind);
  }
}

/** Live games, keyed by game id. Cloned per run so replays do not mutate fixtures. */
const live = new Map<string, { fixture: MockGame; state: GameState }>();
const finished: SavedGame[] = [];

function pickFixture(req: NewGameRequest): MockGame {
  const byMode = FIXTURES.filter((f) => f.request.mode === req.mode);
  const exact = byMode.find(
    (f) =>
      f.request.story_language === req.story_language &&
      (req.mode === 'idea' || f.request.region === req.region),
  );
  return exact ?? byMode.find((f) => f.request.mode === req.mode) ?? FIXTURES[0];
}

export async function createGame(req: NewGameRequest): Promise<{ game_id: string }> {
  await sleep(250);
  raiseIfForced();
  const fixture = pickFixture(req);
  const id = `${fixture.id}-${Date.now().toString(36)}`;
  const state: GameState = structuredClone(fixture.state);
  state.game_id = id;
  // The menu is authoritative for language, even when the fixture differs.
  state.ui_language = req.ui_language;
  state.story_language = req.story_language;
  live.set(id, { fixture, state });
  return { game_id: id };
}

/** Stands in for the SSE progress stream. Returns a cancel function. */
export function streamStages(
  _gameId: string,
  onStage: (stage: Stage) => void,
  onReady: () => void,
): () => void {
  let cancelled = false;
  (async () => {
    for (const [stage, ms] of STAGE_SCRIPT) {
      if (cancelled) return;
      onStage(stage);
      await sleep(ms);
    }
    if (!cancelled) onReady();
  })();
  return () => {
    cancelled = true;
  };
}

function requireGame(id: string) {
  const entry = live.get(id);
  if (!entry) throw new MockApiError('network', `unknown game ${id}`);
  return entry;
}

export async function getGame(id: string): Promise<GameState> {
  await sleep(80);
  return structuredClone(requireGame(id).state);
}

/** Moves the player one tile; arriving on a destination swaps in its scene. */
export async function move(id: string, to: Pos): Promise<GameState> {
  await sleep(40);
  const { fixture, state } = requireGame(id);
  state.player_pos = to;

  const dest = destinationAt(state.map, to);
  if (dest) {
    if (!state.visited.includes(dest.key)) state.visited.push(dest.key);
    if (!state.unlocked.includes(dest.key)) state.unlocked.push(dest.key);
    const scene = fixture.scenes[dest.location_id];
    if (scene) {
      state.current_scene = scene;
      const done = state.resolved.includes(dest.key);
      state.choices = done ? [] : (fixture.choices[dest.location_id] ?? []);
      state.open_question =
        !done && fixture.openQuestionAt === dest.location_id
          ? {
              id: `q-${dest.location_id}`,
              prompt:
                state.story_language === 'pl' ? 'Co powiedziałeś?' : 'What did you say?',
            }
          : undefined;
    }
  }
  return structuredClone(state);
}

export async function choose(id: string, choiceId: string): Promise<GameState> {
  await sleep(320);
  const { state } = requireGame(id);
  const choice = state.choices.find((c) => c.id === choiceId);
  state.turn += 1;

  // Advance the next pending beat; a mid-list choice counts as divergence.
  const pending = state.beat_progress.find((b) => b.status === 'pending');
  if (pending) {
    const index = state.choices.findIndex((c) => c.id === choiceId);
    pending.status = index === 1 ? 'diverged' : 'matched';
    if (pending.status === 'diverged') {
      state.divergence = Math.min(1, state.divergence + 0.25);
    }
  }

  state.choices = [];
  if (choice) {
    state.current_scene = {
      ...state.current_scene,
      id: `${state.current_scene.id}-t${state.turn}`,
    };
  }

  const here = destinationAt(state.map, state.player_pos);
  if (here && !state.resolved.includes(here.key)) state.resolved.push(here.key);

  if (state.resolved.length >= state.map.destinations.length) {
    state.finished = true;
  }
  return structuredClone(state);
}

export async function answer(id: string, _text: string): Promise<GameState> {
  await sleep(280);
  const { state } = requireGame(id);
  state.open_question = undefined;
  return structuredClone(state);
}

export async function getEnding(id: string): Promise<EndingComparison> {
  await sleep(500);
  const { fixture, state } = requireGame(id);
  if (!finished.some((g) => g.game_id === id)) {
    finished.unshift({
      game_id: id,
      mode: state.mode,
      region: state.region,
      title: fixture.ending.title,
      played_at: new Date().toISOString(),
      story_language: state.story_language,
      match_score: fixture.ending.match_score,
      image_url: state.current_scene.image_url,
    });
  }
  return { ...structuredClone(fixture.ending), game_id: id };
}

/** Seeded so the library screen has content on a fresh load. */
const SEEDED: SavedGame[] = FIXTURES.map((f, i) => ({
  game_id: f.id,
  mode: f.request.mode,
  region: f.request.region,
  title: f.ending.title,
  played_at: new Date(Date.now() - (i + 1) * 36e5 * 11).toISOString(),
  story_language: f.request.story_language,
  match_score: f.ending.match_score,
  image_url: f.state.current_scene.image_url,
}));

export async function listGames(): Promise<SavedGame[]> {
  await sleep(200);
  raiseIfForced();
  return [...finished, ...SEEDED];
}

export async function getReplay(id: string): Promise<Replay> {
  await sleep(300);
  const fixture =
    FIXTURES.find((f) => f.id === id) ?? live.get(id)?.fixture ?? FIXTURES[0];
  return structuredClone(fixture.replay);
}
