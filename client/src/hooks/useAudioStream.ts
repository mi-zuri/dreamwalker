import { useEffect, useRef, useCallback, useState } from 'react';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;

export function useAudioStream(sessionId: string | null) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const nextStartTimeRef = useRef<number>(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const connectRef = useRef<() => void>(null);

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Create AudioContext on first connect
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
      console.log('🎧 AudioContext created, state:', audioContextRef.current.state);
    }

    const ctx = audioContextRef.current;

    // Resume if suspended (browser autoplay policy)
    if (ctx.state === 'suspended') {
      console.log('⏸️  AudioContext suspended, attempting to resume...');
      ctx.resume().then(() => {
        console.log('▶️  AudioContext resumed, state:', ctx.state);
      });
    } else {
      console.log('🎧 AudioContext state:', ctx.state);
    }

    // Connect to audio WebSocket
    const wsUrl = `ws://${window.location.hostname}:3001/api/audio?sessionId=${sessionId}`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      console.log('🔊 Audio WebSocket connected');
      setIsPlaying(true);
      nextStartTimeRef.current = ctx.currentTime;
    };

    ws.onmessage = (event) => {
      console.log('📨 Received message, type:', typeof event.data, 'instanceof ArrayBuffer:', event.data instanceof ArrayBuffer);

      if (!(event.data instanceof ArrayBuffer)) {
        console.warn('❌ Message is not ArrayBuffer, skipping');
        return;
      }

      console.log('✅ Processing audio chunk:', event.data.byteLength, 'bytes');

      const pcmData = new Int16Array(event.data);
      const floatData = new Float32Array(pcmData.length);

      // Convert 16-bit PCM to float [-1, 1]
      for (let i = 0; i < pcmData.length; i++) {
        floatData[i] = pcmData[i] / 32768;
      }

      // Create stereo audio buffer
      const numFrames = floatData.length / CHANNELS;
      const audioBuffer = ctx.createBuffer(CHANNELS, numFrames, SAMPLE_RATE);

      console.log(`🎵 Audio buffer: ${numFrames} frames, ${audioBuffer.duration.toFixed(2)}s`);

      // Deinterleave stereo channels
      const leftChannel = audioBuffer.getChannelData(0);
      const rightChannel = audioBuffer.getChannelData(1);
      for (let i = 0; i < numFrames; i++) {
        leftChannel[i] = floatData[i * 2];
        rightChannel[i] = floatData[i * 2 + 1];
      }

      // Schedule playback
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      // Schedule at next available time
      const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
      source.start(startTime);
      nextStartTimeRef.current = startTime + audioBuffer.duration;

      console.log(`▶️  Scheduled playback at ${startTime.toFixed(2)}s (current: ${ctx.currentTime.toFixed(2)}s, ctx state: ${ctx.state})`);
    };

    ws.onerror = (error) => {
      console.error('❌ Audio WebSocket error:', error);
    };

    ws.onclose = (event) => {
      console.log(`🔴 Audio WebSocket closed: code=${event.code}, reason=${event.reason}`);
      setIsPlaying(false);
      // Attempt reconnect after delay
      setTimeout(() => {
        if (sessionId && !wsRef.current) {
          console.log('🔄 Attempting to reconnect...');
          connectRef.current?.();
        }
      }, 2000);
    };

    wsRef.current = ws;
  }, [sessionId]);

  useEffect(() => {
    connectRef.current = connect;
  });

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  // Connect when sessionId changes
  useEffect(() => {
    if (sessionId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [sessionId, connect, disconnect]);

  // Resume audio context on user interaction
  const resume = useCallback(() => {
    console.log('🎯 Resume called, AudioContext state:', audioContextRef.current?.state);
    if (audioContextRef.current?.state === 'suspended') {
      audioContextRef.current.resume().then(() => {
        console.log('✅ AudioContext resumed successfully, new state:', audioContextRef.current?.state);
      }).catch((err) => {
        console.error('❌ Failed to resume AudioContext:', err);
      });
    } else {
      console.log('ℹ️  AudioContext already in state:', audioContextRef.current?.state);
    }
  }, []);

  return { resume, isPlaying };
}
