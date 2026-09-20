"""The planning stage: one model call that decides what the game *is*.

It runs before anything expensive, and everything downstream is derived from
its output - the map's destinations, the scenes, the images, the ending. Both
modes call `make_plan`; they differ only in the brief they hand it.

The model returns a positional draft and we assign the ids, so a location can
never be referenced by a name the model made up two fields later.
"""

from string import ascii_uppercase

from app.llm.base import LLM, GenerationError
from app.models.game import Language, SafetyClass, StyleCard
from app.models.plan import (
    MAX_LOCATIONS,
    MAX_OPEN_QUESTIONS,
    MIN_LOCATIONS,
    Beat,
    PlannedLocation,
    StoryPlan,
    StoryPlanDraft,
)
from app.pipeline.prompts import (
    LANGUAGE_NAME,
    SAFE_MODE_RULE,
    language_rule,
    style_block,
)
from app.pipeline.style_card import style_prompt

STAGE = "plan"

#: At most this many locations are put behind a door. More than two locks in a
#: five-room game means the player spends the whole run walking back.
MAX_LOCKED = 2


def _instructions(language: Language, safety_class: SafetyClass) -> str:
    safe_mode = safety_class == "safe_mode"
    safe = f"\n\nSAFETY:\n{SAFE_MODE_RULE}" if safe_mode else ""
    # Naming the language outright rather than saying "the story language":
    # measured, the model writes the premise in Polish and this field in
    # English when it is only told the rule once, in the abstract.
    note = (
        f"one sentence written in {LANGUAGE_NAME[language]}, naming plainly what the "
        f"player is about to encounter. It is shown before the game starts, with a way "
        f"to decline. It must be in {LANGUAGE_NAME[language]}, like everything else "
        f"the player reads."
        if safe_mode
        else "an empty string. This story needs no content warning."
    )
    return f"""You plan short interactive stories. A player finishes one in 2 to 10 minutes: \
they walk a small map, arrive at each place once, read a short scene and pick one of \
three actions.

{language_rule(language)}

Return exactly:
- `title`: 2 to 5 words. No subtitle, no colon.
- `premise`: 2 to 3 sentences setting up the situation the player is walking into.
- `locations`: {MIN_LOCATIONS} to {MAX_LOCATIONS} distinct places, ordered as the story \
wants them visited. Use {MAX_LOCATIONS} unless the idea is genuinely a single small \
scene - a player spends roughly a minute in each place, and the run should fill several. Each has a `name` (2 to 4 words), a `description` (1 to 2 sentences \
of what is physically there and who is in it) and a `visual`. Set `locked` on at most \
{MAX_LOCKED} of them - never the first - to mean the player cannot get in until they \
have finished somewhere earlier. Lock a place only when the story gives a reason.
- `visual`: an English image prompt for the place. Concrete nouns, light, weather, \
materials, one or two figures at most. No style words - the style is added separately. \
Never any text, letters or signage.
- `beats`: one per location, in the order they should happen, each with the \
`location_index` it belongs to. A beat is what happens there, in one or two sentences.
- `open_question_count`: 1, or 2 when the story has two moments worth the player \
writing a sentence of their own.
- `content_note`: {note}{safe}"""


async def make_plan(
    llm: LLM,
    *,
    brief: str,
    style: StyleCard,
    language: Language,
    safety_class: SafetyClass = "allowed",
    content_note: str = "",
) -> StoryPlan:
    draft = await llm.json(
        STAGE,
        f"{style_block(style_prompt(style))}\n\n{brief}",
        StoryPlanDraft,
        system=_instructions(language, safety_class),
    )
    # The note that reaches the player is the one written in their language;
    # the English one from ingest is the fallback if the stage skipped it.
    if safety_class == "safe_mode":
        content_note = draft.content_note.strip() or content_note
    return normalize_plan(draft, language=language, content_note=content_note)


def normalize_plan(
    draft: StoryPlanDraft, *, language: Language, content_note: str = ""
) -> StoryPlan:
    """Turn a positional draft into ids, within the bounds the game can render.

    The model is asked for a legal plan and mostly gives one; this is what
    happens when it does not, and it never fails - a plan that is slightly
    smaller than asked for is a playable game, and a rejected plan is not.
    """
    drafted = draft.locations[:MAX_LOCATIONS]
    if not drafted:
        raise GenerationError("the plan came back with no locations")

    locations: list[PlannedLocation] = []
    locked_budget = MAX_LOCKED
    for index, item in enumerate(drafted):
        # The first place can never be locked: the player starts outside it.
        locked = index > 0 and item.locked and locked_budget > 0
        if locked:
            locked_budget -= 1
        locations.append(
            PlannedLocation(
                id=f"loc-{ascii_uppercase[index].lower()}",
                name=item.name.strip() or f"Location {index + 1}",
                description=item.description.strip(),
                visual=item.visual.strip(),
                # Opened by finishing the place before it, which is the only
                # ordering the player can discover without being told.
                locked_by=locations[index - 1].id if locked else "",
            )
        )

    beats: list[Beat] = []
    for order, item in enumerate(draft.beats):
        index = item.location_index
        if not 0 <= index < len(locations):
            continue
        beats.append(
            Beat(
                id=f"beat-{order + 1}",
                order=order,
                title=item.title.strip(),
                summary=item.summary.strip(),
                location_ref=locations[index].id,
            )
        )

    return StoryPlan(
        title=draft.title.strip(),
        premise=draft.premise.strip(),
        language=language,
        locations=locations,
        beats=beats,
        open_question_at=_pick_question_locations(locations, draft.open_question_count),
        content_note=content_note,
    )


def _pick_question_locations(locations: list[PlannedLocation], count: int) -> list[str]:
    """Spread the open questions out rather than stacking them at the start."""
    wanted = max(0, min(count, MAX_OPEN_QUESTIONS, len(locations)))
    if wanted == 0:
        return []
    if wanted == 1:
        return [locations[len(locations) // 2].id]
    return [locations[1].id, locations[-1].id] if len(locations) > 2 else [locations[0].id]
