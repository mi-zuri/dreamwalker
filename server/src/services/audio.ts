import { GoogleGenAI } from '@google/genai';
import type { WebSocket } from 'ws';

const client = new GoogleGenAI({
  apiKey: process.env.GOOGLE_API_KEY || '',
  apiVersion: 'v1alpha',
});

interface AudioSessionParams {
  audioStyle: string;
  soundscape: string;
  bpm?: number;
}

interface AudioSession {
  sessionId: string;
  params: AudioSessionParams;
  clientSocket: WebSocket;
  isActive: boolean;
  lyriaSession?: any; // Lyria music session
}

const activeSessions = new Map<string, AudioSession>();

// Extract BPM from soundscape description
function extractBPM(soundscape: string): number {
  const bpmMatch = soundscape.match(/(\d+)\s*bpm/i);
  return bpmMatch ? parseInt(bpmMatch[1], 10) : 70; // Default 70 BPM
}

// Start audio streaming session
export async function startAudioStream(
  sessionId: string,
  params: AudioSessionParams,
  clientSocket: WebSocket
): Promise<void> {
  // Clean up any existing session
  await stopAudioStream(sessionId);

  const bpm = params.bpm || extractBPM(params.soundscape);

  console.log(`\n${'='.repeat(80)}`);
  console.log(`🔵 CONNECTING: LYRIA AUDIO`);
  console.log(`⏰ ${new Date().toISOString()}`);
  console.log(`Session: ${sessionId}`);
  console.log(`\n--- PARAMETERS ---`);
  console.log(`Audio Style: ${params.audioStyle}`);
  console.log(`Soundscape: ${params.soundscape}`);
  console.log(`BPM: ${bpm}`);
  console.log('='.repeat(80));

  const session: AudioSession = {
    sessionId,
    params: { ...params, bpm },
    clientSocket,
    isActive: true,
  };

  activeSessions.set(sessionId, session);

  // Generate audio with Lyria using Google Generative AI
  try {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`🟢 LYRIA STATUS: Starting audio generation`);
    console.log(`⏰ ${new Date().toISOString()}`);
    console.log('='.repeat(80));

    // Connect to Lyria real-time music generation
    const lyriaSession = await client.live.music.connect({
      model: 'models/lyria-realtime-exp',
      callbacks: {
        onmessage: (message: any) => {
          if (message.serverContent?.audioChunks && session.isActive && clientSocket.readyState === 1) {
            const chunks = message.serverContent.audioChunks;
            console.log(`🎵 Received ${chunks.length} audio chunks from Lyria`);

            // Forward raw audio chunks to client (16-bit PCM, 48kHz stereo)
            for (const chunk of chunks) {
              let binaryData: Buffer | null = null;

              if (chunk?.data) {
                // Handle chunk.data which might be base64 or array
                if (typeof chunk.data === 'string') {
                  // Base64 encoded audio data
                  binaryData = Buffer.from(chunk.data, 'base64');
                } else if (Buffer.isBuffer(chunk.data)) {
                  binaryData = chunk.data;
                } else if (chunk.data instanceof Uint8Array) {
                  binaryData = Buffer.from(chunk.data);
                } else if (ArrayBuffer.isView(chunk.data)) {
                  binaryData = Buffer.from(chunk.data.buffer);
                }
              } else if (typeof chunk === 'string') {
                // Chunk is base64 string directly
                binaryData = Buffer.from(chunk, 'base64');
              } else if (Buffer.isBuffer(chunk)) {
                binaryData = chunk;
              } else if (chunk instanceof Uint8Array) {
                binaryData = Buffer.from(chunk);
              }

              if (binaryData) {
                console.log(`  → Sending binary chunk: ${binaryData.length} bytes`);
                clientSocket.send(binaryData, { binary: true });
              } else {
                console.warn(`  ⚠️  Unknown chunk format:`, typeof chunk, chunk?.constructor?.name);
              }
            }
          }
        },
        onerror: (error: any) => {
          console.error(`❌ LYRIA ERROR: ${error.message || 'Unknown error'}`);
          session.isActive = false;
        },
      },
    });

    // Store Lyria session for cleanup
    session.lyriaSession = lyriaSession;

    // Build initial weighted prompt from audio style and soundscape
    const promptText = `${params.audioStyle}. ${params.soundscape}. Dreamlike ambient music`;

    console.log(`🎵 Initial prompt: ${promptText}`);
    console.log(`🎼 Initial BPM: ${bpm}`);

    await lyriaSession.setWeightedPrompts({
      weightedPrompts: [
        { text: promptText, weight: 1.0 },
      ],
    });

    // Configure music generation parameters
    await lyriaSession.setMusicGenerationConfig({
      musicGenerationConfig: {
        bpm,
        temperature: 1.0,
      },
    });

    // Start playback
    lyriaSession.play();

    console.log(`✅ AUDIO SESSION INITIALIZED - Streaming started`);
  } catch (error) {
    console.error(`\n❌ LYRIA ERROR: ${error instanceof Error ? error.message : 'Unknown'}`);
    console.log(`🔴 DISCONNECT: LYRIA AUDIO\n`);
    session.isActive = false;

    // Cleanup Lyria session on error
    if (session.lyriaSession) {
      try {
        await session.lyriaSession.stop();
      } catch (e) {
        // Ignore cleanup errors
      }
    }

    activeSessions.delete(sessionId);
    throw error;
  }
}

