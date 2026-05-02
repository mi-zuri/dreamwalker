import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';

import sessionRouter from './routes/session.js';
import mediaRouter from './routes/media.js';
import { cleanupExpiredSessions, getSession, getSessionCount } from './session-store.js';
import { startCleanupSchedule } from './services/cache.js';
import {
  startAudioStream,
  stopAudioStream,
  cleanupAllAudioSessions,
  generateSoundscape,
} from './services/audio.js';

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 3001;
const SESSION_CLEANUP_MS = 5 * 60 * 1000;

const app = express();
app.use(cors());
app.use(express.json());

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', sessions: getSessionCount() });
});

app.use('/api/session', sessionRouter);
app.use('/api/media', mediaRouter);

const server = createServer(app);
const wss = new WebSocketServer({ server, path: '/api/audio' });

wss.on('connection', (ws, req) => {
  const url = new URL(req.url ?? '', `http://${req.headers.host}`);
  const sessionId = url.searchParams.get('sessionId');
  if (!sessionId) return ws.close(1008, 'Missing sessionId');

  const state = getSession(sessionId);
  if (!state) return ws.close(1008, 'Session not found');

  const { description, bpm } = generateSoundscape(
    state.metrics.arousal,
    state.metrics.valence,
    state.metrics.selfAwareness,
  );

  startAudioStream(
    sessionId,
    { audioStyle: state.dreamLayer.audioStyle, soundscape: description, bpm },
    ws,
  ).catch((error) => {
    console.error('Audio stream error:', error);
    ws.close(1011, 'Audio stream failed');
  });

  ws.on('close', () => {
    stopAudioStream(sessionId).catch((error) =>
      console.error('Error stopping audio stream:', error),
    );
  });
});

const cleanupInterval = setInterval(cleanupExpiredSessions, SESSION_CLEANUP_MS);
const cacheCleanupInterval = startCleanupSchedule();

async function shutdown() {
  clearInterval(cleanupInterval);
  clearInterval(cacheCleanupInterval);
  await cleanupAllAudioSessions();
  wss.clients.forEach((client) => client.close());
  wss.close();
  server.close(() => process.exit(0));
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
