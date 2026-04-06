import Anthropic from "@anthropic-ai/sdk";
import type {
  GameState,
  ConversationMessage,
  InitiatorOutput,
  JudgeOutput,
  DirectorOutput,
  Step,
} from "../../../shared/types.js";
import { generateSceneImage } from "./image.js";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const MODEL = "claude-haiku-4-5";
const MAX_TOKENS = 1024;
const MAX_HISTORY_MESSAGES = 30;

// Random seed for when no user thought is provided
function generateRandomSeed(length = 50): string {
  const chars =
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * chars.length)];
  }
  return result;
}

// Example style sets — appended randomly to help guide (but not constrain) the model
const EXAMPLE_STYLES: InitiatorOutput[] = [
  {
    world: "realistic modern city",
    writingStyle: "drama",
    visualStyle: "photorealistic",
    audioStyle: "urban ambient",
  },
  {
    world: "black and white detective story",
    writingStyle: "noir",
    visualStyle: "noir film grain",
    audioStyle: "jazz",
  },
  {
    world: "surreal melting landscape",
    writingStyle: "abstract poetry",
    visualStyle: "abstract expressionism",
    audioStyle: "experimental electronic",
  },
  {
    world: "cartoon kingdom",
    writingStyle: "comedy",
    visualStyle: "animation",
    audioStyle: "cartoon sound effects",
  },
  {
    world: "pixelated dungeon",
    writingStyle: "retro game text",
    visualStyle: "8-bit pixel art",
    audioStyle: "chiptune",
  },
  {
    world: "terminal simulation",
    writingStyle: "computer code and logs",
    visualStyle: "green-on-black terminal",
    audioStyle: "dial-up modem, keystrokes",
  },
  {
    world: "space opera galaxy",
    writingStyle: "sci-fi epic",
    visualStyle: "cinematic sci-fi",
    audioStyle: "orchestral synth",
  },
  {
    world: "magical academy",
    writingStyle: "anime narration",
    visualStyle: "anime cel-shaded",
    audioStyle: "j-pop inspired",
  },
  {
    world: "enchanted meadow",
    writingStyle: "children's book",
    visualStyle: "watercolor illustration",
    audioStyle: "lullaby, gentle chimes",
  },
  {
    world: "heartbreak hotel",
    writingStyle: "love letter",
    visualStyle: "soft focus romance",
    audioStyle: "piano ballad",
  },
  {
    world: "haunted asylum",
    writingStyle: "horror",
    visualStyle: "dark desaturated found-footage",
    audioStyle: "dread drones, silence",
  },
  {
    world: "rhyming countryside",
    writingStyle: "poem in verse",
    visualStyle: "impressionist painting",
    audioStyle: "acoustic folk",
  },
  {
    world: "concert stage",
    writingStyle: "song lyrics with stage directions",
    visualStyle: "neon concert lighting",
    audioStyle: "live rock",
  },
  {
    world: "old west frontier",
    writingStyle: "western drawl",
    visualStyle: "dusty sepia tones",
    audioStyle: "harmonica, spurs",
  },
  {
    world: "ancient mythology",
    writingStyle: "epic myth",
    visualStyle: "classical oil painting",
    audioStyle: "choral, ancient instruments",
  },
];

function pickRandomExamples(): {
  examples: InitiatorOutput[];
  note: string;
} {
  const count = Math.floor(Math.random() * 6); // 0 to 5
  if (count === 0) {
    return { examples: [], note: "" };
  }
  const shuffled = [...EXAMPLE_STYLES].sort(() => Math.random() - 0.5);
  const examples = shuffled.slice(0, count);
  const note =
    "NOTE: Do NOT choose from the examples above. They are only shown for structural reference. The user's prompt is the primary input — build the dream world around it.";
  return { examples, note };
}

