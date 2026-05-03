import { Router, type Router as ExpressRouter } from "express";
import { randomUUID } from "crypto";
import type { GameState, StartSessionRequest } from "../../../shared/types.js";
import { getSession, setSession, deleteSession } from "../session-store.js";
import { getDerivedMetrics, applyDecision, advanceStep } from "../logic.js";
import { generateStep } from "../services/text.js";
import { updateAudioPrompt } from "../services/audio.js";

const SESSION_ID_REGEX = /^[a-zA-Z0-9_-]{8,64}$/;

function refreshAudio(sessionId: string, state: GameState, storyContext?: string): void {
  const loc = state.dreamLayer.locations[state.dreamLayer.currentLocationIndex];
  if (!loc) return;
  updateAudioPrompt(
    sessionId,
    loc.audioStyle,
    state.metrics.arousal,
    state.metrics.valence,
    state.metrics.selfAwareness,
    storyContext,
  ).catch((e) => console.error("Failed to update audio prompt:", e));
}

const router: ExpressRouter = Router();

router.post("/", (req, res) => {
  const body = req.body as StartSessionRequest;
  const sessionId = randomUUID();
  const state: GameState = {
    sessionId,
    metrics: { arousal: 0, valence: 0, selfAwareness: 0 },
    dreamLayer: {
      stepCount: 0,
      maxSteps: 87,
      locations: [],
      currentLocationIndex: -1,
      world: "",
      writingStyle: "",
      visualStyle: "",
      audioStyle: "",
    },
    currentStep: null,
    stepHistory: [],
    storyHistory: [],
    isAwake: false,
    wakeCause: null,
    initialThought: body.initialThought ?? null,
    conversationHistory: [],
    lastStepData: null,
  };
  setSession(sessionId, state);
  res.json({ sessionId, initialState: state });
});

router.get("/:id", (req, res) => {
  const id = req.params.id;
  if (!SESSION_ID_REGEX.test(id)) return void res.status(400).json({ error: "Invalid session ID format" });
  const state = getSession(id);
  if (!state) return void res.status(404).json({ error: "Session not found" });
  res.json(state);
});

router.delete("/:id", (req, res) => {
  const id = req.params.id;
  if (!SESSION_ID_REGEX.test(id)) return void res.status(400).json({ error: "Invalid session ID format" });
  if (!deleteSession(id)) return void res.status(404).json({ error: "Session not found" });
  res.json({ success: true });
});

router.post("/:id/generate", async (req, res) => {
  const id = req.params.id;
  if (!SESSION_ID_REGEX.test(id)) return void res.status(400).json({ error: "Invalid session ID format" });
  const state = getSession(id);
  if (!state) return void res.status(404).json({ error: "Session not found" });
  if (state.isAwake) return void res.status(400).json({ error: "Session ended (woke)" });

  try {
    const step = await generateStep(state, req.body?.imaginedElement as string | undefined);
    setSession(id, state);
    refreshAudio(id, state, step.context);
    res.json({ step, state });
  } catch (e) {
    res.status(500).json({ error: e instanceof Error ? e.message : "Unknown error" });
  }
});

router.post("/:id/decide", (req, res) => {
  const id = req.params.id;
  if (!SESSION_ID_REGEX.test(id)) return void res.status(400).json({ error: "Invalid session ID format" });
  const { decisionId } = req.body;
  if (typeof decisionId !== "string") return void res.status(400).json({ error: "decisionId required" });

  const state = getSession(id);
  if (!state) return void res.status(404).json({ error: "Session not found" });
  if (state.isAwake) return void res.status(400).json({ error: "Session already ended (player woke)" });
  if (!state.currentStep) return void res.status(400).json({ error: "No current step - call /generate first" });

  const result = applyDecision(state, decisionId);
  if (!result) return void res.status(400).json({ error: "Invalid decision ID" });

  const chosen = state.currentStep.decisions.find((d) => d.id === decisionId);
  if (chosen) state.storyHistory.push({ context: state.currentStep.context, chosenAction: chosen.text });

  advanceStep(state);
  setSession(id, state);

  res.json({
    appliedEffects: result.appliedEffects,
    woke: result.woke,
    wakeCause: result.wakeCause,
    state,
  });
});

router.get("/:id/derived", (req, res) => {
  const id = req.params.id;
  if (!SESSION_ID_REGEX.test(id)) return void res.status(400).json({ error: "Invalid session ID format" });
  const state = getSession(id);
  if (!state) return void res.status(404).json({ error: "Session not found" });
  res.json(getDerivedMetrics(state.metrics));
});

export default router;
