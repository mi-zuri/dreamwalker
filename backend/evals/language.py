"""Does the story come out in the language the player asked for - everywhere?

Language is the setting most likely to fail partially rather than completely:
the premise lands in Polish, a choice drifts back to English, the ending is
right and the fallback text beside it is not. So this does not check "is the
output Polish"; it checks every player-facing string a finished run produces,
plus the two places language is deliberately *not* the story's: the interface,
which follows its own setting, and image prompts, which are always English
because the models follow English better and because a Polish prompt is how
Polish words end up painted on a picture.

Offline, the prose comes from `FakeLLM`, so what is being measured is the
plumbing - that the right instruction reaches every stage and the right
language comes back through every field. `--live` measures the model instead.
"""

import re

from app.llm.fake import FakeLLM
from app.models.game import Language
from app.pipeline.prompts import IMAGE_RULE, LANGUAGE_NAME
from evals import fixtures as fx
from evals.harness import Case, Context, check

#: Function words dense enough in ordinary prose that a sentence or two is
#: enough to tell the two apart. Deliberately not a language-id dependency:
#: two languages, both known in advance, is not a modelling problem.
#:
#: Every short word that exists in both languages is left out on purpose -
#: "do", "to", "i", "a", "on", "za". Keeping them cost more than they gave:
#: "What do you do?" scored as Polish on the strength of two "do"s.
_MARKERS: dict[Language, tuple[str, ...]] = {
    "pl": (
        "nie",
        "się",
        "że",
        "jest",
        "czy",
        "jak",
        "ale",
        "tylko",
        "przez",
        "dla",
        "który",
        "która",
        "był",
        "była",
        "są",
        "ich",
        "jej",
        "jego",
        "tym",
        "już",
        "gdzie",
        "kiedy",
        "tam",
        "tutaj",
        "nikt",
        "wszystko",
        "ktoś",
        "swoje",
    ),
    "en": (
        "the",
        "and",
        "you",
        "with",
        "that",
        "this",
        "was",
        "were",
        "they",
        "there",
        "from",
        "have",
        "has",
        "into",
        "your",
        "about",
        "which",
        "they",
        "does",
        "where",
        "when",
        "here",
        "nobody",
        "everything",
        "someone",
        "their",
    ),
}
_POLISH_LETTERS = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def looks_like(text: str, language: Language) -> bool:
    """True when `text` reads as `language` rather than as the other one.

    Short strings - a two-word title, a three-word choice - often contain no
    function word at all. Those are scored as a pass rather than guessed at,
    because a wrong guess would make the number worse than no number.
    """
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return True
    if _POLISH_LETTERS.search(text):
        return language == "pl"
    hits = {code: sum(1 for w in words if w in markers) for code, markers in _MARKERS.items()}
    other: Language = "en" if language == "pl" else "pl"
    if hits[language] == hits[other]:
        return True
    return hits[language] > hits[other]


def _player_facing(opened, state, ending) -> list[tuple[str, str]]:
    """Every string a player reads in one run, with a name for each."""
    items = [
        ("title", ending.title),
        ("summary", ending.summary),
        ("premise", opened.plan.premise),
        ("prologue", opened.script.scenes and opened.state.current_scene.text or ""),
    ]
    for location in opened.plan.locations:
        items.append((f"location-name/{location.id}", location.name))
        scene = opened.script.scenes.get(location.id)
        if scene:
            items.append((f"scene/{location.id}", scene.text))
        for choice in opened.script.choices.get(location.id, []):
            items.append((f"choice/{choice.id}", choice.text))
        question = opened.script.open_questions.get(location.id)
        if question:
            items.append((f"question/{location.id}", question))
    items += [(f"player-beat/{b.beat_id}", b.what_you_did) for b in ending.player]
    items += [(f"style-label/{label.axis}", label.label) for label in ending.style_labels]
    return [(name, text) for name, text in items if text and text.strip()]


async def _one_run(ctx: Context, *, mode: str, story: Language, ui: Language) -> list[Case]:
    llm = ctx.model()
    label = f"{mode}/{story}"
    if ui != story:
        label += f"-ui-{ui}"

    if mode == "news":
        title = "Divers reach the wreck and recover the ship's bell"
        opened = await fx.open_news(llm, fx.make_event(title), story_language=story, ui_language=ui)
    else:
        idea = {
            "pl": "latarnik zastaje lampę już zapaloną",
            "en": "a lighthouse keeper finds the lamp already lit",
        }[story]
        opened = await fx.open_idea(llm, idea=idea, story_language=story, ui_language=ui)

    state, ending = await fx.played_ending(llm, opened, fx.alternate)

    cases = [
        check(f"{label}/plan-echoes-language", opened.plan.language == story, opened.plan.language),
        check(
            f"{label}/state-keeps-both-settings",
            state.story_language == story and state.ui_language == ui,
            f"story {state.story_language}, ui {state.ui_language}",
        ),
    ]

    for name, text in _player_facing(opened, state, ending):
        cases.append(
            check(
                f"{label}/{name}",
                looks_like(text, story),
                f"expected {LANGUAGE_NAME[story]}: {text[:90]!r}",
            )
        )

    # Image prompts are the exception and must stay English, with the no-text
    # rule attached - a Polish prompt is how Polish words get painted on.
    visuals = [loc.visual for loc in opened.plan.locations if loc.visual]
    cases += [
        check(
            f"{label}/visual-is-english/{index}",
            looks_like(visual, "en"),
            f"image prompt is not English: {visual[:90]!r}",
        )
        for index, visual in enumerate(visuals)
    ]

    if isinstance(llm, FakeLLM):
        image_prompts = [text for stage, text in llm.prompts if stage == "image"]
        cases += [
            check(
                f"{label}/image-prompt-forbids-text/{index}",
                IMAGE_RULE in prompt,
                "an image prompt went out without the no-text rule",
            )
            for index, prompt in enumerate(image_prompts)
        ]
        wanted = f'`language` field to "{story}"'
        told = [system for stage, system in llm.prompts if stage in {"plan", "scenes", "ending"}]
        cases.append(
            check(
                f"{label}/every-stage-is-told-the-language",
                bool(told) and all(wanted in text for text in told),
                f"{sum(1 for t in told if wanted in t)} of {len(told)} stages",
            )
        )

    if mode == "news":
        cases.append(
            check(
                f"{label}/source-note-localised",
                looks_like(opened.state.source_note or "", story),
                f"{opened.state.source_note!r}",
            )
        )
    return cases


async def run(ctx: Context) -> list[Case]:
    cases: list[Case] = []
    combinations: list[tuple[str, Language, Language]] = [
        ("idea", "en", "en"),
        ("idea", "pl", "pl"),
        ("news", "en", "en"),
        ("news", "pl", "pl"),
        # The two settings are independent, and the pair most likely to be
        # confused: a Polish interface around an English story.
        ("idea", "en", "pl"),
        ("news", "pl", "en"),
    ]
    # Every combination, every time: this is a fixed matrix rather than a
    # sample, so `--samples` has nothing to vary here.
    for mode, story, ui in combinations:
        cases += await _one_run(ctx, mode=mode, story=story, ui=ui)
    return cases