// Logging utilities
function logAgentCall(
  agentName: string,
  system: string,
  userPrompt: string,
  historyLength?: number,
) {
  console.log(`\n${"=".repeat(80)}`);
  console.log(`🔵 CONNECTING: ${agentName}`);
  console.log(`⏰ ${new Date().toISOString()}`);
  if (historyLength !== undefined) {
    console.log(`📚 History: ${historyLength} messages`);
  }
  console.log(`\n--- SYSTEM ---`);
  console.log(system);
  console.log(`\n--- USER ---`);
  console.log(userPrompt);
  console.log("=".repeat(80));
}

function logAgentResponse(agentName: string, rawText: string, parsed?: any) {
  console.log(`\n${"=".repeat(80)}`);
  console.log(`🟢 RESPONSE: ${agentName}`);
  console.log(`⏰ ${new Date().toISOString()}`);
  console.log(`\n--- RAW ---`);
  console.log(rawText);
  if (parsed) {
    console.log(`\n--- PARSED ---`);
    console.log(JSON.stringify(parsed, null, 2));
  }
  console.log("=".repeat(80) + "\n");
}

function logAgentDisconnect(agentName: string, conversationReset: boolean) {
  console.log(
    `🔴 DISCONNECT: ${agentName}${conversationReset ? " (RESET)" : " (MAINTAINING HISTORY)"}`,
  );
  console.log(`⏰ ${new Date().toISOString()}\n`);
}

// JSON parsing utilities
function cleanJsonString(text: string): string {
  // Remove comments (// and /* */)
  let cleaned = text.replace(/\/\/.*/g, "").replace(/\/\*[\s\S]*?\*\//g, "");

  // Remove trailing commas before } or ]
  cleaned = cleaned.replace(/,(\s*[}\]])/g, "$1");

  // Remove trailing comma at end
  cleaned = cleaned.replace(/,\s*$/, "");

  return cleaned.trim();
}

function extractJson(text: string): string {
  // Try to extract from markdown code block
  const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    return jsonMatch[1].trim();
  }

  // Try to find JSON object in text
  const objectMatch = text.match(/\{[\s\S]*\}/);
  if (objectMatch) {
    return objectMatch[0];
  }

  return text.trim();
}

