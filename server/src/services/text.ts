import { GoogleGenAI } from '@google/genai';
import type {
  GameState,
  ConversationMessage,
  InitiatorOutput,
  JudgeOutput,
  DirectorOutput,
  Step,
} from '../../../shared/types.js';
import { generateSceneImage } from './image.js';

const ai = new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY! });
const MODEL = 'gemini-3.1-flash-lite-preview';
const MAX_HISTORY_MESSAGES = 30;

// ── Helpers ──────────────────────────────────────────────────────────

function generateRandomSeed(length = 50): string {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * chars.length)];
  }
  return result;
}

const EXAMPLE_STYLES: InitiatorOutput[] = [
  { world: 'realistic modern city', writingStyle: 'drama', visualStyle: 'photorealistic', audioStyle: 'urban ambient' },
  { world: 'black and white detective story', writingStyle: 'noir', visualStyle: 'noir film grain', audioStyle: 'jazz' },
  { world: 'surreal melting landscape', writingStyle: 'abstract poetry', visualStyle: 'abstract expressionism', audioStyle: 'experimental electronic' },
  { world: 'cartoon kingdom', writingStyle: 'comedy', visualStyle: 'animation', audioStyle: 'cartoon sound effects' },
  { world: 'pixelated dungeon', writingStyle: 'retro game text', visualStyle: '8-bit pixel art', audioStyle: 'chiptune' },
  { world: 'terminal simulation', writingStyle: 'computer code and logs', visualStyle: 'green-on-black terminal', audioStyle: 'dial-up modem, keystrokes' },
  { world: 'space opera galaxy', writingStyle: 'sci-fi epic', visualStyle: 'cinematic sci-fi', audioStyle: 'orchestral synth' },
  { world: 'magical academy', writingStyle: 'anime narration', visualStyle: 'anime cel-shaded', audioStyle: 'j-pop inspired' },
  { world: 'enchanted meadow', writingStyle: 'children\'s book', visualStyle: 'watercolor illustration', audioStyle: 'lullaby, gentle chimes' },
  { world: 'heartbreak hotel', writingStyle: 'love letter', visualStyle: 'soft focus romance', audioStyle: 'piano ballad' },
  { world: 'haunted asylum', writingStyle: 'horror', visualStyle: 'dark desaturated found-footage', audioStyle: 'dread drones, silence' },
  { world: 'rhyming countryside', writingStyle: 'poem in verse', visualStyle: 'impressionist painting', audioStyle: 'acoustic folk' },
  { world: 'concert stage', writingStyle: 'song lyrics with stage directions', visualStyle: 'neon concert lighting', audioStyle: 'live rock' },
  { world: 'old west frontier', writingStyle: 'western drawl', visualStyle: 'dusty sepia tones', audioStyle: 'harmonica, spurs' },
  { world: 'ancient mythology', writingStyle: 'epic myth', visualStyle: 'classical oil painting', audioStyle: 'choral, ancient instruments' },
];

function pickRandomExamples(): { examples: InitiatorOutput[]; note: string } {
  const count = Math.floor(Math.random() * 6); // 0–5
  if (count === 0) return { examples: [], note: '' };
  const shuffled = [...EXAMPLE_STYLES].sort(() => Math.random() - 0.5);
  return {
    examples: shuffled.slice(0, count),
    note: 'NOTE: Do NOT choose from the examples above. They are only shown for structural reference. The user\'s prompt is the primary input — build the dream world around it.',
  };
}

function trimConversationHistory(history: ConversationMessage[]): ConversationMessage[] {
  if (history.length <= MAX_HISTORY_MESSAGES) return history;
  return history.slice(-MAX_HISTORY_MESSAGES);
}

