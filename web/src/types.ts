/**
 * Game types for the mock-only phase.
 *
 * Phase 2 replaces this file with types generated from the backend OpenAPI
 * schema (`bun run gen:api` -> `src/api/schema.d.ts`). Keep the shapes here
 * identical to the Pydantic models so that swap is mechanical.
 */

export type Mode = 'idea' | 'news';
export type Region = 'pl' | 'world';
export type Language = 'pl' | 'en';
export type SafetyClass = 'allowed' | 'safe_mode' | 'blocked';

/** Coarse progress enum; the UI only ever shows a vague label for these. */
export type Stage = 'story' | 'map' | 'images' | 'music' | 'finishing';

export interface StyleCard {
  genre: string;
  narrative_voice: string;
  tone: string;
  protagonist_role: string;
  visual_style: string;
  music_mood: string;
  pacing: string;
}

export interface Pos {
  x: number;
  y: number;
}

export interface Destination {
  /** The character used for this destination in `GameMap.tiles`. */
  key: string;
  location_id: string;
  name: string;
}

export interface Door {
  key: string;
  pos: Pos;
  /** Destination that must be reached before this door opens. */
  unlock_from: string;
}

/**
 * Tile grid. Characters: `#` wall, `.` floor, `+` locked door,
 * `@` start, `A`-`F` destinations.
 */
export interface GameMap {
  width: number;
  height: number;
  tiles: string[];
  destinations: Destination[];
  doors: Door[];
}

export interface ImageCredit {
  source_url: string;
  credit: string;
}

export interface Scene {
  id: string;
  location_id: string;
  /** May contain `[POI:..]`, `[LOC:..]` and `[KEY:..]` highlight markers. */
  text: string;
  image_url?: string;
  image_credit?: ImageCredit;
}

export interface Choice {
  id: string;
  text: string;
}

export interface OpenQuestion {
  id: string;
  prompt: string;
}

export type BeatStatus = 'pending' | 'matched' | 'diverged' | 'skipped';

export interface BeatProgress {
  beat_id: string;
  status: BeatStatus;
}

/** Travel shows the full map; scene shows the location's text and choices. */
export type View = 'travel' | 'scene';

export interface GameState {
  game_id: string;
  mode: Mode;
  view: View;
  region?: Region;
  story_language: Language;
  ui_language: Language;
  safety_class: SafetyClass;
  /** Shown before the game starts when `safety_class` is `safe_mode`. */
  content_note?: string;
  /** "Based on real events, dramatized" - news mode only. */
  source_note?: string;
  style_card: StyleCard;
  map: GameMap;
  player_pos: Pos;
  /** Destinations the player has stepped on. */
  visited: string[];
  /** Destinations where the player has actually made a choice. */
  resolved: string[];
  /** Destinations whose doors are now open. */
  unlocked: string[];
  current_scene: Scene;
  choices: Choice[];
  open_question?: OpenQuestion;
  beat_progress: BeatProgress[];
  divergence: number;
  turn: number;
  finished: boolean;
}

export interface CanonBeat {
  id: string;
  title: string;
  summary: string;
  sources: string[];
}

export interface PlayerBeat {
  beat_id: string;
  status: BeatStatus;
  what_you_did: string;
}

export interface EndingComparison {
  game_id: string;
  mode: Mode;
  /** News mode only - Idea mode has no canon to score against. */
  match_score?: number;
  title: string;
  summary: string;
  canon: CanonBeat[];
  player: PlayerBeat[];
  style_card: StyleCard;
  sources: { url: string; title: string }[];
}

export interface SavedGame {
  game_id: string;
  mode: Mode;
  region?: Region;
  title: string;
  played_at: string;
  story_language: Language;
  match_score?: number;
  image_url?: string;
}

export interface ReplayTurn {
  turn: number;
  scene: Scene;
  player_pos: Pos;
  chosen?: string;
  answer?: string;
}

export interface Replay {
  game_id: string;
  title: string;
  turns: ReplayTurn[];
}

export interface NewGameRequest {
  mode: Mode;
  idea?: string;
  region?: Region;
  story_language: Language;
  ui_language: Language;
}

export type AppErrorKind =
  | 'network'
  | 'generation_failed'
  | 'pool_empty'
  | 'budget_exceeded'
  | 'blocked_event'
  | 'auth';

export interface AppError {
  kind: AppErrorKind;
  detail?: string;
}