function parseAgentResponse<T>(text: string, agentName: string): T {
  try {
    const jsonStr = extractJson(text);
    const cleaned = cleanJsonString(jsonStr);
    return JSON.parse(cleaned) as T;
  } catch (error) {
    throw new Error(
      `${agentName} failed to parse JSON: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  }
}

function validateInitiatorOutput(
  output: any,
): asserts output is InitiatorOutput {
  if (!output.world || typeof output.world !== "string") {
    throw new Error('Initiator output missing or invalid "world" field');
  }
  if (!output.writingStyle || typeof output.writingStyle !== "string") {
    throw new Error('Initiator output missing or invalid "writingStyle" field');
  }
  if (!output.visualStyle || typeof output.visualStyle !== "string") {
    throw new Error('Initiator output missing or invalid "visualStyle" field');
  }
  if (!output.audioStyle || typeof output.audioStyle !== "string") {
    throw new Error('Initiator output missing or invalid "audioStyle" field');
  }
}

function validateJudgeOutput(output: any): asserts output is JudgeOutput {
  if (!output.event || typeof output.event !== "object") {
    throw new Error('Judge output missing or invalid "event" field');
  }
  if (
    typeof output.event.arousal !== "number" ||
    typeof output.event.valence !== "number" ||
    typeof output.event.selfAwareness !== "number"
  ) {
    throw new Error('Judge output "event" missing required metric fields');
  }
  if (!Array.isArray(output.choices)) {
    throw new Error('Judge output missing or invalid "choices" array');
  }
  output.choices.forEach((choice: any, index: number) => {
    if (
      typeof choice.arousal !== "number" ||
      typeof choice.valence !== "number" ||
      typeof choice.selfAwareness !== "number"
    ) {
      throw new Error(
        `Judge output "choices[${index}]" missing required metric fields`,
      );
    }
  });
}

function validateDirectorOutput(output: any): asserts output is DirectorOutput {
  if (typeof output.locationChange !== "boolean") {
    throw new Error(
      'Director output missing or invalid "locationChange" field',
    );
  }
  if (typeof output.poi !== "boolean") {
    throw new Error('Director output missing or invalid "poi" field');
  }
  if (typeof output.timedEvent !== "boolean") {
    throw new Error('Director output missing or invalid "timedEvent" field');
  }
  if (!output.guidance || typeof output.guidance !== "string") {
    throw new Error('Director output missing or invalid "guidance" field');
  }
}

// Retry wrapper
async function withRetry<T>(
  fn: () => Promise<T>,
  agentName: string,
): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    console.warn(`\n⚠️  ${agentName} FAILED - RETRY 2/2`);
    console.warn(
      `Error: ${error instanceof Error ? error.message : "Unknown"}\n`,
    );
    return await fn();
  }
}

// Conversation history trimming
function trimConversationHistory(
  history: ConversationMessage[],
): ConversationMessage[] {
  if (history.length <= MAX_HISTORY_MESSAGES) {
    return history;
  }
  return history.slice(-MAX_HISTORY_MESSAGES);
}

// Story summarization
function createStorySummary(state: GameState): string {
  const entries = state.storyHistory;
  if (entries.length === 0) {
    return "No story yet.";
  }

  let summary = "STORY SUMMARY:\n";

  // Condense older entries (1-2 sentences per 5 steps)
  const recentCount = 3;
  const olderEntries = entries.slice(0, -recentCount);
  if (olderEntries.length > 0) {
    const chunkSize = 5;
    for (let i = 0; i < olderEntries.length; i += chunkSize) {
      const chunk = olderEntries.slice(i, i + chunkSize);
      const contexts = chunk.map((e) => e.context).join(" ");
      const stepRange = `[Steps ${i + 1}-${i + chunk.length}]`;
      summary += `${stepRange}: ${contexts.slice(0, 200)}...\n`;
    }
  }

  // Keep last 3 entries full
  const recentEntries = entries.slice(-recentCount);
  recentEntries.forEach((entry, index) => {
    const stepNum = entries.length - recentCount + index + 1;
    summary += `[Recent - Step ${stepNum}]: ${entry.context}\n`;
    if (entry.chosenAction) {
      summary += `  → Player: ${entry.chosenAction}\n`;
    }
    if (entry.outcome) {
      summary += `  → Outcome: ${entry.outcome}\n`;
    }
  });

  return summary;
}

function createDecisionsHistory(state: GameState): string {
  if (state.storyHistory.length === 0) {
    return "No decisions yet.";
  }

  const decisions = state.storyHistory
    .map((entry, index) => `Step ${index + 1}: "${entry.chosenAction}"`)
    .join(" → ");

  return `ALL DECISIONS TAKEN:\n${decisions}`;
}

// Agent 1: Initiator (runs once)
async function runInitiator(userPromptText: string): Promise<InitiatorOutput> {
  const systemPrompt = `Hi how are you?`;
  // You imagine simple and realistic worlds. They don't have to be complicated. Your idea should be clear and straightforward. It might be fully realistic as dreams often are.

  // IMPORTANT: The user's prompt is the SOLE basis for your dream world. Every field in your output MUST directly reflect the prompt's theme, setting, and mood. Do not invent unrelated worlds.

  // Output JSON only:
  // {
  //   "world": "~100 word description of world rules, atmosphere, physics — derived from the prompt",
  //   "writingStyle": "narrative voice that fits the prompt",
  //   "visualStyle": "image aesthetic that fits the prompt",
  //   "audioStyle": "sound design that fits the prompt"
  // }`;

  //   const { examples, note } = pickRandomExamples();

  let userPrompt = "";

  // //   if (examples.length > 0) {
  // //     const examplesBlock = examples
  // //       .map(
  // //         (ex, i) =>
  // //           `Example ${i + 1}:\n  world: "${ex.world}"\n  writingStyle: "${ex.writingStyle}"\n  visualStyle: "${ex.visualStyle}"\n  audioStyle: "${ex.audioStyle}"`,
  // //       )
  // //       .join("\n\n");

  // //     userPrompt += `--- STYLE EXAMPLES (structural reference only) ---
  // // ${examplesBlock}

  // // ${note}

  // // ---

  // // `;
  // //   }

  //   userPrompt += `USER PROMPT: "${userPromptText}"

  // Create a dream world that is DIRECTLY about the above prompt. All fields must reflect this prompt.`;

  logAgentCall("Initiator", systemPrompt, userPrompt);

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: systemPrompt,
    messages: [{ role: "user", content: userPrompt }],
  });

  const text =
    response.content[0].type === "text" ? response.content[0].text : "";
  const parsed = parseAgentResponse<any>(text, "Initiator");
  validateInitiatorOutput(parsed);

  logAgentResponse("Initiator", text, parsed);
  logAgentDisconnect("Initiator", true);

  return parsed;
}

