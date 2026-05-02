import { GoogleGenAI, Type } from '@google/genai';
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

interface Choice { id: string; text: string }

// ── Schemas ─────────────────────────────────────────────────────────

const STR = { type: Type.STRING };
const INT = { type: Type.INTEGER };
const BOOL = { type: Type.BOOLEAN };
const METRICS_SCHEMA = {
  type: Type.OBJECT,
  properties: { arousal: INT, valence: INT, selfAwareness: INT },
  required: ['arousal', 'valence', 'selfAwareness'],
};

const INITIATOR_SCHEMA = {
  type: Type.OBJECT,
  properties: { world: STR, writingStyle: STR, visualStyle: STR, audioStyle: STR },
  required: ['world', 'writingStyle', 'visualStyle', 'audioStyle'],
};

const STORYTELLER_SCHEMA = {
  type: Type.OBJECT,
  properties: { text: STR },
  required: ['text'],
};

const BRANCHER_SCHEMA = {
  type: Type.OBJECT,
  properties: {
    choices: {
      type: Type.ARRAY,
      items: { type: Type.OBJECT, properties: { id: STR, text: STR }, required: ['id', 'text'] },
    },
  },
  required: ['choices'],
};

const JUDGE_SCHEMA = {
  type: Type.OBJECT,
  properties: { event: METRICS_SCHEMA, choices: { type: Type.ARRAY, items: METRICS_SCHEMA } },
  required: ['event', 'choices'],
};

const DIRECTOR_SCHEMA = {
  type: Type.OBJECT,
  properties: { locationChange: BOOL, guidance: STR },
  required: ['locationChange', 'guidance'],
};

// ── Helpers ─────────────────────────────────────────────────────────

function recentSummary(state: GameState): string {
  const recent = state.storyHistory.slice(-3);
  if (recent.length === 0) return 'No story yet.';
  return recent
    .map((e, i) => `[${state.storyHistory.length - recent.length + i + 1}] ${e.context} → "${e.chosenAction}"`)
    .join('\n');
}

async function callGemini<T>(
  prompt: string,
  schema: object,
  chat?: { systemPrompt: string; history: ConversationMessage[] },
): Promise<{ result: T; rawText: string }> {
  const contents = chat
    ? [
        ...chat.history.map((m) => ({
          role: m.role === 'assistant' ? ('model' as const) : ('user' as const),
          parts: [{ text: m.content }],
        })),
        { role: 'user' as const, parts: [{ text: prompt }] },
      ]
    : prompt;
  const response = await ai.models.generateContent({
    model: MODEL,
    contents,
    config: {
      responseMimeType: 'application/json',
      responseSchema: schema,
      ...(chat ? { systemInstruction: chat.systemPrompt } : {}),
    },
  });
  const rawText = response.text ?? '';
  return { result: JSON.parse(rawText) as T, rawText };
}

// ── Agents ──────────────────────────────────────────────────────────

async function runInitiator(userThought: string): Promise<InitiatorOutput> {
  const prompt = `Create a dream world from this thought. Every field must reflect it.
THOUGHT: "${userThought}"
Fields: world (~100 words: rules, atmosphere, physics), writingStyle, visualStyle, audioStyle.`;
  const { result } = await callGemini<InitiatorOutput>(prompt, INITIATOR_SCHEMA);
  return result;
}

async function runStoryteller(
  state: GameState,
  directorGuidance?: string,
  imaginedElement?: string,
): Promise<{ storyText: string; updatedHistory: ConversationMessage[] }> {
  const systemPrompt = `Dream narrator. Continue the story in 2-4 sentences. Concrete details, no "dreamlike" labels. React to the player's last choice.
World: ${state.dreamLayer.world}
Style: ${state.dreamLayer.writingStyle}${directorGuidance ? `\nDirector: ${directorGuidance}` : ''}`;

  const trimmedHistory = state.conversationHistory.slice(-MAX_HISTORY_MESSAGES);
  let userPrompt = trimmedHistory.length === 0 ? 'Begin the dream.' : 'Continue.';
  if (imaginedElement) userPrompt += `\nThe player imagines: "${imaginedElement}"`;

  const { result, rawText } = await callGemini<{ text: string }>(
    userPrompt, STORYTELLER_SCHEMA, { systemPrompt, history: trimmedHistory },
  );

  const updatedHistory: ConversationMessage[] = [
    ...trimmedHistory,
    { role: 'user', content: userPrompt },
    { role: 'assistant', content: rawText },
  ];
  return { storyText: result.text, updatedHistory };
}

