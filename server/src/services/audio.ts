import { GoogleGenAI } from '@google/genai';
import type { WebSocket } from 'ws';
import { logAI } from './ai-log.js';

const client = new GoogleGenAI({
  apiKey: process.env.GOOGLE_API_KEY || '',
  apiVersion: 'v1alpha',
});

interface AudioSessionParams {
  audioStyle: string;
  soundscape: string;
  bpm: number;
}

interface AudioSession {
  sessionId: string;
  params: AudioSessionParams;
  clientSocket: WebSocket;
  isActive: boolean;
  lyriaSession?: any;
  lastPromptText?: string;
}

const activeSessions = new Map<string, AudioSession>();

function chunkToBuffer(chunk: any): Buffer | null {
  const data = chunk?.data ?? chunk;
  if (typeof data === 'string') return Buffer.from(data, 'base64');
  if (Buffer.isBuffer(data)) return data;
  if (data instanceof Uint8Array) return Buffer.from(data);
  if (ArrayBuffer.isView(data)) return Buffer.from(data.buffer);
  return null;
}

export async function startAudioStream(
  sessionId: string,
  params: AudioSessionParams,
  clientSocket: WebSocket
): Promise<void> {
  await stopAudioStream(sessionId);

  const session: AudioSession = { sessionId, params, clientSocket, isActive: true };
  activeSessions.set(sessionId, session);

  try {
    const lyriaSession = await client.live.music.connect({
      model: 'models/lyria-realtime-exp',
      callbacks: {
        onmessage: (message: any) => {
          if (!message.serverContent?.audioChunks || !session.isActive || clientSocket.readyState !== 1) return;
          for (const chunk of message.serverContent.audioChunks) {
            const buffer = chunkToBuffer(chunk);
            if (buffer) clientSocket.send(buffer, { binary: true });
          }
        },
        onerror: (error: any) => {
          console.error(`Lyria error: ${error.message || 'Unknown'}`);
          session.isActive = false;
        },
      },
    });

    session.lyriaSession = lyriaSession;

    const promptText = `${params.audioStyle}. ${params.soundscape}. Dreamlike ambient music`;
    await lyriaSession.setWeightedPrompts({ weightedPrompts: [{ text: promptText, weight: 1.0 }] });
    await lyriaSession.setMusicGenerationConfig({
      musicGenerationConfig: { bpm: params.bpm, temperature: 1.0 },
    });
    lyriaSession.play();
    session.lastPromptText = promptText;
    logAI('audio:start', { promptText, bpm: params.bpm }, '<lyria stream open>');
  } catch (error) {
    console.error(`Lyria error: ${error instanceof Error ? error.message : 'Unknown'}`);
    session.isActive = false;
    if (session.lyriaSession) {
      await session.lyriaSession.stop().catch(() => {});
    }
    activeSessions.delete(sessionId);
    throw error;
  }
}

export async function stopAudioStream(sessionId: string): Promise<void> {
  const session = activeSessions.get(sessionId);
  if (!session) return;
  session.isActive = false;
  if (session.lyriaSession) {
    await session.lyriaSession.stop().catch((error: unknown) =>
      console.error(`Error stopping Lyria session: ${error instanceof Error ? error.message : 'Unknown'}`),
    );
  }
  activeSessions.delete(sessionId);
}

// Generate dynamic soundscape description based on game metrics (-100 to +100 range)
export function generateSoundscape(arousal: number, valence: number, selfAwareness: number): { description: string; bpm: number } {
  const bpm = Math.round(40 + Math.abs(arousal) * 0.8);
  const descriptors: string[] = [];

  const absArousal = Math.abs(arousal);
  if (absArousal < 20) descriptors.push('extremely slow tempo', 'minimal movement', 'long sustained tones');
  else if (absArousal < 40) descriptors.push('slow pace', 'sparse arrangement', 'spacious');
  else if (absArousal < 60) descriptors.push('moderate tempo', 'balanced rhythm', 'flowing');
  else if (absArousal < 80) descriptors.push('energetic', 'rhythmic drive', 'building intensity');
  else descriptors.push('fast tempo', 'intense', 'dense layering', 'powerful');

  if (valence < -60) descriptors.push('deeply dark', 'heavily dissonant', 'ominous');
  else if (valence < -20) descriptors.push('dark harmonies', 'minor tonalities', 'tense');
  else if (valence < 20) descriptors.push('neutral mood', 'atmospheric pads');
  else if (valence < 60) descriptors.push('warm tones', 'consonant harmonies', 'hopeful');
  else descriptors.push('bright', 'major key', 'euphoric', 'uplifting');

  if (selfAwareness < -60) descriptors.push('completely abstract', 'heavily processed', 'dreamlike blur');
  else if (selfAwareness < -20) descriptors.push('abstract textures', 'blurred boundaries', 'ethereal');
  else if (selfAwareness < 20) descriptors.push('ambient wash', 'soft textures');
  else if (selfAwareness < 60) descriptors.push('defined elements', 'clear structure', 'focused');
  else descriptors.push('hyper-clear', 'sharp definition', 'crystalline', 'precise');

  return { description: descriptors.join(', '), bpm };
}

export async function updateAudioPrompt(
  sessionId: string,
  audioStyle: string,
  arousal: number,
  valence: number,
  selfAwareness: number,
  storyContext?: string,
): Promise<void> {
  const session = activeSessions.get(sessionId);
  if (!session?.lyriaSession || !session.isActive) return;

  const { description, bpm } = generateSoundscape(arousal, valence, selfAwareness);
  const contextHint = storyContext ? `. Scene: ${storyContext.substring(0, 100)}` : '';
  const promptText = `${audioStyle}. ${description}. Dreamlike ambient music${contextHint}`;

  if (promptText === session.lastPromptText) return;

  try {
    await session.lyriaSession.setWeightedPrompts({ weightedPrompts: [{ text: promptText, weight: 1.0 }] });
    if (Math.abs(bpm - session.params.bpm) > 5) {
      await session.lyriaSession.setMusicGenerationConfig({
        musicGenerationConfig: { bpm, temperature: 1.0 },
      });
      session.params.bpm = bpm;
    }
    session.params.audioStyle = audioStyle;
    session.lastPromptText = promptText;
    logAI('audio:update', { promptText, bpm }, '<prompt updated>');
  } catch (error) {
    console.error(`Failed to update audio prompt: ${error instanceof Error ? error.message : 'Unknown'}`);
  }
}

export async function cleanupAllAudioSessions(): Promise<void> {
  await Promise.all([...activeSessions.keys()].map(stopAudioStream));
}