function createStorySummary(state: GameState): string {
  const entries = state.storyHistory;
  if (entries.length === 0) return 'No story yet.';

  let summary = 'STORY SUMMARY:\n';
  const recentCount = 3;
  const olderEntries = entries.slice(0, -recentCount);

  if (olderEntries.length > 0) {
    const chunkSize = 5;
    for (let i = 0; i < olderEntries.length; i += chunkSize) {
      const chunk = olderEntries.slice(i, i + chunkSize);
      const contexts = chunk.map((e) => e.context).join(' ');
      summary += `[Steps ${i + 1}-${i + chunk.length}]: ${contexts.slice(0, 200)}...\n`;
    }
  }

  const recentEntries = entries.slice(-recentCount);
  recentEntries.forEach((entry, index) => {
    const stepNum = entries.length - recentCount + index + 1;
    summary += `[Recent - Step ${stepNum}]: ${entry.context}\n`;
    if (entry.chosenAction) summary += `  → Player: ${entry.chosenAction}\n`;
    if (entry.outcome) summary += `  → Outcome: ${entry.outcome}\n`;
  });

  return summary;
}

function createDecisionsHistory(state: GameState): string {
  if (state.storyHistory.length === 0) return 'No decisions yet.';
  const decisions = state.storyHistory
    .map((entry, index) => `Step ${index + 1}: "${entry.chosenAction}"`)
    .join(' → ');
  return `ALL DECISIONS TAKEN:\n${decisions}`;
}

// ── Logging ──────────────────────────────────────────────────────────

function logAgentCall(agentName: string, prompt: string, historyLength?: number) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`🔵 ${agentName} | ${new Date().toISOString()}`);
  if (historyLength !== undefined) console.log(`📚 History: ${historyLength} msgs`);
  console.log(`--- PROMPT ---\n${prompt.slice(0, 500)}${prompt.length > 500 ? '...' : ''}`);
  console.log('='.repeat(60));
}

function logAgentResponse(agentName: string, rawText: string) {
  console.log(`🟢 ${agentName} response: ${rawText.slice(0, 300)}${rawText.length > 300 ? '...' : ''}`);
}

// ── Validators ───────────────────────────────────────────────────────

function validateInitiatorOutput(output: any): asserts output is InitiatorOutput {
  if (!output.world || typeof output.world !== 'string') throw new Error('Initiator: missing "world"');
  if (!output.writingStyle || typeof output.writingStyle !== 'string') throw new Error('Initiator: missing "writingStyle"');
  if (!output.visualStyle || typeof output.visualStyle !== 'string') throw new Error('Initiator: missing "visualStyle"');
  if (!output.audioStyle || typeof output.audioStyle !== 'string') throw new Error('Initiator: missing "audioStyle"');
}

function validateJudgeOutput(output: any, choiceCount: number): asserts output is JudgeOutput {
  if (!output.event || typeof output.event !== 'object') throw new Error('Judge: missing "event"');
  for (const k of ['arousal', 'valence', 'selfAwareness'] as const) {
    if (typeof output.event[k] !== 'number') throw new Error(`Judge: event.${k} not a number`);
  }
  if (!Array.isArray(output.choices)) throw new Error('Judge: missing "choices" array');
  // Pad or truncate to match choice count
  while (output.choices.length < choiceCount) {
    output.choices.push({ arousal: 0, valence: 0, selfAwareness: 0 });
  }
  output.choices = output.choices.slice(0, choiceCount);
}

function validateDirectorOutput(output: any): asserts output is DirectorOutput {
  if (typeof output.locationChange !== 'boolean') output.locationChange = false;
  if (typeof output.poi !== 'boolean') output.poi = false;
  if (typeof output.timedEvent !== 'boolean') output.timedEvent = false;
  if (!output.guidance || typeof output.guidance !== 'string') throw new Error('Director: missing "guidance"');
}

// ── Gemini callers ───────────────────────────────────────────────────

async function callGemini<T>(prompt: string, agentName: string): Promise<T> {
  logAgentCall(agentName, prompt);
  const response = await ai.models.generateContent({
    model: MODEL,
    contents: prompt,
    config: { responseMimeType: 'application/json' },
  });
  const text = response.text ?? '';
  logAgentResponse(agentName, text);
  return JSON.parse(text) as T;
}

