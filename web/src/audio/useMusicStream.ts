import { useEffect, useRef, useCallback } from 'react';
import { idToken } from '../auth/firebase';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;
/** Drop incoming audio once we are this far ahead; the stream has run away from playback. */
const MAX_LEAD_SECONDS = 2;
const RECONNECT_DELAY_MS = 2000;

/** What the backend tells us over the same socket it sends audio on. */
type Control =
  | { mode: 'realtime' }
  | { mode: 'loops'; url: string; reason?: string }
  | { mode: 'off'; reason?: string };

async function musicUrl(gameId: string): Promise<string> {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = await idToken();
  // A browser WebSocket cannot set headers, so the token rides in the query
  // string. Only this endpoint does that; the SSE stream reads its body with
  // `fetch` precisely so its token can stay in a header.
  const auth = token ? `&token=${encodeURIComponent(token)}` : '';
  return `${scheme}//${window.location.host}/api/music?game_id=${encodeURIComponent(gameId)}${auth}`;
}

/**
 * Plays the backend's music.
 *
 * Normally that is the Lyria proxy: interleaved 16-bit PCM at 48kHz stereo,
 * scheduled gaplessly onto a single AudioContext timeline. If Lyria is
 * unavailable the backend sends a loop URL instead and this plays that on an
 * `<audio>` element, which is why the fallback is silent rather than audible.
 *
 * `locationId` steers the music: whenever it changes, the backend is told, and
 * it rebuilds the prompt for wherever the player now is.
 */
export function useMusicStream(gameId: string | null, locationId?: string | null) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const loopRef = useRef<HTMLAudioElement | null>(null);
  const nextStartTimeRef = useRef<number>(0);

  useEffect(() => {
    if (!gameId) return;

    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function stopLoop() {
      loopRef.current?.pause();
      loopRef.current = null;
    }

    function handleControl(control: Control) {
      if (control.mode === 'loops') {
        stopLoop();
        const element = new Audio(control.url);
        element.loop = true;
        element.volume = 0.7;
        // Autoplay may be blocked until the player has clicked something;
        // `resume` below is called from a gesture and retries.
        element.play().catch(() => undefined);
        loopRef.current = element;
      } else if (control.mode === 'off') {
        stopLoop();
      }
    }

    async function connect() {
      if (cancelled) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
      }
      const ctx = audioContextRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      const ws = new WebSocket(await musicUrl(gameId!));
      if (cancelled) {
        ws.close();
        return;
      }
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        nextStartTimeRef.current = ctx.currentTime;
        if (locationId) ws.send(JSON.stringify({ location: locationId }));
      };

      ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
          try {
            handleControl(JSON.parse(event.data) as Control);
          } catch {
            // A control frame we cannot read is not worth killing music over.
          }
          return;
        }
        if (!(event.data instanceof ArrayBuffer)) return;

        // If playback has fallen far behind the stream, skip ahead rather than
        // queueing an ever-growing backlog of buffers.
        if (nextStartTimeRef.current - ctx.currentTime > MAX_LEAD_SECONDS) return;

        const pcmData = new Int16Array(event.data);
        const numFrames = pcmData.length / CHANNELS;
        if (numFrames === 0) return;

        const audioBuffer = ctx.createBuffer(CHANNELS, numFrames, SAMPLE_RATE);
        const left = audioBuffer.getChannelData(0);
        const right = audioBuffer.getChannelData(1);
        for (let i = 0; i < numFrames; i++) {
          left[i] = pcmData[i * 2] / 32768;
          right[i] = pcmData[i * 2 + 1] / 32768;
        }

        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
        source.start(startTime);
        nextStartTimeRef.current = startTime + audioBuffer.duration;
      };

      ws.onerror = () => {
        // `onclose` follows and handles the retry; logging both is noise.
      };

      ws.onclose = () => {
        if (cancelled) return;
        wsRef.current = null;
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      stopLoop();
      wsRef.current?.close();
      wsRef.current = null;
    };
    // `locationId` is sent through the open socket below rather than
    // reconnecting, so it is deliberately not a dependency here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId]);

  /** Tell the backend where the player is now, so the music can follow. */
  useEffect(() => {
    const ws = wsRef.current;
    if (!locationId || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ location: locationId }));
  }, [locationId]);

  /** Unlocks audio playback; must be called from a user gesture. */
  const resume = useCallback(() => {
    if (audioContextRef.current?.state === 'suspended') {
      audioContextRef.current.resume().catch(() => undefined);
    }
    loopRef.current?.play().catch(() => undefined);
  }, []);

  return { resume };
}
