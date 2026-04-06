export interface Metrics {
  arousal: number;
  valence: number;
  selfAwareness: number;
}

export interface DerivedMetrics {
  luck: number;
  turbulence: number;
}

export type POIType = string;

export interface POI {
  type: POIType;
  description: string;
  fulfilled: boolean;
}

export interface Decision {
  id: string;
  text: string;
  successEffects: { arousal: number; valence: number; selfAwareness: number };
  failureEffects: { arousal: number; valence: number; selfAwareness: number };
  successChance: number;
  leadsToNode: string | null;
}

export interface Location {
  id: string;
  name: string;
  description: string;
  visualStyle: string;
  audioStyle: string;
  imageUrl?: string;
  audioUrl?: string;
}

// Single game step
export interface Step {
  id: string;
  stepNumber: number;
  context: string;
  decisions: Decision[];
  locationId: string;
  poiVisible: boolean;
  isTimed: boolean;
  timedDeadline?: number;
}

// Wake cause tags
export type WakeCause =
  | 'emotional_overload'
  | 'action_overload'
  | 'lucidity_break'
  | 'dissolution';

export interface DreamLayer {
  stepCount: number;
  maxSteps: number;
  locations: Location[];
  currentLocationIndex: number;
  poi: POI | null;
  world: string;
  writingStyle: string;
  visualStyle: string;
  audioStyle: string;
}

// Stability tracking for descent
export interface StabilityTracker {
  consecutiveStable: number;
}

// Location history for backtrack detection
export interface LocationHistory {
  locationIds: string[];
}

export interface StoryEntry {
  context: string;
  chosenAction: string;
  outcome?: string;
}

// Claude conversation message
export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

// Last step data for Director
export interface LastStepData {
  storytellerOutput: string;
  choices: Array<{ id: string; text: string }>;
  judgeOutput: JudgeOutput;
}

// Session state
export interface GameState {
  sessionId: string;
  masterSeed: string;
  metrics: Metrics;
  dreamLayer: DreamLayer;
  currentStep: Step | null;
  stepHistory: string[];
  storyHistory: StoryEntry[];
  locationHistory: LocationHistory;
  stabilityTracker: StabilityTracker;
  inventory: string | null;
  isAwake: boolean;
  wakeCause: WakeCause | null;
  initialThought: string | null;
  conversationHistory: ConversationMessage[];
  lastStepData: LastStepData | null;
}

// Style presets for pre-game selection
export interface StylePreferences {
  visual: VisualStylePreset;
  audio: AudioStylePreset;
  writing: WritingStylePreset;
}

export type VisualStylePreset = string;

export type AudioStylePreset = string;

export type WritingStylePreset = string;

// API request/response types
export interface StartSessionRequest {
  initialThought?: string;
}

export interface StartSessionResponse {
  sessionId: string;
  initialState: GameState;
}

export interface MakeDecisionRequest {
  sessionId: string;
  decisionId: string;
}

export interface StepResponse {
  state: GameState;
  step: Step;
  outcome?: {
    text: string;
    metricsChanged: Partial<Metrics>;
  };
}

// Agent response types for multi-agent Claude system
export interface InitiatorOutput {
  world: string;
  writingStyle: string;
  visualStyle: string;
  audioStyle: string;
}

export interface JudgeOutput {
  event: Metrics;
  choices: Metrics[];
}

export interface DirectorOutput {
  locationChange: boolean;
  poi: boolean;
  timedEvent: boolean;
  guidance: string;
}