async function callGeminiChat(
  systemPrompt: string,
  history: ConversationMessage[],
  userMessage: string,
  agentName: string,
): Promise<{ result: any; rawText: string }> {
  logAgentCall(agentName, `[system] ${systemPrompt.slice(0, 200)}... [user] ${userMessage}`, history.length);

  const contents = [
    ...history.map((m) => ({
      role: m.role === 'assistant' ? 'model' as const : 'user' as const,
      parts: [{ text: m.content }],
    })),
    { role: 'user' as const, parts: [{ text: userMessage }] },
  ];

  const response = await ai.models.generateContent({
    model: MODEL,
    contents,
    config: {
      responseMimeType: 'application/json',
      systemInstruction: systemPrompt,
    },
  });
  const text = response.text ?? '';
  logAgentResponse(agentName, text);
  return { result: JSON.parse(text), rawText: text };
}

// ── Retry wrapper ────────────────────────────────────────────────────

async function withRetry<T>(fn: () => Promise<T>, label: string): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    console.warn(`⚠️  ${label} FAILED - retrying once. Error: ${error instanceof Error ? error.message : 'Unknown'}`);
    return await fn();
  }
}

// ── Agent 1: Initiator ──────────────────────────────────────────────

async function runInitiator(userThought: string): Promise<InitiatorOutput> {
  const { examples, note } = pickRandomExamples();

  let examplesBlock = '';
  if (examples.length > 0) {
    examplesBlock = `\n--- STYLE EXAMPLES (structural reference only) ---\n${examples
      .map((ex, i) => `Example ${i + 1}:\n  world: "${ex.world}"\n  writingStyle: "${ex.writingStyle}"\n  visualStyle: "${ex.visualStyle}"\n  audioStyle: "${ex.audioStyle}"`)
      .join('\n\n')}\n\n${note}\n---\n`;
  }

  const prompt = `You imagine dream worlds. Create a surreal but coherent dream setting based on the user's thought.
The world should be simple and clear — dreams are often realistic before becoming strange.

IMPORTANT: The user's prompt is the SOLE basis for your dream world. Every field in your output MUST directly reflect the prompt's theme, setting, and mood. Do not invent unrelated worlds.

Output JSON:
{
  "world": "~100 word description of world rules, atmosphere, physics — derived from the prompt",
  "writingStyle": "narrative voice that fits the prompt",
  "visualStyle": "image aesthetic that fits the prompt",
  "audioStyle": "sound design that fits the prompt"
}
${examplesBlock}
USER THOUGHT: "${userThought}"

Create a dream world that is DIRECTLY about the above thought. All fields must reflect this thought.`;

  const output = await callGemini<any>(prompt, 'Initiator');
  validateInitiatorOutput(output);
  return output;
}

// ── Agent 2: Storyteller ────────────────────────────────────────────

interface Choice { id: string; text: string }

async function runStoryteller(
  state: GameState,
  directorGuidance?: string,
  imaginedElement?: string,
): Promise<{ storyText: string; updatedHistory: ConversationMessage[] }> {
  const systemPrompt = `You are a dream narrator. Write 2-4 sentence story continuations.

Rules:
- React to player choices (show consequences)
- Reference POI (current objective) when relevant
- Use concrete details, avoid "dreamlike" labels
- Maintain continuity with conversation history

World Rules: ${state.dreamLayer.world}
Writing Style: ${state.dreamLayer.writingStyle}
${state.dreamLayer.poi ? `Current POI: ${state.dreamLayer.poi.description}` : ''}
${directorGuidance ? `\nDirector Guidance: ${directorGuidance}` : ''}

Output JSON: { "text": "2-4 sentence narrative" }`;

  const trimmedHistory = trimConversationHistory(state.conversationHistory);

  let userPrompt = trimmedHistory.length === 0
    ? 'Begin the dream story.'
    : 'Continue the story based on the latest events.';

  if (imaginedElement) {
    userPrompt += `\n\nThe player imagines: "${imaginedElement}"`;
  }

  const { result, rawText } = await callGeminiChat(systemPrompt, trimmedHistory, userPrompt, 'Storyteller');

  if (!result.text || typeof result.text !== 'string') {
    throw new Error('Storyteller: missing "text" field');
  }

  const updatedHistory: ConversationMessage[] = [
    ...trimmedHistory,
    { role: 'user', content: userPrompt },
    { role: 'assistant', content: rawText },
  ];

  return { storyText: result.text, updatedHistory };
}