// Agent 2: Storyteller (maintains full history)
async function runStoryteller(
  state: GameState,
  directorGuidance?: string,
): Promise<{ storyText: string; updatedHistory: ConversationMessage[] }> {
  const worldRules = state.dreamLayer.world;
  const writingStyle = state.dreamLayer.writingStyle;
  const poi = state.dreamLayer.poi;

  const systemPrompt = `You are a dream narrator. Write 2-4 sentence story continuations.

Rules:
- React to player choices (show consequences)
- Reference POI (current objective) when relevant
- Use concrete details, avoid "dreamlike" labels
- Maintain continuity with conversation history

World Rules: ${worldRules}
Writing Style: ${writingStyle}
${poi ? `Current POI: ${poi.description}` : ""}
${directorGuidance ? `\nDirector Guidance: ${directorGuidance}` : ""}

Output JSON:
{
  "text": "2-4 sentence narrative"
}`;

  const trimmedHistory = trimConversationHistory(state.conversationHistory);

  const userPrompt =
    trimmedHistory.length === 0
      ? "Begin the dream story."
      : "Continue the story based on the latest events.";

  const messages: ConversationMessage[] = [
    ...trimmedHistory,
    { role: "user", content: userPrompt },
  ];

  logAgentCall("Storyteller", systemPrompt, userPrompt, trimmedHistory.length);

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: systemPrompt,
    messages,
  });

  const text =
    response.content[0].type === "text" ? response.content[0].text : "";
  const parsed = parseAgentResponse<{ text: string }>(text, "Storyteller");

  if (!parsed.text || typeof parsed.text !== "string") {
    throw new Error('Storyteller output missing or invalid "text" field');
  }

  logAgentResponse("Storyteller", text, parsed);

  const updatedHistory: ConversationMessage[] = [
    ...trimmedHistory,
    { role: "user", content: userPrompt },
    { role: "assistant", content: text },
  ];

  logAgentDisconnect("Storyteller", false);

  return { storyText: parsed.text, updatedHistory };
}

// Agent 3: Brancher (resets each step)
interface Choice {
  id: string;
  text: string;
}

