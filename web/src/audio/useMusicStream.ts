import { useEffect, useRef, useCallback } from 'react';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;
/** Drop incoming audio once we are this far ahead; the stream has run away from playback. */
const MAX_LEAD_SECONDS = 2;
const RECONNECT_DELAY_MS = 2000;

function musicUrl(gameId: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${window.location.host}/api/music?game_id=${encodeURIComponent(gameId)}`;
}

/**
 * Plays the backend's Lyria proxy stream: interleaved 16-bit PCM at 48kHz stereo,
 * scheduled gaplessly onto a single AudioContext timeline.
 */
export function useMusicStream(gameId: string | null) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const nextStartTimeRef = useRef<number>(0);

  useEffect(() => {
    if (!gameId) return;

    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
      }
      const ctx = audioContextRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      const ws = new WebSocket(musicUrl(gameId!));
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        nextStartTimeRef.current = ctx.currentTime;
      };

      ws.onmessage = (event) => {
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

      ws.onerror = (error) => console.error('Music WebSocket error:', error);

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
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [gameId]);

  /** Unlocks the AudioContext; must be called from a user gesture. */
  const resume = useCallback(() => {
    if (audioContextRef.current?.state === 'suspended') {
      audioContextRef.current.resume().catch((err) => {
        console.error('Failed to resume AudioContext:', err);
      });
    }
  }, []);

  return { resume };
}