// Stop audio streaming session
export async function stopAudioStream(sessionId: string): Promise<void> {
  const session = activeSessions.get(sessionId);
  if (session) {
    session.isActive = false;

    // Stop Lyria session if exists
    if (session.lyriaSession) {
      try {
        await session.lyriaSession.stop();
      } catch (error) {
        console.error(`Error stopping Lyria session: ${error instanceof Error ? error.message : 'Unknown'}`);
      }
    }

    activeSessions.delete(sessionId);
    console.log(`🔴 STOPPING: LYRIA AUDIO`);
    console.log(`Session: ${sessionId}`);
    console.log(`⏰ ${new Date().toISOString()}\n`);
  }
}

// Check if session has active audio stream
export function hasActiveAudioStream(sessionId: string): boolean {
  const session = activeSessions.get(sessionId);
  return session?.isActive ?? false;
}

// Generate dynamic soundscape description based on game metrics (-100 to +100 range)
function generateSoundscape(arousal: number, valence: number, selfAwareness: number): { description: string; bpm: number } {
  // BPM based on absolute arousal (40-120 range)
  const bpm = Math.round(40 + Math.abs(arousal) * 0.8); // 0.8 multiplier for -100/+100 range

  const descriptors: string[] = [];

  // Arousal affects intensity and tempo feel
  const absArousal = Math.abs(arousal);
  if (absArousal < 20) {
    descriptors.push('extremely slow tempo', 'minimal movement', 'long sustained tones');
  } else if (absArousal < 40) {
    descriptors.push('slow pace', 'sparse arrangement', 'spacious');
  } else if (absArousal < 60) {
    descriptors.push('moderate tempo', 'balanced rhythm', 'flowing');
  } else if (absArousal < 80) {
    descriptors.push('energetic', 'rhythmic drive', 'building intensity');
  } else {
    descriptors.push('fast tempo', 'intense', 'dense layering', 'powerful');
  }

  // Valence affects harmonic mood and tonality
  if (valence < -60) {
    descriptors.push('deeply dark', 'heavily dissonant', 'ominous');
  } else if (valence < -20) {
    descriptors.push('dark harmonies', 'minor tonalities', 'tense');
  } else if (valence < 20) {
    descriptors.push('neutral mood', 'atmospheric pads');
  } else if (valence < 60) {
    descriptors.push('warm tones', 'consonant harmonies', 'hopeful');
  } else {
    descriptors.push('bright', 'major key', 'euphoric', 'uplifting');
  }

  // Self-awareness affects textural clarity and definition
  if (selfAwareness < -60) {
    descriptors.push('completely abstract', 'heavily processed', 'dreamlike blur');
  } else if (selfAwareness < -20) {
    descriptors.push('abstract textures', 'blurred boundaries', 'ethereal');
  } else if (selfAwareness < 20) {
    descriptors.push('ambient wash', 'soft textures');
  } else if (selfAwareness < 60) {
    descriptors.push('defined elements', 'clear structure', 'focused');
  } else {
    descriptors.push('hyper-clear', 'sharp definition', 'crystalline', 'precise');
  }

  const description = descriptors.join(', ');
  return { description, bpm };
}

// Update audio prompt dynamically during gameplay
export async function updateAudioPrompt(
  sessionId: string,
  audioStyle: string,
  arousal: number,
  valence: number,
  selfAwareness: number,
  storyContext?: string
): Promise<void> {
  const session = activeSessions.get(sessionId);
  if (!session?.lyriaSession || !session.isActive) {
    console.log(`⚠️  Cannot update audio: session ${sessionId} not active`);
    return;
  }

  const { description, bpm } = generateSoundscape(arousal, valence, selfAwareness);
  const contextHint = storyContext ? `. Scene: ${storyContext.substring(0, 100)}` : '';
  const promptText = `${audioStyle}. ${description}. Dreamlike ambient music${contextHint}`;

  // Store old BPM for comparison
  const oldBpm = session.params.bpm || 70;
  const bpmChange = bpm - oldBpm;

  console.log(`\n${'='.repeat(80)}`);
  console.log(`🔄 UPDATING LYRIA AUDIO`);
  console.log(`⏰ ${new Date().toISOString()}`);
  console.log(`Session: ${sessionId}`);
  console.log(`📊 Metrics: arousal=${arousal.toFixed(0)}, valence=${valence.toFixed(0)}, awareness=${selfAwareness.toFixed(0)}`);
  console.log(`🎼 BPM: ${oldBpm} → ${bpm} (${bpmChange > 0 ? '+' : ''}${bpmChange})`);
  console.log(`🎵 New prompt: ${promptText}`);
  console.log('='.repeat(80));

  try {
    // Update weighted prompts for smooth transition
    await session.lyriaSession.setWeightedPrompts({
      weightedPrompts: [
        { text: promptText, weight: 1.0 },
      ],
    });

    // Update BPM if changed significantly (more than 5 BPM difference)
    if (Math.abs(bpm - (session.params.bpm || 70)) > 5) {
      await session.lyriaSession.setMusicGenerationConfig({
        musicGenerationConfig: {
          bpm,
          temperature: 1.0,
        },
      });
      session.params.bpm = bpm;
    }

    // Update session params
    session.params.audioStyle = audioStyle;

    console.log(`✅ Audio prompt updated successfully`);
  } catch (error) {
    console.error(`❌ Failed to update audio prompt: ${error instanceof Error ? error.message : 'Unknown'}`);
  }
}

// Cleanup all audio sessions
export async function cleanupAllAudioSessions(): Promise<void> {
  const promises = [];
  for (const sessionId of activeSessions.keys()) {
    promises.push(stopAudioStream(sessionId));
  }
  await Promise.all(promises);
}
