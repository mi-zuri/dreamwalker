export interface Metrics {
  arousal: number;
  valence: number;
  selfAwareness: number;
}

export interface DerivedMetrics {
  luck: number;
  turbulence: number;
}

export interface Decision {
  id: string;
  text: string;
  effects: Metrics;
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

export interface Step {
  id: string;
  stepNumber: number;
  context: string;
  decisions: Decision[];
  locationId: string;
}

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
  world: string;
  writingStyle: string;
  visualStyle: string;
  audioStyle: string;
}

export interface StoryEntry {
  context: string;
  chosenAction: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface LastStepData {
  storytellerOutput: string;
  choices: Array<{ id: string; text: string }>;
  judgeOutput: JudgeOutput;
}

export interface GameState {
  sessionId: string;
  metrics: Metrics;
  dreamLayer: DreamLayer;
  currentStep: Step | null;
  stepHistory: string[];
  storyHistory: StoryEntry[];
  isAwake: boolean;
  wakeCause: WakeCause | null;
  initialThought: string | null;
  conversationHistory: ConversationMessage[];
  lastStepData: LastStepData | null;
}

export interface StartSessionRequest {
  initialThought?: string;
}

export interface StartSessionResponse {
  sessionId: string;
  initialState: GameState;
}

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
  guidance: string;
}
