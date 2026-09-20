"""The Lyria RealTime connection.

Lyria is Gemini-API-only - it is not on Vertex - so this is the one part of
the backend that uses an API key rather than ADC. It also has no ephemeral
token support (tokens are documented as Live-API-only), which is why the
session has to live on the server at all: the browser cannot hold one.

Ported from `server/src/services/audio.ts`, keeping the two things that
version got right: tolerant handling of whatever shape a chunk arrives in, and
never re-sending a prompt that has not changed. The second matters more than
it looks - the old code called the API on every step and the guard was the
only thing stopping it.

Verified live: 48kHz stereo 16-bit PCM, 192000 bytes per second of audio,
arriving in a few large chunks rather than a steady trickle.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.settings import settings

log = logging.getLogger(__name__)

SAMPLE_RATE = 48_000
CHANNELS = 2
BYTES_PER_SAMPLE = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE


class MusicUnavailable(RuntimeError):
    """Lyria could not be reached, or refused. The caller falls back to loops."""


def chunk_bytes(chunk: object) -> bytes | None:
    """Whatever shape a chunk arrives in, get the PCM out of it.

    The SDK is experimental and has changed the wrapper around this more than
    once; the bytes have always been in there somewhere.
    """
    data = getattr(chunk, "data", chunk)
    if isinstance(data, bytes | bytearray):
        return bytes(data)
    if isinstance(data, str):
        from base64 import b64decode

        with contextlib.suppress(ValueError):
            return b64decode(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    return None


def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise MusicUnavailable("GEMINI_API_KEY is unset; live music needs one")
    # Not cached: a music session owns its client for its lifetime and closing
    # it is how the connection is released.
    return genai.Client(api_key=settings.gemini_api_key, http_options={"api_version": "v1alpha"})


class LyriaStream:
    """One live music session. Async-iterate it for PCM."""

    def __init__(self, prompt: str, bpm: int) -> None:
        self._prompt = prompt
        self._bpm = bpm
        self._session = None
        self._exit = None

    async def open(self) -> None:
        try:
            self._exit = _client().aio.live.music.connect(model=settings.music_model)
            self._session = await self._exit.__aenter__()
            await self._apply(self._prompt, self._bpm)
            await self._session.play()
        except Exception as exc:
            await self.close()
            raise MusicUnavailable(str(exc)) from exc

    async def _apply(self, prompt: str, bpm: int) -> None:
        await self._session.set_weighted_prompts(
            prompts=[types.WeightedPrompt(text=prompt, weight=1.0)]
        )
        await self._session.set_music_generation_config(
            config=types.LiveMusicGenerationConfig(bpm=bpm, temperature=1.0)
        )

    async def steer(self, prompt: str, bpm: int) -> bool:
        """Move the music. Returns False when nothing needed to change."""
        if self._session is None:
            return False
        if prompt == self._prompt and bpm == self._bpm:
            return False
        try:
            await self._apply(prompt, bpm)
        except Exception as exc:  # noqa: BLE001 - a failed steer is not fatal
            log.warning("could not steer the music: %s", exc)
            return False
        self._prompt, self._bpm = prompt, bpm
        return True

    async def chunks(self) -> AsyncIterator[bytes]:
        if self._session is None:
            return
        async for message in self._session.receive():
            content = getattr(message, "server_content", None)
            for chunk in getattr(content, "audio_chunks", None) or []:
                data = chunk_bytes(chunk)
                if data:
                    yield data

    async def close(self) -> None:
        session, self._session = self._session, None
        exit_, self._exit = self._exit, None
        if session is not None:
            with contextlib.suppress(Exception):
                await session.stop()
        if exit_ is not None:
            with contextlib.suppress(Exception):
                await exit_.__aexit__(None, None, None)


async def capture(prompt: str, bpm: int, seconds: float) -> bytes:
    """Record a fixed stretch of PCM. Used to build the loop library."""
    stream = LyriaStream(prompt, bpm)
    await stream.open()
    wanted = int(seconds * BYTES_PER_SECOND)
    buffer = bytearray()
    try:
        async with asyncio.timeout(seconds * 4 + 20):
            async for data in stream.chunks():
                buffer.extend(data)
                if len(buffer) >= wanted:
                    break
    except TimeoutError:
        log.warning("capture timed out with %d of %d bytes", len(buffer), wanted)
    finally:
        await stream.close()
    return bytes(buffer[:wanted])
