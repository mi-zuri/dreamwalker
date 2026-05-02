import { Router, type Router as ExpressRouter } from "express";
import { validateSessionId } from "../utils/validation.js";
import { getSession, setSession } from "../sessions.js";
import { getDerivedMetrics } from "../game/metrics.js";
import { applyDecision, advanceStep } from "../game/state.js";
import { generateStep } from "../services/text.js";
import { updateAudioPrompt } from "../services/audio.js";

const router: ExpressRouter = Router();

// POST /api/session/:id/generate - Generate next story step
router.post("/:id/generate", validateSessionId, async (req, res) => {
  const sessionId = req.params.id as string;
  const state = getSession(sessionId);

  if (!state) {
    res.status(404).json({ error: "Session not found" });
    return;
  }

  if (state.isAwake) {
    res.status(400).json({ error: "Session ended (woke)" });
    return;
  }

  try {
    const imaginedElement = req.body?.imaginedElement as string | undefined;
    const step = await generateStep(state, imaginedElement);
    setSession(sessionId, state);

    // Update audio prompt to match the new scene
    const currentLocation =
      state.dreamLayer.locations[state.dreamLayer.currentLocationIndex];
    if (currentLocation && step) {
      updateAudioPrompt(
        sessionId,
        currentLocation.audioStyle,
        state.metrics.arousal,
        state.metrics.valence,
        state.metrics.selfAwareness,
        step.context,
      ).catch((error) => {
        console.error("Failed to update audio prompt:", error);
      });
    }

    res.json({ step, state });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    res.status(500).json({ error: message });
  }
});

// POST /api/session/:id/decide - Execute player decision
router.post("/:id/decide", validateSessionId, async (req, res) => {
  const { decisionId } = req.body;
  if (!decisionId || typeof decisionId !== "string") {
    res.status(400).json({ error: "decisionId required" });
    return;
  }

  const sessionId = req.params.id as string;
  const state = getSession(sessionId);

  if (!state) {
    res.status(404).json({ error: "Session not found" });
    return;
  }

  if (state.isAwake) {
    res.status(400).json({ error: "Session already ended (player woke)" });
    return;
  }

  if (!state.currentStep) {
    res.status(400).json({ error: "No current step - call /generate first" });
    return;
  }

  const result = applyDecision(state, decisionId);
  if (!result) {
    res.status(400).json({ error: "Invalid decision ID" });
    return;
  }

  // Add to story history
  const chosenDecision = state.currentStep.decisions.find(
    (d) => d.id === decisionId,
  );
  if (chosenDecision) {
    state.storyHistory.push({
      context: state.currentStep.context,
      chosenAction: chosenDecision.text,
      outcome: result.success ? "success" : "failure",
    });
  }

  advanceStep(state);
  setSession(sessionId, state);

  // Update audio prompt to reflect new metrics
  const currentLocation =
    state.dreamLayer.locations[state.dreamLayer.currentLocationIndex];
  if (currentLocation) {
    updateAudioPrompt(
      sessionId,
      currentLocation.audioStyle,
      state.metrics.arousal,
      state.metrics.valence,
      state.metrics.selfAwareness,
    ).catch((error) => {
      console.error("Failed to update audio prompt:", error);
    });
  }

  res.json({
    success: result.success,
    appliedEffects: result.appliedEffects,
    woke: result.woke,
    wakeCause: result.wakeCause,
    state,
  });
});

// GET /api/session/:id/derived - Get derived metrics
router.get("/:id/derived", validateSessionId, (req, res) => {
  const sessionId = req.params.id as string;
  const state = getSession(sessionId);
  if (!state) {
    res.status(404).json({ error: "Session not found" });
    return;
  }

  const derived = getDerivedMetrics(state.metrics);
  res.json(derived);
});

export default router;
