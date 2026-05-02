import { useEffect, useRef, useCallback } from 'react';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;

export function useAudioStream(sessionId: string | null) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const nextStartTimeRef = useRef<number>(0);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
      }
      const ctx = audioContextRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      const ws = new WebSocket(
        `ws://${window.location.hostname}:3001/api/audio?sessionId=${sessionId}`,
      );
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        nextStartTimeRef.current = ctx.currentTime;
      };

      ws.onmessage = (event) => {
        if (!(event.data instanceof ArrayBuffer)) return;
        const pcmData = new Int16Array(event.data);
        const floatData = new Float32Array(pcmData.length);
        for (let i = 0; i < pcmData.length; i++) floatData[i] = pcmData[i] / 32768;

        const numFrames = floatData.length / CHANNELS;
        const audioBuffer = ctx.createBuffer(CHANNELS, numFrames, SAMPLE_RATE);
        const left = audioBuffer.getChannelData(0);
        const right = audioBuffer.getChannelData(1);
        for (let i = 0; i < numFrames; i++) {
          left[i] = floatData[i * 2];
          right[i] = floatData[i * 2 + 1];
        }

        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
        source.start(startTime);
        nextStartTimeRef.current = startTime + audioBuffer.duration;
      };

      ws.onerror = (error) => console.error('Audio WebSocket error:', error);

      ws.onclose = () => {
        if (cancelled) return;
        wsRef.current = null;
        reconnectTimer = setTimeout(connect, 2000);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId]);

  const resume = useCallback(() => {
    if (audioContextRef.current?.state === 'suspended') {
      audioContextRef.current.resume().catch((err) => {
        console.error('Failed to resume AudioContext:', err);
      });
    }
  }, []);

  return { resume };
}