// ── Agent 3: Brancher ───────────────────────────────────────────────

async function runBrancher(state: GameState, lastStoryText: string): Promise<Choice[]> {
  const prompt = `Generate 1-4 meaningful choices based on story context.
Each choice: 3-8 words, actionable, distinct from each other.

${createStorySummary(state)}

${createDecisionsHistory(state)}

LAST STORY EVENT:
${lastStoryText}

Output JSON:
{
  "choices": [
    {"id": "c1", "text": "..."},
    {"id": "c2", "text": "..."}
  ]
}

Generate 1-4 choices for the player.`;

  const parsed = await callGemini<{ choices: Choice[] }>(prompt, 'Brancher');

  if (!Array.isArray(parsed.choices) || parsed.choices.length === 0) {
    throw new Error('Brancher: empty choices array');
  }
  for (const c of parsed.choices) {
    if (!c.id || !c.text) throw new Error('Brancher: choice missing id or text');
  }

  return parsed.choices;
}

// ── Agent 4: Judge ──────────────────────────────────────────────────

async function runJudge(storyText: string, choices: Choice[]): Promise<JudgeOutput> {
  const choicesText = choices.map((c, i) => `${i + 1}. ${c.text}`).join('\n');

  const prompt = `Evaluate a story event and each player choice for psychological metric impact.
Output integer values from -25 to +25 for each metric.

Arousal: Physical/action intensity (negative = calm, positive = intense)
Valence: Emotional tone (negative = dark emotions, positive = bright emotions)
SelfAwareness: Dream lucidity (negative = immersed, positive = aware it's a dream)

STORY EVENT:
${storyText}

CHOICES:
${choicesText}

Output JSON:
{
  "event": {"arousal": 0, "valence": 0, "selfAwareness": 0},
  "choices": [
    {"arousal": 0, "valence": 0, "selfAwareness": 0}
  ]
}

Rate the story event and EACH choice (one entry per choice, ±5 to ±25).`;

  const parsed = await callGemini<any>(prompt, 'Judge');
  validateJudgeOutput(parsed, choices.length);
  return parsed;
}

// ── Agent 5: Director ───────────────────────────────────────────────

async function runDirector(
  state: GameState,
  storytellerOutput: string,
  choices: Choice[],
  judgeOutput: JudgeOutput,
  userChoice: Choice,
): Promise<DirectorOutput> {
  const choicesWithMetrics = choices
    .map((c, i) => `${i + 1}. "${c.text}" → arousal:${judgeOutput.choices[i]?.arousal ?? 0}, valence:${judgeOutput.choices[i]?.valence ?? 0}, selfAwareness:${judgeOutput.choices[i]?.selfAwareness ?? 0}`)
    .join('\n');

  const prompt = `Orchestrate narrative pacing for a dream game. Decide structural changes and guide the Storyteller for the next scene.

${createStorySummary(state)}

${createDecisionsHistory(state)}

LAST STORY EVENT:
${storytellerOutput}
Event metrics → arousal:${judgeOutput.event.arousal}, valence:${judgeOutput.event.valence}, selfAwareness:${judgeOutput.event.selfAwareness}

CHOICES:
${choicesWithMetrics}

USER CHOSE: "${userChoice.text}"

Current metrics: arousal=${state.metrics.arousal}, valence=${state.metrics.valence}, selfAwareness=${state.metrics.selfAwareness}
Step ${state.dreamLayer.stepCount}/${state.dreamLayer.maxSteps}

Output JSON:
{
  "locationChange": false,
  "poi": false,
  "timedEvent": false,
  "guidance": "Instructions for the Storyteller about what happens next"
}

Decide what happens next and guide the Storyteller.`;

  const parsed = await callGemini<any>(prompt, 'Director');
  validateDirectorOutput(parsed);
  return parsed;
}

