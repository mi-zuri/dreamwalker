"""Building the fallback loop library, and checking that live music works.

    uv run python -m app.music.cli check
    uv run python -m app.music.cli build-loops
    uv run python -m app.music.cli build-loops --mood drone

`check` opens a real Lyria session for a few seconds and reports how much
audio arrived. It is the only way to find out whether live music is working,
because Lyria RealTime publishes no price and no quota.
"""

import argparse
import asyncio
import logging
import time

from app.music.loops import LOOP_SECONDS, build_loop, loop_url
from app.music.lyria import BYTES_PER_SECOND, LyriaStream, MusicUnavailable
from app.music.prompts import DEFAULT_BPM, RULES
from app.pipeline.style_catalog import MUSIC_MOOD
from app.settings import settings
from app.storage.assets import get_assets


async def _check(_: str | None) -> None:
    stream = LyriaStream(f"a single sustained drone, almost no movement. {RULES}", DEFAULT_BPM)
    started = time.monotonic()
    try:
        await stream.open()
    except MusicUnavailable as exc:
        print(f"live music unavailable: {exc}")
        return

    received = 0
    try:
        async with asyncio.timeout(12):
            async for data in stream.chunks():
                received += len(data)
                if received >= BYTES_PER_SECOND * 5:
                    break
    except TimeoutError:
        pass
    finally:
        await stream.close()

    wall = time.monotonic() - started
    print(f"model:  {settings.music_model}")
    print(f"opened and streamed {received} bytes in {wall:.1f}s")
    print(f"      = {received / BYTES_PER_SECOND:.1f}s of 48kHz stereo 16-bit audio")


async def _build(mood: str | None) -> None:
    assets = get_assets()
    moods = [mood] if mood else [v.id for v in MUSIC_MOOD]
    print(f"capturing {len(moods)} loop(s) of {LOOP_SECONDS:.0f}s into {type(assets).__name__}")
    for name in moods:
        url = await build_loop(assets, name) if mood else await loop_url(assets, name)
        print(f"  {name:10s} {url or 'FAILED'}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Dreamwalker music")
    parser.add_argument("command", choices=["check", "build-loops"])
    parser.add_argument("--mood", choices=[v.id for v in MUSIC_MOOD])
    args = parser.parse_args()

    runner = {"check": _check, "build-loops": _build}[args.command]
    asyncio.run(runner(args.mood))


if __name__ == "__main__":
    main()
