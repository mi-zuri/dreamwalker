"""How `FakeLLM` answers the news stages.

Kept beside the stages rather than inside the fake, so that adding a stage
means adding its builder next to its prompt instead of editing a file that
knows about everything.

The scoring builder is the one that matters. It reads keywords out of the
brief it was given and classifies accordingly, which is what lets the safety
eval cases be asserted in CI without a model: a fixture that says "earthquake"
comes back `safe_mode`, one that says "missing girl" comes back `blocked`, and
the assertion is about the pipeline honouring the classification rather than
about the model producing it.
"""

import re

from app.llm.fake import FakeLLM, register
from app.news.enrich import (
    CanonBeatDraft,
    DossierDraft,
    FactDraft,
    PersonDraft,
    PhotoCheck,
    PhotoVerdict,
)
from app.news.score import EventScoreDraft, ScoringDraft

#: Substrings that force a classification, checked in this order.
BLOCKED = (
    "missing",
    "zaginio",
    "divorce",
    "rozwód",
    "child",
    "dziecko",
    "abuse",
    "grooming",
)
SAFE_MODE = (
    "earthquake",
    "trzęsienie",
    "attack",
    "zamach",
    "terror",
    "crash",
    "katastrofa",
    "killed",
    "zginęł",
    "fire",
    "pożar",
    "flood",
    "powódź",
    "war",
    "wojn",
)

_NUMBERED = re.compile(r"^(\d+)\.\s", re.MULTILINE)


def classify(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    if any(word in lowered for word in BLOCKED):
        return "blocked", []
    if any(word in lowered for word in SAFE_MODE):
        return "safe_mode", ["rescuer", "witness", "official"]
    return "allowed", ["participant", "witness", "journalist"]


@register(ScoringDraft)
def _scores(fake: FakeLLM, prompt: str, system: str) -> ScoringDraft:
    entries = []
    blocks = _NUMBERED.split(prompt)
    # `split` yields ["", "0", "body", "1", "body", ...].
    for index, body in zip(blocks[1::2], blocks[2::2], strict=False):
        safety, roles = classify(body)
        entries.append(
            EventScoreDraft(
                index=int(index),
                interest=0.7,
                playability=0.2 if safety == "blocked" else 0.8,
                safety_class=safety,
                content_note=(
                    "This is based on a real event in which people were hurt."
                    if safety == "safe_mode"
                    else ""
                ),
                roles=roles,
                reason="fake classification",
            )
        )
    return ScoringDraft(events=entries)


@register(DossierDraft)
def _dossier(fake: FakeLLM, prompt: str, system: str) -> DossierDraft:

    return DossierDraft(
        what="Something happened, and it was reported by several outlets.",
        where="A named town, on a named street.",
        when="Yesterday, in the afternoon.",
        who=[
            PersonDraft(name="A Minister", role="the minister", public_figure=True),
            PersonDraft(name="Jan Kowalski", role="a neighbour", public_figure=False),
        ],
        timeline=[
            FactDraft(text="First the thing began.", certainty="high"),
            FactDraft(text="Then the response arrived.", certainty="high"),
            FactDraft(text="By evening it was over.", certainty="medium"),
        ],
        uncertain=[FactDraft(text="One outlet reported a second cause.", certainty="low")],
        beats=[
            CanonBeatDraft(title=f"Beat {i + 1}", summary="What happened next.", place=place)
            for i, place in enumerate(["The Square", "The Depot", "The Clinic", "The Bridge"])
        ],
    )


@register(PhotoCheck)
def _photos(fake: FakeLLM, prompt: str, system: str) -> PhotoCheck:
    count = int(match.group(1)) if (match := re.search(r"these (\d+)", prompt)) else 1
    return PhotoCheck(
        photos=[
            PhotoVerdict(index=i, safe=True, caption=f"a wide shot of a place, number {i}")
            for i in range(count)
        ]
    )