async function runBrancher(state: GameState, lastStoryText: string): Promise<Choice[]> {
  const prompt = `Generate 1-4 distinct player choices (3-8 words each, actionable) for this scene.
Recent:
${recentSummary(state)}
Scene: ${lastStoryText}`;
  const { result } = await callGemini<{ choices: Choice[] }>(prompt, BRANCHER_SCHEMA);
  return result.choices;
}

async function runJudge(storyText: string, choices: Choice[]): Promise<JudgeOutput> {
  const choicesText = choices.map((c, i) => `${i + 1}. ${c.text}`).join('\n');
  const prompt = `Rate the event and each choice on three axes, integers in [-25, +25]:
  arousal: calm(-) ↔ intense(+)
  valence: dark(-) ↔ bright(+)
  selfAwareness: immersed(-) ↔ lucid(+)
EVENT: ${storyText}
CHOICES:
${choicesText}
Return one entry in choices[] per choice (${choices.length} total).`;
  const { result } = await callGemini<JudgeOutput>(prompt, JUDGE_SCHEMA);
  return result;
}

async function runDirector(
  state: GameState,
  storytellerOutput: string,
  choices: Choice[],
  judgeOutput: JudgeOutput,
  userChoice: Choice,
): Promise<DirectorOutput> {
  const choicesWithMetrics = choices
    .map((c, i) => `${i + 1}. "${c.text}" → a:${judgeOutput.choices[i]?.arousal ?? 0} v:${judgeOutput.choices[i]?.valence ?? 0} s:${judgeOutput.choices[i]?.selfAwareness ?? 0}`)
    .join('\n');
  const prompt = `Pace the dream. Decide structural flags + guide the next scene.
Step ${state.dreamLayer.stepCount}/${state.dreamLayer.maxSteps} | metrics a=${state.metrics.arousal} v=${state.metrics.valence} s=${state.metrics.selfAwareness}
Recent:
${recentSummary(state)}
Last event: ${storytellerOutput} (a:${judgeOutput.event.arousal} v:${judgeOutput.event.valence} s:${judgeOutput.event.selfAwareness})
Choices:
${choicesWithMetrics}
User chose: "${userChoice.text}"`;
  const { result } = await callGemini<DirectorOutput>(prompt, DIRECTOR_SCHEMA);
  return result;
}

// ── Main orchestrator ────────────────────────────────────────────────

export async function generateStep(state: GameState, imaginedElement?: string): Promise<Step> {
  // Step 1: Run Initiator on first step
  if (!state.dreamLayer.world) {
    const init = await runInitiator(state.initialThought || 'a dream');
    state.dreamLayer.world = init.world;
    state.dreamLayer.writingStyle = init.writingStyle;
    state.dreamLayer.visualStyle = init.visualStyle;
    state.dreamLayer.audioStyle = init.audioStyle;
    state.dreamLayer.locations = [{
      id: 'loc-0',
      name: 'Dream Space',
      description: init.world,
      visualStyle: init.visualStyle,
      audioStyle: init.audioStyle,
    }];
    state.dreamLayer.currentLocationIndex = 0;
  }

  // Step 2: Director guidance (step 2+)
  let directorGuidance: string | undefined;
  if (state.dreamLayer.stepCount > 0 && state.lastStepData && state.storyHistory.length > 0) {
    const lastEntry = state.storyHistory[state.storyHistory.length - 1];
    const directorOutput = await runDirector(
      state,
      state.lastStepData.storytellerOutput,
      state.lastStepData.choices,
      state.lastStepData.judgeOutput,
      { id: 'last', text: lastEntry.chosenAction },
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
      currentLocation.imageUrl = await generateSceneImage(
        state.dreamLayer.visualStyle,
        currentLocation.description,
        storyText,
      );
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
      effects: judgeOutput.choices[index],
    })),
    locationId: currentLocation?.id || '',
  };

  state.currentStep = step;
  state.stepHistory.push(step.id);
  state.lastStepData = { storytellerOutput: storyText, choices, judgeOutput };

  return step;
}
