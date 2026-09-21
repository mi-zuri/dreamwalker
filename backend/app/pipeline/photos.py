"""Putting real press photographs where they belong.

Every photo already carries a caption, written during the ingest safety check
by a model that was looking at the picture. Matching therefore does not need
to look at the pictures again: it is a text call over captions and location
descriptions, which costs a few hundred tokens instead of re-uploading four
images, and uses exactly the same information.

Every photo that lands on a location saves a generated one - which matters
more than the money, because generated images are capped at two a minute and
press photos are not capped at all.
"""

import logging

from pydantic import BaseModel, Field

from app.llm.base import LLM
from app.models.game import ImageCredit
from app.models.plan import StoryPlan
from app.news.models import Photo
from app.pipeline.images import SourcedImage

log = logging.getLogger(__name__)

STAGE = "photo-match"


class Match(BaseModel):
    photo_index: int
    #: Index into the plan's locations, or -1 for "this fits nowhere".
    location_index: int = -1
    confidence: float = 0.0


class Matches(BaseModel):
    matches: list[Match] = Field(default_factory=list)


#: Below this a photo is left unused rather than put somewhere it does not fit.
#: A wrong photograph of a real event is worse than a generated picture.
MIN_CONFIDENCE = 0.5


INSTRUCTIONS = """You are placing real press photographs of a news event into the \
locations of a short story based on that event.

For each photograph, give the index of the location it actually depicts, and how \
confident you are from 0.0 to 1.0. Use -1 when a photograph does not show any of the \
listed places - that is the normal answer for a portrait, a logo, a studio shot or a \
generic file image, and it is better than a wrong placement.

Match on what is physically in the picture against what the location says is there. Do \
not match on mood, subject matter or the fact that both relate to the same event. Each \
location takes at most one photograph."""


def _brief(plan: StoryPlan, photos: list[Photo]) -> str:
    lines = ["LOCATIONS:"]
    for index, location in enumerate(plan.locations):
        lines.append(f"{index}. {location.name} - {location.description} ({location.visual})")
    lines += ["", "PHOTOGRAPHS:"]
    for index, photo in enumerate(photos):
        lines.append(f"{index}. {photo.caption}")
    return "\n".join(lines)


async def match_photos(llm: LLM, plan: StoryPlan, photos: list[Photo]) -> dict[str, SourcedImage]:
    """`location_id -> SourcedImage` for every location a photo genuinely fits."""
    usable = [p for p in photos if p.safe and p.stored_url and p.caption]
    if not usable or not plan.locations:
        return {}

    try:
        result = await llm.json(STAGE, _brief(plan, usable), Matches, system=INSTRUCTIONS)
    except Exception:
        log.exception("photo matching failed; every location will be generated")
        return {}

    placed: dict[str, SourcedImage] = {}
    taken: set[int] = set()
    for match in sorted(result.matches, key=lambda m: -m.confidence):
        if match.confidence < MIN_CONFIDENCE:
            continue
        if not (0 <= match.location_index < len(plan.locations)):
            continue
        if match.location_index in taken or not (0 <= match.photo_index < len(usable)):
            continue
        photo = usable[match.photo_index]
        taken.add(match.location_index)
        placed[plan.locations[match.location_index].id] = SourcedImage(
            photo.stored_url,
            ImageCredit(source_url=photo.source_url, credit=photo.credit),
        )

    log.info("placed %d of %d press photos", len(placed), len(usable))
    return placed


def best_for_opening(photos: list[Photo]) -> SourcedImage | None:
    """A press photo for the opening screen, so News mode opens without waiting.

    The opening image is the one generated picture on the critical path. In
    News mode there is usually a real photograph to use instead, which is both
    free and immediate.
    """
    for photo in photos:
        if photo.safe and photo.stored_url:
            return SourcedImage(
                photo.stored_url,
                ImageCredit(source_url=photo.source_url, credit=photo.credit),
            )
    return None
