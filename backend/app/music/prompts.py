"""What the music is asked to be.

Two inputs: the style card's `music_mood`, which is fixed for the whole run,
and wherever the player currently is, which is not. The prompt is always
English - Lyria is prompted in English regardless of the story's language, and
there is nothing for a language to leak into.

The old TypeScript version derived tempo and texture from the arousal/valence/
self-awareness metrics. Those are gone, and this is what replaced them: the
mood axis sets the register, and the location moves it.
"""

from app.models.game import StyleCard
from app.models.plan import PlannedLocation
from app.pipeline.style_card import music_prompt

#: Lyria accepts 60-200. The game never wants the top of that range.
BPM_FOR_PACING: dict[str, int] = {
    "slow_burn": 62,
    "staccato": 104,
    "escalating": 84,
}
DEFAULT_BPM = 72

#: Said every time, because a vocal line over a scene is unusable.
RULES = "Instrumental only. No vocals, no lyrics, no spoken word."


def bpm_for(style: StyleCard) -> int:
    return BPM_FOR_PACING.get(style.pacing, DEFAULT_BPM)


def opening_prompt(style: StyleCard) -> str:
    return f"{music_prompt(style)}. {RULES}"


def location_prompt(style: StyleCard, location: PlannedLocation | None) -> str:
    """The mood, coloured by where the player is standing.

    The location's `visual` is reused rather than its `description`: it is
    already English, already concrete, and already free of story-language
    prose.
    """
    if location is None:
        return opening_prompt(style)
    return f"{music_prompt(style)}. The setting: {location.visual.strip()}. {RULES}"
