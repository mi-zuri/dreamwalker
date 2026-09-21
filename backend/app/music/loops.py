"""The fallback music: short loops, captured once and then free forever.

The plan called for `lyria-3-clip-preview` at $0.04 a clip. That model exists
on the Gemini API but the installed SDK has no method that reaches it, and
adding a hand-rolled REST call for a fallback path is not a good trade. So the
loops are captured from Lyria RealTime instead - the same model family, the
same prompts, through an API that is already verified working.

One capture per mood, about twenty seconds each, written to the asset store as
WAV. Six moods is six short sessions, once, and then the fallback costs
nothing at all. Built by `python -m app.music.cli build-loops`, or lazily the
first time a live session fails.
"""

import asyncio
import logging
import struct

from app.music.lyria import BYTES_PER_SECOND, CHANNELS, SAMPLE_RATE, MusicUnavailable, capture
from app.music.prompts import DEFAULT_BPM, RULES
from app.pipeline.style_catalog import MUSIC_MOOD
from app.storage.assets import AssetStore

log = logging.getLogger(__name__)

#: Long enough not to sound like a ringtone, short enough to be cheap.
LOOP_SECONDS = 20.0
WAV = "audio/wav"

#: One capture at a time. Two concurrent Lyria sessions for the same fallback
#: would be paying twice for the same file.
_building = asyncio.Lock()


def loop_key(mood: str) -> str:
    return f"music/loop-{mood}.wav"


def to_wav(pcm: bytes) -> bytes:
    """Wrap raw 48kHz stereo 16-bit PCM so a browser will play it."""
    byte_rate = SAMPLE_RATE * CHANNELS * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        CHANNELS,
        SAMPLE_RATE,
        byte_rate,
        CHANNELS * 2,
        16,
        b"data",
        len(pcm),
    )
    return header + pcm


async def loop_url(assets: AssetStore, mood: str, *, build: bool = True) -> str | None:
    """The URL of this mood's loop, capturing it first if it is not there yet."""
    key = loop_key(mood)
    existing = await assets.url_for(key)
    if existing is not None or not build:
        return existing

    async with _building:
        # Another caller may have built it while this one waited.
        existing = await assets.url_for(key)
        if existing is not None:
            return existing
        return await build_loop(assets, mood)


async def build_loop(assets: AssetStore, mood: str) -> str | None:
    prompt = next((v.prompt for v in MUSIC_MOOD if v.id == mood), mood)
    try:
        pcm = await capture(f"{prompt}. {RULES}", DEFAULT_BPM, LOOP_SECONDS)
    except MusicUnavailable as exc:
        log.warning("could not capture a loop for %s: %s", mood, exc)
        return None

    if len(pcm) < BYTES_PER_SECOND * 4:
        log.warning("capture for %s was too short to loop (%d bytes)", mood, len(pcm))
        return None

    url = await assets.put(loop_key(mood), to_wav(pcm), WAV)
    log.info("captured a %.0fs loop for %s", len(pcm) / BYTES_PER_SECOND, mood)
    return url


async def build_library(assets: AssetStore) -> dict[str, str | None]:
    """Every mood, one after another. This is the one-off cost."""
    return {v.id: await loop_url(assets, v.id) for v in MUSIC_MOOD}
