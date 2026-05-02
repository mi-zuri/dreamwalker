import { Router, type Router as ExpressRouter } from "express";
import { randomUUID } from "crypto";
import type { GameState, StartSessionRequest } from "../../../shared/types.js";
import { getSession, setSession, deleteSession } from "../sessions.js";
import { validateSessionId } from "../utils/validation.js";

const router: ExpressRouter = Router();

function createInitialState(
  sessionId: string,
  initialThought?: string,
): GameState {
  const now = Date.now();
  return {
    sessionId,
    masterSeed: now.toString(),
    metrics: { arousal: 0, valence: 0, selfAwareness: 0 },
    dreamLayer: {
      stepCount: 0,
      maxSteps: 87,
      locations: [],
      currentLocationIndex: -1,
      poi: null,
      world: "",
      writingStyle: "",
      visualStyle: "",
      audioStyle: "",
    },
    currentStep: null,
    stepHistory: [],
    storyHistory: [],
    locationHistory: { locationIds: [] },
    stabilityTracker: { consecutiveStable: 0 },
    inventory: null,
    isAwake: false,
    wakeCause: null,
    initialThought: initialThought ?? null,
    conversationHistory: [],
    lastStepData: null,
  };
}

// POST /api/session - Create new session
router.post("/", (req, res) => {
  const body = req.body as StartSessionRequest;
  const sessionId = randomUUID();
  const state = createInitialState(sessionId, body.initialThought);
  setSession(sessionId, state);
  res.json({ sessionId, initialState: state });
});

// GET /api/session/:id - Get session
router.get("/:id", validateSessionId, (req, res) => {
  const sessionId = req.params.id as string;
  const state = getSession(sessionId);
  if (!state) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  res.json(state);
});

// DELETE /api/session/:id - End session
router.delete("/:id", validateSessionId, (req, res) => {
  const sessionId = req.params.id as string;
  const deleted = deleteSession(sessionId);
  if (!deleted) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  res.json({ success: true });
});

export default router;
