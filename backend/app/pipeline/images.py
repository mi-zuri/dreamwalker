"""Image sourcing.

One image per location, built from the location's own `visual` line plus the
style card's visual axis, and never from the scene prose - prose in the story
language would drag the model toward rendering that language as text on the
picture, which is exactly what `IMAGE_RULE` exists to prevent.

Nothing here is allowed to be fatal. A location without an image renders
without one, and the game is unaffected.
"""

import logging

from app.llm.base import LLM
from app.models.game import ImageCredit, StyleCard
from app.models.plan import PlannedLocation
from app.pipeline.prompts import IMAGE_RULE
from app.pipeline.style_card import visual_prompt
from app.storage.assets import AssetStore, asset_key

log = logging.getLogger(__name__)

STAGE = "images"


class SourcedImage:
    __slots__ = ("credit", "url")

    def __init__(self, url: str | None, credit: ImageCredit | None = None) -> None:
        self.url = url
        self.credit = credit


def prompt_for(location: PlannedLocation, style: StyleCard) -> str:
    """Always English, style first so it frames the subject rather than trailing it."""
    return f"{visual_prompt(style)}. {location.visual.strip()}. {IMAGE_RULE}"


async def generate_image(
    llm: LLM, assets: AssetStore, prompt: str, *, timeout: float | None = None
) -> str | None:
    """Generate, or return the URL of an identical earlier image.

    `timeout` bounds the wait for image quota. Only the opening image passes
    one; everything else is happy to queue.
    """
    key = asset_key(prompt)
    cached = await assets.url_for(key)
    if cached is not None:
        log.info("image cache hit for %s", key)
        return cached

    data = await llm.image(STAGE, prompt, timeout=timeout)
    if data is None:
        return None
    return await assets.put(key, data)


async def image_for(
    llm: LLM, assets: AssetStore, location: PlannedLocation, style: StyleCard
) -> SourcedImage:
    try:
        return SourcedImage(await generate_image(llm, assets, prompt_for(location, style)))
    except Exception as exc:  # noqa: BLE001 - a missing picture must not end a game
        log.warning("image for %s failed: %s", location.id, exc)
        return SourcedImage(None)