// ── Main orchestrator ────────────────────────────────────────────────

export async function generateStep(state: GameState, imaginedElement?: string): Promise<Step> {
  return withRetry(async () => {
    // Step 1: Run Initiator on first step
    if (!state.dreamLayer.world) {
      const initiatorOutput = await runInitiator(state.initialThought || generateRandomSeed());
      state.dreamLayer.world = initiatorOutput.world;
      state.dreamLayer.writingStyle = initiatorOutput.writingStyle;
      state.dreamLayer.visualStyle = initiatorOutput.visualStyle;
      state.dreamLayer.audioStyle = initiatorOutput.audioStyle;

      state.dreamLayer.locations = [{
        id: 'loc-0',
        name: 'Dream Space',
        description: initiatorOutput.world,
        visualStyle: initiatorOutput.visualStyle,
        audioStyle: initiatorOutput.audioStyle,
        imageUrl: '',
      }];
      state.dreamLayer.currentLocationIndex = 0;
    }

    // Step 2: Director guidance (step 2+)
    let directorGuidance: string | undefined;
    if (state.dreamLayer.stepCount > 0 && state.lastStepData && state.storyHistory.length > 0) {
      const lastEntry = state.storyHistory[state.storyHistory.length - 1];
      const userChoice: Choice = { id: 'last', text: lastEntry.chosenAction };

      const directorOutput = await runDirector(
        state,
        state.lastStepData.storytellerOutput,
        state.lastStepData.choices,
        state.lastStepData.judgeOutput,
        userChoice,
      );
      directorGuidance = directorOutput.guidance;
    }

    // Step 3: Storyteller
    const { storyText, updatedHistory } = await runStoryteller(state, directorGuidance, imaginedElement);
    state.conversationHistory = updatedHistory;

    // Step 4: Brancher
    const choices = await runBrancher(state, storyText);

    // Step 5: Judge
    const judgeOutput = await runJudge(storyText, choices);

    // Step 6: Image generation (fire-and-forget on error)
    const currentLocation = state.dreamLayer.locations[state.dreamLayer.currentLocationIndex];
    if (currentLocation) {
      try {
        const imageUrl = await generateSceneImage({
          visualStyle: state.dreamLayer.visualStyle,
          locationDescription: currentLocation.description,
          storyContext: storyText,
        });
        currentLocation.imageUrl = imageUrl;
      } catch (error) {
        console.error('Image generation failed:', error);
      }
    }

    // Step 7: Build Step
    const step: Step = {
      id: `step-${state.dreamLayer.stepCount + 1}`,
      stepNumber: state.dreamLayer.stepCount + 1,
      context: storyText,
      decisions: choices.map((choice, index) => ({
        id: choice.id,
        text: choice.text,
        successEffects: judgeOutput.choices[index],
        failureEffects: {
          arousal: -judgeOutput.choices[index].arousal,
          valence: -judgeOutput.choices[index].valence,
          selfAwareness: -judgeOutput.choices[index].selfAwareness,
        },
        successChance: 100,
        leadsToNode: null,
      })),
      locationId: currentLocation?.id || '',
      poiVisible: state.dreamLayer.poi !== null,
      isTimed: false,
    };

    state.currentStep = step;
    state.stepHistory.push(step.id);
    state.lastStepData = { storytellerOutput: storyText, choices, judgeOutput };

    return step;
  }, 'generateStep');
}
