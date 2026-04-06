import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';

import sessionRouter from './routes/session.js';
import gameRouter from './routes/game.js';
import mediaRouter from './routes/media.js';
import { cleanupExpiredSessions, getSessionCount } from './sessions.js';
import { startCleanupSchedule, stopCleanupSchedule } from './services/cache.js';
import {
  startAudioStream,
  stopAudioStream,
  cleanupAllAudioSessions,
} from './services/audio.js';
import { getSession } from './sessions.js';

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 3001;
const CLEANUP_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

const app = express();

app.use(cors());
app.use(express.json());

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', sessions: getSessionCount() });
});

// Routes
app.use('/api/session', sessionRouter);
app.use('/api/session', gameRouter);
app.use('/api/media', mediaRouter);

// HTTP server
const server = createServer(app);

// WebSocket server for audio streaming
const wss = new WebSocketServer({ server, path: '/api/audio' });

wss.on('connection', (ws, req) => {
  const url = new URL(req.url ?? '', `http://${req.headers.host}`);
  const sessionId = url.searchParams.get('sessionId');

  if (!sessionId) {
    ws.close(1008, 'Missing sessionId');
    return;
  }

  const state = getSession(sessionId);
  if (!state) {
    ws.close(1008, 'Session not found');
    return;
  }

  // Generate initial soundscape based on metrics
  const arousal = state.metrics.arousal;
  const valence = state.metrics.valence;
  const selfAwareness = state.metrics.selfAwareness;
  const bpm = Math.round(40 + arousal * 80);

  const descriptors: string[] = ['ambient'];
  if (arousal < 0.3) descriptors.push('slow', 'sparse');
  else if (arousal > 0.7) descriptors.push('intense', 'driving');
  if (valence < 0.3) descriptors.push('dark', 'tense');
  else if (valence > 0.7) descriptors.push('bright', 'uplifting');
  if (selfAwareness < 0.3) descriptors.push('ethereal', 'abstract');
  else if (selfAwareness > 0.7) descriptors.push('clear', 'structured');

  const soundscape = `${descriptors.join(', ')}, ${bpm} BPM`;

  // Start audio streaming
  startAudioStream(
    sessionId,
    {
      audioStyle: state.dreamLayer.audioStyle,
      soundscape,
      bpm,
    },
    ws
  ).catch((error) => {
    console.error('Audio stream error:', error);
    ws.close(1011, 'Audio stream failed');
  });

  ws.on('close', () => {
    stopAudioStream(sessionId).catch((error) => {
      console.error('Error stopping audio stream:', error);
    });
  });
});

// Session cleanup interval
const cleanupInterval = setInterval(() => {
  const cleaned = cleanupExpiredSessions();
  if (cleaned > 0) {
    console.log(`Cleaned up ${cleaned} expired sessions`);
  }
}, CLEANUP_INTERVAL_MS);

// Cache cleanup schedule
const cacheCleanupInterval = startCleanupSchedule();

// Graceful shutdown
async function shutdown() {
  console.log('Shutting down...');
  clearInterval(cleanupInterval);
  stopCleanupSchedule(cacheCleanupInterval);

  await cleanupAllAudioSessions();
  wss.clients.forEach((client) => client.close());
  wss.close();

  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });

  setTimeout(() => {
    console.error('Forced shutdown');
    process.exit(1);
  }, 5000);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
