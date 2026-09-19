"""Phase 0 gate: prove every model in the plan is reachable, and measure what it costs.

Run:  uv run python scripts/verify_models.py [--skip-music]

Text and images go through Vertex AI (ADC). Lyria RealTime is Gemini-API-only and
needs GEMINI_API_KEY. Nothing here is imported by the app; delete after Phase 0.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from google import genai
from google.genai import types

PROJECT = os.environ.get("GCP_PROJECT", "")
LOCATION = os.environ.get("GCP_LOCATION", "europe-central2")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gemini-3.5-flash-lite")
TEXT_FALLBACK = "gemini-3.1-flash-lite"
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-lite-image")
MUSIC_MODEL = "models/lyria-realtime-exp"

# Published rates, USD per 1M tokens (ai.google.dev/gemini-api/docs/pricing, 2026-09-19).
TEXT_IN, TEXT_OUT = 0.30, 2.50
IMG_IN, IMG_OUT, IMG_TOKENS = 0.25, 1.50, 30.00

OK, FAIL, WARN = "  ok  ", " FAIL ", " warn "


def vertex() -> genai.Client:
    return genai.Client(vertexai=True, project=PROJECT, location=LOCATION)


def check_text() -> bool:
    """Structured JSON output, the mode every pipeline stage depends on."""
    schema = {
        "type": "OBJECT",
        "properties": {"title": {"type": "STRING"}, "beats": {"type": "INTEGER"}},
        "required": ["title", "beats"],
    }
    for model in (TEXT_MODEL, TEXT_FALLBACK):
        try:
            t0 = time.monotonic()
            r = vertex().models.generate_content(
                model=model,
                contents="Wymysl tytul krotkiej historii o ladowaniu rakiety i liczbe scen.",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=schema
                ),
            )
            dt = time.monotonic() - t0
            u = r.usage_metadata
            cost = (u.prompt_token_count * TEXT_IN + u.candidates_token_count * TEXT_OUT) / 1e6
            print(f"[{OK}] text {model}")
            print(f"        {u.prompt_token_count} in / {u.candidates_token_count} out"
                  f" | {dt:.2f}s | ${cost:.6f}")
            print(f"        json: {r.text.strip()[:90]}")
            if model != TEXT_MODEL:
                print(f"        NOTE: {TEXT_MODEL} unavailable; plan's fallback is in use.")
            return True
        except Exception as e:  # noqa: BLE001 - this is a diagnostic script
            print(f"[{WARN}] text {model}: {type(e).__name__}: {str(e)[:160]}")
    print(f"[{FAIL}] no text model reachable on Vertex AI")
    return False


def check_image() -> bool:
    try:
        t0 = time.monotonic()
        r = vertex().models.generate_content(
            model=IMAGE_MODEL,
            contents=(
                "Pixel-art interior of an empty parliament chamber at night, muted palette. "
                "No text, letters, numbers, signage or watermarks anywhere in the image."
            ),
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        dt = time.monotonic() - t0
        blob = next(
            (p.inline_data.data for p in r.candidates[0].content.parts if p.inline_data), None
        )
        if not blob:
            print(f"[{FAIL}] image {IMAGE_MODEL}: responded without image data")
            return False
        u = r.usage_metadata
        img_tok = getattr(u, "candidates_token_count", 0) or 0
        cost = (u.prompt_token_count * IMG_IN + img_tok * IMG_TOKENS) / 1e6
        print(f"[{OK}] image {IMAGE_MODEL}")
        print(f"        {len(blob) / 1024:.0f}KB PNG | {dt:.2f}s | ~${cost:.4f}/image")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[{FAIL}] image {IMAGE_MODEL}: {type(e).__name__}: {str(e)[:160]}")
        return False


async def check_music(seconds: int = 20) -> bool:
    """Lyria has no published rate, so measure throughput and read billing afterwards."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print(f"[{WARN}] music: GEMINI_API_KEY unset, skipping")
        return False
    try:
        client = genai.Client(api_key=key, http_options={"api_version": "v1alpha"})
        total = 0
        t0 = time.monotonic()
        async with client.aio.live.music.connect(model=MUSIC_MODEL) as session:
            await session.set_weighted_prompts(
                prompts=[types.WeightedPrompt(text="sparse tense drone, low strings", weight=1.0)]
            )
            await session.set_music_generation_config(
                config=types.LiveMusicGenerationConfig(bpm=72, guidance=4.0)
            )
            await session.play()

            async def drain() -> None:
                nonlocal total
                async for msg in session.receive():
                    for chunk in (msg.server_content.audio_chunks or []):
                        total += len(chunk.data)

            try:
                await asyncio.wait_for(drain(), timeout=seconds)
            except TimeoutError:
                pass
        wall = time.monotonic() - t0
        audio_s = total / (48000 * 2 * 2)  # 48kHz, stereo, 16-bit
        print(f"[{OK}] music {MUSIC_MODEL}")
        print(f"        {total / 1024:.0f}KB = {audio_s:.1f}s audio in {wall:.1f}s wall")
        print(f"        a 10-min game streams ~{600 * 48000 * 2 * 2 / 1e6:.0f}MB")
        print("        COST: unpublished. Read actual spend for this run in the "
              "AI Studio / GCP billing console, then fill it into the plan's cost model.")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[{FAIL}] music {MUSIC_MODEL}: {type(e).__name__}: {str(e)[:160]}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-music", action="store_true")
    ap.add_argument("--music-seconds", type=int, default=20)
    args = ap.parse_args()

    if not PROJECT:
        print(f"[{FAIL}] GCP_PROJECT unset - Vertex AI checks cannot run")
        return 2
    print(f"project={PROJECT} location={LOCATION}\n")

    results = [("text", check_text()), ("image", check_image())]
    if not args.skip_music:
        results.append(("music", asyncio.run(check_music(args.music_seconds))))

    print("\n" + "  ".join(f"{n}={'PASS' if ok else 'FAIL'}" for n, ok in results))
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
