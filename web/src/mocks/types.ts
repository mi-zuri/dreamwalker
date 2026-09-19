import type {
  Choice,
  EndingComparison,
  GameState,
  NewGameRequest,
  Replay,
  Scene,
} from '../types';

/** A complete scripted run: enough to play the whole loop with no backend. */
export interface MockGame {
  id: string;
  /** Matched against the player's menu selection to pick this fixture. */
  request: NewGameRequest;
  state: GameState;
  /** Keyed by `location_id`. */
  scenes: Record<string, Scene>;
  /** Keyed by `location_id`. */
  choices: Record<string, Choice[]>;
  /** Location whose scene asks the player to write something. */
  openQuestionAt: string;
  ending: EndingComparison;
  replay: Replay;
}
