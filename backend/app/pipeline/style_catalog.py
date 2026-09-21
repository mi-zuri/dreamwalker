"""The style-card catalog.

Every axis value is a language-neutral id. The sampler only ever moves ids
around; natural language lives here, in one place, as a display label per
UI language plus a single English `prompt` fragment that is spliced into the
generation prompts.

That split is what makes style cards work identically in Polish and English:
the prompt fragment describes *how to write*, and a separate instruction says
*which language to write in*. Translating the fragments would make the two
languages drift apart for no benefit.

`docs/style-cards.md` is generated from this module - see `dump_catalog()`.
"""

from typing import Literal, NamedTuple

Axis = Literal[
    "genre",
    "narrative_voice",
    "tone",
    "protagonist_role",
    "visual_style",
    "music_mood",
    "pacing",
]

#: Axis order is fixed: it is the order the card is rendered in and the order
#: the anti-repetition check walks, so it must not depend on dict iteration.
AXES: tuple[Axis, ...] = (
    "genre",
    "narrative_voice",
    "tone",
    "protagonist_role",
    "visual_style",
    "music_mood",
    "pacing",
)


class Value(NamedTuple):
    id: str
    pl: str
    en: str
    #: English guidance fragment, spliced into the relevant stage prompt.
    prompt: str
    #: Excluded when the event is played in safe mode.
    safe: bool = True


def _v(id: str, pl: str, en: str, prompt: str, safe: bool = True) -> Value:
    return Value(id, pl, en, prompt, safe)


GENRE: tuple[Value, ...] = (
    _v(
        "noir",
        "noir",
        "noir",
        "hard-boiled noir: short sentences, moral fog, rain and sodium light",
    ),
    _v(
        "folk_tale",
        "baśń",
        "folk tale",
        "an oral folk tale: repetition, omens, plain words holding strange things",
    ),
    _v(
        "procedural",
        "proceduralny",
        "procedural",
        "a procedural: competence, jargon used correctly, process as tension",
    ),
    _v(
        "absurdist",
        "absurd",
        "absurdist",
        "absurdist: deadpan impossible logic followed rigorously",
        safe=False,
    ),
    _v(
        "epic",
        "epicki",
        "epic",
        "epic register: scale, weather, consequence beyond the protagonist",
    ),
    _v(
        "documentary",
        "dokument",
        "documentary",
        "documentary realism: verified detail, restraint, no authorial flourish",
    ),
    _v(
        "pastoral",
        "pastoralny",
        "pastoral",
        "pastoral: landscape as a character, slow attention to ordinary work",
    ),
    _v(
        "gothic",
        "gotycki",
        "gothic",
        "gothic: architecture that watches, inheritance, dread under politeness",
    ),
)

NARRATIVE_VOICE: tuple[Value, ...] = (
    _v(
        "second_present",
        "druga osoba, teraz",
        "second person, present",
        "second person present tense ('you walk')",
    ),
    _v(
        "first_past",
        "pierwsza osoba, przeszła",
        "first person, past",
        "first person past tense ('I walked')",
    ),
    _v(
        "third_close",
        "trzecia osoba, bliska",
        "third person, close",
        "close third person, fixed to the protagonist's senses",
    ),
    _v("chorus", "chór", "chorus", "a collective 'we' that speaks for the people present"),
)

TONE: tuple[Value, ...] = (
    _v("dry", "oschły", "dry", "dry and unsentimental; let facts do the work"),
    _v(
        "lyrical",
        "liryczny",
        "lyrical",
        "lyrical; image-led sentences, but never ornate for its own sake",
    ),
    _v("tense", "napięty", "tense", "tense; short clauses, withheld information, physical detail"),
    _v("warm", "ciepły", "warm", "warm; attentive to small kindnesses and to what people carry"),
    _v(
        "deadpan",
        "beznamiętny",
        "deadpan",
        "deadpan; report the extraordinary in the register of a timetable",
        safe=False,
    ),
    _v(
        "reverent",
        "pełen szacunku",
        "reverent",
        "reverent; measured, unhurried, conscious of what is at stake",
    ),
)

PROTAGONIST_ROLE: tuple[Value, ...] = (
    _v("participant", "uczestnik", "participant", "the protagonist is caught up in this directly"),
    _v(
        "witness",
        "świadek",
        "witness",
        "the protagonist watches and records, and mostly cannot intervene",
    ),
    _v("rescuer", "ratownik", "rescuer", "the protagonist's job is to get people out"),
    _v(
        "official",
        "urzędnik",
        "official",
        "the protagonist carries an official responsibility and its constraints",
    ),
    _v(
        "journalist",
        "dziennikarz",
        "journalist",
        "the protagonist is reporting, and must decide what to publish",
    ),
    _v(
        "outsider",
        "obcy",
        "outsider",
        "the protagonist does not belong here and reads everything slightly wrong",
    ),
    _v(
        "volunteer",
        "wolontariusz",
        "volunteer",
        "the protagonist turned up to help without being asked to",
    ),
)

