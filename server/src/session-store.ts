import type { GameState } from '../../shared/types.js';

interface SessionEntry {
  state: GameState;
  lastActivity: number;
}

const sessions = new Map<string, SessionEntry>();

const SESSION_TTL_MS = 60 * 60 * 1000; // 1 hour

export function getSession(id: string): GameState | undefined {
  const entry = sessions.get(id);
  if (entry) {
    entry.lastActivity = Date.now();
    return entry.state;
  }
  return undefined;
}

export function setSession(id: string, state: GameState): void {
  sessions.set(id, { state, lastActivity: Date.now() });
}

export function deleteSession(id: string): boolean {
  return sessions.delete(id);
}

export function cleanupExpiredSessions(): number {
  const now = Date.now();
  let cleaned = 0;
  for (const [id, entry] of sessions) {
    if (now - entry.lastActivity > SESSION_TTL_MS) {
      sessions.delete(id);
      cleaned++;
    }
  }
  return cleaned;
}

export function getSessionCount(): number {
  return sessions.size;
}