async function runBrancher(
  state: GameState,
  lastStorytellerOutput: string,
): Promise<Choice[]> {
  const summary = createStorySummary(state);
  const decisionsHistory = createDecisionsHistory(state);

  const systemPrompt = `Generate 1-4 meaningful choices based on story context.
Each choice: 3-8 words, actionable.

Output JSON:
{
  "choices": [
    {"id": "c1", "text": "..."},
    {"id": "c2", "text": "..."}
  ]
}`;

  const userPrompt = `${summary}

${decisionsHistory}

LAST STORY EVENT:
${lastStorytellerOutput}

Generate 1-4 choices for the player.`;

  logAgentCall("Brancher", systemPrompt, userPrompt);

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: systemPrompt,
    messages: [{ role: "user", content: userPrompt }],
  });

  const text =
    response.content[0].type === "text" ? response.content[0].text : "";
  const parsed = parseAgentResponse<{ choices: Choice[] }>(text, "Brancher");

  if (!Array.isArray(parsed.choices) || parsed.choices.length === 0) {
    throw new Error('Brancher output missing or empty "choices" array');
  }

  parsed.choices.forEach((choice, index) => {
    if (!choice.id || !choice.text) {
      throw new Error(`Brancher choice[${index}] missing id or text`);
    }
  });

  logAgentResponse("Brancher", text, parsed);
  logAgentDisconnect("Brancher", true);

  return parsed.choices;
}

// Agent 4: Judge (resets each step)
async function runJudge(
  storytellerOutput: string,
  choices: Choice[],
): Promise<JudgeOutput> {
  const systemPrompt = `Evaluate story event and each choice for metric impact.
Output values: ±5 to ±25 for arousal, valence, selfAwareness.

Arousal: Physical/action intensity (negative = calm, positive = intense)
Valence: Emotional tone (negative = negative emotions, positive = positive emotions)
SelfAwareness: Dream lucidity (negative = immersed, positive = aware it's a dream)

Output JSON:
{
  "event": {"arousal": 0, "valence": 0, "selfAwareness": 0},
  "choices": [
    {"arousal": 0, "valence": 0, "selfAwareness": 0},
    ...
  ]
}`;

  const choicesText = choices.map((c, i) => `${i + 1}. ${c.text}`).join("\n");

  const userPrompt = `STORY EVENT:
${storytellerOutput}

CHOICES:
${choicesText}

Rate the story event and each choice (±5 to ±25 for each metric).`;

  logAgentCall("Judge", systemPrompt, userPrompt);

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: systemPrompt,
    messages: [{ role: "user", content: userPrompt }],
  });

  const text =
    response.content[0].type === "text" ? response.content[0].text : "";
  const parsed = parseAgentResponse<any>(text, "Judge");
  validateJudgeOutput(parsed);

  logAgentResponse("Judge", text, parsed);
  logAgentDisconnect("Judge", true);

  return parsed;
}

// Agent 5: Director (resets each step)
async function runDirector(
  state: GameState,
  storytellerOutput: string,
  choices: Choice[],
  judgeOutput: JudgeOutput,
  userChoice: Choice,
): Promise<DirectorOutput> {
  const summary = createStorySummary(state);
  const decisionsHistory = createDecisionsHistory(state);

  const systemPrompt = `Orchestrate narrative. Decide structure changes and guide Storyteller.

Output JSON:
{
  "locationChange": boolean,
  "poi": boolean (show/update POI),
  "timedEvent": boolean (10-second urgent challenge),
  "guidance": "Text instructions for Storyteller about what happens next"
}`;

  const choicesWithMetrics = choices
    .map(
      (c, i) =>
        `${i + 1}. "${c.text}" → arousal:${judgeOutput.choices[i].arousal}, valence:${judgeOutput.choices[i].valence}, selfAwareness:${judgeOutput.choices[i].selfAwareness}`,
    )
    .join("\n");

  const userPrompt = `${summary}

${decisionsHistory}

LAST STORY EVENT:
${storytellerOutput}
Event metrics → arousal:${judgeOutput.event.arousal}, valence:${judgeOutput.event.valence}, selfAwareness:${judgeOutput.event.selfAwareness}

CHOICES:
${choicesWithMetrics}

USER CHOSE: "${userChoice.text}"

Current metrics: arousal=${state.metrics.arousal}, valence=${state.metrics.valence}, selfAwareness=${state.metrics.selfAwareness}
Step ${state.dreamLayer.stepCount}/${state.dreamLayer.maxSteps}

Decide what happens next and guide the Storyteller.`;

  logAgentCall("Director", systemPrompt, userPrompt);

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: systemPrompt,
    messages: [{ role: "user", content: userPrompt }],
  });

  const text =
    response.content[0].type === "text" ? response.content[0].text : "";
  const parsed = parseAgentResponse<any>(text, "Director");
  validateDirectorOutput(parsed);

  logAgentResponse("Director", text, parsed);
  logAgentDisconnect("Director", true);

  return parsed;
}