#: Roles that stay plausible and decent when the underlying event is a tragedy.
SAFE_ROLES: frozenset[str] = frozenset(
    {"rescuer", "witness", "official", "journalist", "volunteer"}
)

VISUAL_STYLE: tuple[Value, ...] = (
    _v(
        "pixel",
        "pixel art",
        "pixel art",
        "low-resolution pixel art, limited palette, chunky dithering",
        safe=False,
    ),
    _v(
        "ink_wash",
        "tusz",
        "ink wash",
        "monochrome ink wash painting, wet edges, large areas of empty paper",
    ),
    _v(
        "grainy_photo",
        "ziarnista fotografia",
        "grainy photo",
        "grainy 35mm photograph, available light, slight motion blur",
    ),
    _v(
        "blueprint",
        "rysunek techniczny",
        "blueprint",
        "cyanotype blueprint: white line on deep blue, annotated",
    ),
    _v("woodcut", "drzeworyt", "woodcut", "high-contrast woodcut print, carved lines, no midtones"),
    _v(
        "oil_sketch",
        "szkic olejny",
        "oil sketch",
        "loose oil sketch on toned ground, visible brushwork",
    ),
    _v(
        "risograph",
        "riso",
        "risograph",
        "two-colour risograph print, misregistered layers, paper texture",
    ),
)

MUSIC_MOOD: tuple[Value, ...] = (
    _v("drone", "dron", "drone", "a single sustained drone, almost no movement"),
    _v("pulse", "puls", "pulse", "a slow repeating pulse, minimal and mechanical"),
    _v("elegy", "elegia", "elegy", "an elegy: strings, falling intervals, space between phrases"),
    _v("march", "marsz", "march", "a restrained march, low percussion, steady tread"),
    _v("shimmer", "migotanie", "shimmer", "high shimmering texture, bells and bowed metal"),
    _v("static", "szum", "static", "filtered static and room tone, barely musical"),
)

PACING: tuple[Value, ...] = (
    _v("slow_burn", "powolny", "slow burn", "slow burn: let scenes breathe, escalate late"),
    _v("staccato", "urywany", "staccato", "staccato: quick cuts, each scene one hard beat"),
    _v(
        "escalating",
        "narastający",
        "escalating",
        "escalating: each scene raises the stakes over the last",
    ),
)

CATALOG: dict[Axis, tuple[Value, ...]] = {
    "genre": GENRE,
    "narrative_voice": NARRATIVE_VOICE,
    "tone": TONE,
    "protagonist_role": PROTAGONIST_ROLE,
    "visual_style": VISUAL_STYLE,
    "music_mood": MUSIC_MOOD,
    "pacing": PACING,
}

_BY_ID: dict[Axis, dict[str, Value]] = {
    axis: {v.id: v for v in values} for axis, values in CATALOG.items()
}


def value(axis: Axis, value_id: str) -> Value | None:
    return _BY_ID[axis].get(value_id)


def label(axis: Axis, value_id: str, language: str) -> str:
    """Display label, falling back to the raw id for values no longer in the catalog."""
    found = value(axis, value_id)
    if found is None:
        return value_id.replace("_", " ")
    return found.pl if language == "pl" else found.en


def fragment(axis: Axis, value_id: str) -> str:
    found = value(axis, value_id)
    return found.prompt if found is not None else value_id.replace("_", " ")


def dump_catalog() -> str:
    """The Markdown table behind `docs/style-cards.md`."""
    lines = ["# Style cards", "", "Generated from `app/pipeline/style_catalog.py`.", ""]
    for axis in AXES:
        lines += [
            f"## `{axis}`",
            "",
            "| id | pl | en | prompt fragment | safe mode |",
            "|---|---|---|---|---|",
        ]
        for v in CATALOG[axis]:
            lines.append(
                f"| `{v.id}` | {v.pl} | {v.en} | {v.prompt} | {'yes' if v.safe else 'no'} |"
            )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":  # `make docs` regenerates the page from here
    import sys

    # `write`, not `print`: the table already ends in a newline and a second
    # one would put `make docs` permanently one line away from the committed
    # page.
    sys.stdout.write(dump_catalog())
