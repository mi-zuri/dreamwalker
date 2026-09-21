/**
 * Backend client.
 *
 * Every response shape here comes from `types.ts`, which is itself projected
 * from the generated OpenAPI schema, so a backend contract change breaks the
 * build rather than the game.
 */

import { idToken } from '../auth/firebase';
import type {
  AppErrorKind,
  EndingComparison,
  GameState,
  NewGameRequest,
  NewsStory,
  Pos,
  Region,
  Replay,
  SavedGame,
  Stage,
  User,
} from '../types';

export class ApiError extends Error {
  kind: AppErrorKind;

  constructor(kind: AppErrorKind, detail?: string) {
    super(detail ?? kind);
    this.kind = kind;
  }
}

async function headers(body: boolean): Promise<HeadersInit> {
  const h: Record<string, string> = {};
  if (body) h['Content-Type'] = 'application/json';
  const token = await idToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    if (body && typeof body.kind === 'string') return new ApiError(body.kind, body.detail);
  } catch {
    // Non-JSON failure (a proxy error page, a dropped connection).
  }
  return new ApiError(res.status === 401 ? 'auth' : 'network', `HTTP ${res.status}`);
}

async function request<T>(
  path: string,
  init?: Omit<RequestInit, 'body'> & { body?: unknown },
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: await headers(init?.body !== undefined),
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch (e) {
    throw new ApiError('network', e instanceof Error ? e.message : String(e));
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body });

export const me = () => request<User>('/me');
export const createGame = (req: NewGameRequest) => post<{ game_id: string }>('/games', req);
export const getGame = (id: string) => request<GameState>(`/games/${id}`);
export const move = (id: string, to: Pos) => post<GameState>(`/games/${id}/move`, { to });
export const choose = (id: string, choice_id: string) =>
  post<GameState>(`/games/${id}/choose`, { choice_id });
export const answer = (id: string, text: string) =>
  post<GameState>(`/games/${id}/answer`, { text });
export const setOff = (id: string) => post<GameState>(`/games/${id}/set-off`);
export const getEnding = (id: string) => request<EndingComparison>(`/games/${id}/ending`);
export const listGames = () => request<SavedGame[]>('/games');
export const listNews = (region: Region) => request<NewsStory[]>(`/news?region=${region}`);
export const getReplay = (id: string) => request<Replay>(`/games/${id}/replay`);

export const forceError = (kind: AppErrorKind | null) => post<unknown>('/dev/force-error', { kind });

/**
 * Loading progress.
 *
 * Read with `fetch` rather than `EventSource` because the stream needs the
 * bearer token in a header - `EventSource` can only put it in the URL, where
 * it would end up in access logs. Returns a cancel function.
 */
export function streamStages(
  gameId: string,
  onStage: (stage: Stage) => void,
  onReady: () => void,
  onError: (e: ApiError) => void,
): () => void {
  const abort = new AbortController();

  (async () => {
    try {
      const res = await fetch(`/api/games/${gameId}/stream`, {
        headers: await headers(false),
        signal: abort.signal,
      });
      if (!res.ok || !res.body) throw await toError(res);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line.
        let cut: number;
        while ((cut = buffer.indexOf('\n\n')) >= 0) {
          const frame = buffer.slice(0, cut);
          buffer = buffer.slice(cut + 2);
          const data = frame
            .split('\n')
            .filter((l) => l.startsWith('data:'))
            .map((l) => l.slice(5).trim())
            .join('');
          if (!data) continue;
          const payload = JSON.parse(data) as {
            stage?: Stage;
            ready?: boolean;
            kind?: AppErrorKind;
            detail?: string;
          };
          // Generation runs after the create call has already returned, so a
          // failure has nowhere to surface except here.
          if (payload.kind) {
            onError(new ApiError(payload.kind, payload.detail));
            return;
          }
          if (payload.stage) onStage(payload.stage);
          if (payload.ready) {
            onReady();
            return;
          }
        }
      }
      // The stream closed without a `ready` frame; the game may still be fine.
      onReady();
    } catch (e) {
      if (abort.signal.aborted) return;
      onError(e instanceof ApiError ? e : new ApiError('network', String(e)));
    }
  })();

  return () => abort.abort();
}
