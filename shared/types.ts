// Psychological Metrics (-100 to +100, stable zone: -50 to +50)
export interface Metrics {
  action: number;      // External intensity
  emotion: number;     // Internal intensity
  selfConsciousness: number; // Awareness of dreaming
}

// Derived values
export interface DerivedMetrics {
  luck: number;        // Influences attempt success
  turbulence: number;  // Dream instability (|action| + |emotion|)
}

// Tension levels affect luck calculation
export type TensionLevel = 'low' | 'medium' | 'high';

// Atmosphere affects dream generation
export type Atmosphere = 'calm' | 'neutral' | 'difficult';

// POI types
export type POIType = 'reach' | 'understand' | 'deliver' | 'escape' | 'witness';

export interface POI {
  type: POIType;
  description: string;
  fulfilled: boolean;
}

// Decision in a step
export interface Decision {
  id: string;
  text: string;
  effects: {
    action: number;    // Direction shown, magnitude hidden
    emotion: number;
    selfConsciousness: number;
  };
  leadsToNode: string | null; // null = same node
}

// Attempt (uncertain action)
export interface Attempt {
  id: string;
  text: string;
  successEffects: { action: number; emotion: number };
  failureEffects: { action: number; emotion: number };
}

// Location in dream
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
  context: string;           // 1-sentence situation
  decisions: Decision[];     // 1-4 choices
  attempts?: Attempt[];      // Optional uncertain actions
  locationId: string;
  poiVisible: boolean;
  isTimed: boolean;
  timedDeadline?: number;    // 10 seconds
}

// Extreme step counters for wake detection
export interface ExtremeSteps {
  action: number;
  emotion: number;
  turbulence: number;
}

// Wake cause tags
export type WakeCause =
  | 'emotional_overload'
  | 'action_overload'
  | 'lucidity_break'
  | 'dissolution'
  | 'terror_spiral'
  | 'stagnation'
  | 'turbulence_critical';

// Dream layer state
export interface DreamLayer {
  depth: number;
  stepCount: number;
  maxSteps: number;          // 87
  locations: Location[];
  currentLocationIndex: number;
  poi: POI;
  atmosphere: Atmosphere;
  tension: TensionLevel;
  writingStyle: string;
  visualStyle: string;
  audioStyle: string;
}

// Session state
export interface GameState {
  sessionId: string;
  masterSeed: string;
  metrics: Metrics;
  extremeSteps: ExtremeSteps;
  dreamLayer: DreamLayer;
  currentStep: Step | null;
  stepHistory: string[];     // Step IDs
  inventory: string | null;  // Single symbolic item
  isAwake: boolean;
  wakeCause: WakeCause | null;
}

// API request/response types
export interface StartSessionRequest {
  stylePreferences?: string;
}

export interface StartSessionResponse {
  sessionId: string;
  initialState: GameState;
}

export interface MakeDecisionRequest {
  sessionId: string;
  decisionId: string;
}

export interface MakeAttemptRequest {
  sessionId: string;
  attemptId: string;
}

export interface StepResponse {
  state: GameState;
  step: Step;
  outcome?: {
    text: string;
    metricsChanged: Partial<Metrics>;
  };
}