// Main orchestrator
export async function generateStep(state: GameState): Promise<Step> {
  return withRetry(async () => {
    // Step 1: Run Initiator if first time
    if (!state.dreamLayer.world) {
      const initiatorOutput = await runInitiator(
        state.initialThought || generateRandomSeed(),
      );
      state.dreamLayer.world = initiatorOutput.world;
      state.dreamLayer.writingStyle = initiatorOutput.writingStyle;
      state.dreamLayer.visualStyle = initiatorOutput.visualStyle;
      state.dreamLayer.audioStyle = initiatorOutput.audioStyle;

      // Create initial location (location system to be fully implemented later)
      state.dreamLayer.locations = [
        {
          id: "loc-0",
          name: "Dream Space",
          description: initiatorOutput.world,
          visualStyle: initiatorOutput.visualStyle,
          audioStyle: initiatorOutput.audioStyle,
          imageUrl: "", // Images generated on-demand via /generate-image endpoint
        },
      ];
      state.dreamLayer.currentLocationIndex = 0;
    }

    // Step 2: Get Director guidance if not first step
    let directorGuidance: string | undefined;
    if (
      state.dreamLayer.stepCount > 0 &&
      state.lastStepData &&
      state.storyHistory.length > 0
    ) {
      const lastEntry = state.storyHistory[state.storyHistory.length - 1];
      const userChoice: Choice = { id: "last", text: lastEntry.chosenAction };

      // Run Director with data from last step
      const directorOutput = await runDirector(
        state,
        state.lastStepData.storytellerOutput,
        state.lastStepData.choices,
        state.lastStepData.judgeOutput,
        userChoice,
      );

      directorGuidance = directorOutput.guidance;

      // Handle Director flags
      if (directorOutput.locationChange) {
        // TODO: Implement location change logic
      }
      if (directorOutput.poi) {
        // TODO: Implement POI update logic
      }
      if (directorOutput.timedEvent) {
        // TODO: Implement timed event logic
      }
    }

    // Step 3: Run Storyteller
    const { storyText, updatedHistory } = await runStoryteller(
      state,
      directorGuidance,
    );
    state.conversationHistory = updatedHistory;

    // Step 4: Run Brancher
    const choices = await runBrancher(state, storyText);

    // Step 5: Run Judge
    const judgeOutput = await runJudge(storyText, choices);

    // Step 6: Generate scene image for current location on each step
    const currentLocation =
      state.dreamLayer.locations[state.dreamLayer.currentLocationIndex];
    if (currentLocation) {
      try {
        const imageUrl = await generateSceneImage({
          visualStyle: state.dreamLayer.visualStyle,
          locationDescription: currentLocation.description,
          storyContext: storyText,
        });
        currentLocation.imageUrl = imageUrl;
      } catch (error) {
        console.error("Image generation failed:", error);
        // Continue without image - game is playable without it
      }
    }

    // Step 7: Create Step object
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
        successChance: 100, // Default success chance
        leadsToNode: null,
      })),
      locationId:
        state.dreamLayer.locations[state.dreamLayer.currentLocationIndex]?.id ||
        "",
      poiVisible: state.dreamLayer.poi !== null,
      isTimed: false,
      timedDeadline: undefined,
    };

    // Store current step
    state.currentStep = step;
    state.stepHistory.push(step.id);

    // Store data for next Director call
    state.lastStepData = {
      storytellerOutput: storyText,
      choices,
      judgeOutput,
    };

    return step;
  }, "generateStep");
}
