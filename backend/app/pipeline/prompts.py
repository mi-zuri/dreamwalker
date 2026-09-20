"""Prompt fragments shared by every text stage.

The rules here are the ones that must not vary between stages, because a
player notices immediately when they do: which language the prose is in, what
the highlight markers mean, and the fact that no image may ever contain text.
"""

from app.models.game import Language

LANGUAGE_NAME: dict[Language, str] = {"pl": "Polish", "en": "English"}


def language_rule(language: Language) -> str:
    """Said the same way in every stage, and echoed back in the JSON.

    The instruction is in English even when the output is Polish: the model
    follows an English instruction more reliably, and mixing the two inside
    one prompt is what makes output drift back to English mid-paragraph.
    """
    name = LANGUAGE_NAME[language]
    return (
        f"Write every piece of player-facing text in {name}, including names of "
        f"places and people where {name} would naturally translate them. Do not "
        f'mix languages. Set the `language` field to "{language}".\n'
        f"The one exception is any field named `visual`, which is an image prompt "
        f"and must always be written in English."
    )


#: Parsed by `web/src/components/HighlightedText.tsx`, which colours them.
MARKER_RULE = (
    "Mark up to three phrases per scene with highlight markers, using the exact "
    "syntax `[POI:the rusted winch]`, `[LOC:the north pier]` or `[KEY:a brass key]`. "
    "POI is a thing worth looking at, LOC is a place, KEY is something the player "
    "could take or use. The brackets are shown to the player as coloured text, so "
    "the phrase inside must read naturally in the sentence. Never nest markers."
)

#: Every image prompt ends with this. Text on an image is the one failure mode
#: that would break the game's language setting in a way we cannot fix later.
IMAGE_RULE = (
    "No text, no letters, no numbers, no words, no signage, no captions, no "
    "watermarks and no logos anywhere in the image. No frame or border. "
    "Landscape orientation, 4:3."
)

SAFE_MODE_RULE = (
    "This is based on a real event in which people were hurt or killed. "
    "Do not describe injuries, bodies or dying. Do not name any private "
    "individual - refer to people by role. Keep the register respectful and "
    "factual. The player is never rewarded for harm, and a death toll is never "
    "framed as a score. Do not invent casualties or blame."
)


def style_block(style_text: str) -> str:
    return f"STYLE - obey every line of this:\n{style_text}"
