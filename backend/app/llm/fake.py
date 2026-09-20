"""A model that never calls anything.

This is not the same thing as `LLM_MODE=mock`. Mock replays four recorded
games and never touches the pipeline; `FakeLLM` runs the *real* pipeline -
planning, map generation, scene assembly, the turn engine, the ending - and
only substitutes the model at the very bottom. That makes it the thing to test
against, because a bug in stage sequencing or in draft normalization shows up
here and cannot show up under mock.

It is also usable in a browser (`LLM_MODE=fake`), which is how a live-shaped
game gets walked end to end without spending anything.
"""

import re
from collections.abc import Callable
from random import Random
from typing import TypeVar
from zlib import crc32

from pydantic import BaseModel

from app.llm.base import LLM, GenerationError, Usage
from app.models.game import Language
from app.models.plan import (
    CHOICES_PER_SCENE,
    BeatDraft,
    ChoiceDraft,
    EndingDraft,
    PlannedLocationDraft,
    PlayerBeatDraft,
    SceneDraft,
    ScenesDraft,
    StoryPlanDraft,
)

T = TypeVar("T", bound=BaseModel)

Builder = Callable[["FakeLLM", str, str], BaseModel]

_BUILDERS: dict[type[BaseModel], Builder] = {}

#: A 1x1 transparent PNG. Small enough to keep fixtures readable, and a real
#: enough PNG that the browser and the asset store both accept it.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)

_LANGUAGE = re.compile(r'`language` field to "(pl|en)"')


def register(schema: type[BaseModel]) -> Callable[[Builder], Builder]:
    """Stages add their own builder next to the stage, not in here."""

    def decorate(builder: Builder) -> Builder:
        _BUILDERS[schema] = builder
        return builder

    return decorate


_WORDS = {
    "en": {
        "place": ["Harbour Office", "The Long Shed", "Winter Garden", "Signal Hut", "Back Stair"],
        "thing": [
            "a rusted winch",
            "a folded map",
            "a cold stove",
            "a taped window",
            "a brass key",
        ],
        "verb": ["Ask what happened", "Wait and listen", "Open the cupboard", "Go back outside"],
        "title": "The Long Shed",
        "premise": (
            "You arrive late, and the door is already open. Nobody here expected you, "
            "and nobody says so."
        ),
        "beat": "Something happens at",
        "scene": (
            "The door gives on a room you were not expecting. [POI:{thing}] sits where a "
            "table should be. Someone straightens up and does not look at you."
        ),
        "question": "What do you say?",
        "consequence": "they answer, eventually",
        "note": "This is based on a real event in which people were hurt.",
        "ending_title": "What The Shed Kept",
        "ending_summary": (
            "You went in, and you came back out with less certainty than you started with. "
            "Nothing was resolved, and everything was answered."
        ),
        "did": "You stayed and listened.",
    },
    "pl": {
        "place": [
            "Biuro Portowe",
            "Długa Szopa",
            "Zimowy Ogród",
            "Chatka Sygnałowa",
            "Tylne Schody",
        ],
        "thing": [
            "zardzewiała wyciągarka",
            "złożona mapa",
            "zimny piec",
            "zaklejone okno",
            "mosiężny klucz",
        ],
        "verb": [
            "Zapytaj, co się stało",
            "Poczekaj i posłuchaj",
            "Otwórz szafkę",
            "Wyjdź na zewnątrz",
        ],
        "title": "Długa Szopa",
        "premise": (
            "Przychodzisz za późno, a drzwi są już otwarte. Nikt się ciebie tutaj nie "
            "spodziewał i nikt tego nie mówi."
        ),
        "beat": "Coś się wydarza w miejscu:",
        "scene": (
            "Za drzwiami jest pokój, którego się nie spodziewałeś. [POI:{thing}] stoi tam, "
            "gdzie powinien być stół. Ktoś prostuje się i nie patrzy w twoją stronę."
        ),
        "question": "Co mówisz?",
        "consequence": "w końcu odpowiadają",
        "note": "To jest oparte na prawdziwym wydarzeniu, w którym ucierpieli ludzie.",
        "ending_title": "Co Zatrzymała Szopa",
        "ending_summary": (
            "Wszedłeś tam i wyszedłeś z mniejszą pewnością, niż miałeś na początku. "
            "Nic się nie rozstrzygnęło, a jednak wszystko zostało powiedziane."
        ),
        "did": "Zostałeś i słuchałeś.",
    },
}


class FakeLLM(LLM):
    """Deterministic for a given prompt, so two runs of a test agree."""

    def __init__(self, *, fail_stages: tuple[str, ...] = (), locations: int = 4) -> None:
        self.usage = Usage()
        self.prompts: list[tuple[str, str]] = []
        self.seen_images: list[int] = []
        self._fail = set(fail_stages)
        self._locations = locations

    async def json(
        self,
        stage: str,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 1.0,
    ) -> T:
        self.prompts.append((stage, f"{system or ''}\n{prompt}"))
        if stage in self._fail:
            raise GenerationError(f"stage {stage!r} was told to fail")

        # Costed as if it were real, so the budget path is exercised too.
        self.usage.add_text(stage, len(prompt) // 4, 600)

        builder = _BUILDERS.get(schema)
        if builder is None:
            raise GenerationError(f"FakeLLM has no builder for {schema.__name__}")
        built = builder(self, prompt, system or "")
        assert isinstance(built, schema)
        return built

    async def embed(self, stage: str, texts: list[str]) -> list[list[float]]:
        """Hashed bag-of-words, so similarity actually means something.

        A random vector per input would make every clustering test pass or
        fail by luck. This gives texts that share words a genuinely high
        cosine, which is the property the clustering thresholds are tuned on.
        """
        self.usage.add_embeddings(stage, sum(len(t) for t in texts) // 4)
        return [_bag(text) for text in texts]

    async def vision(
        self,
        stage: str,
        prompt: str,
        images: list[bytes],
        schema: type[T],
        *,
        system: str | None = None,
    ) -> T:
        """Same builders as `json`; the pictures only change the token count."""
        self.seen_images.append(len(images))
        return await self.json(stage, prompt, schema, system=system)

    async def image(self, stage: str, prompt: str, *, timeout: float | None = None) -> bytes | None:
        self.prompts.append((stage, prompt))
        if stage in self._fail:
            return None
        self.usage.add_image(stage)
        # Distinct bytes per prompt, so content-addressed caching is exercised.
        return TINY_PNG + prompt.encode("utf-8")[:16]

    # ── helpers the builders share ──────────────────────────────────────

    def rng(self, prompt: str) -> Random:
        return Random(crc32(prompt.encode("utf-8")))

    def language(self, system: str) -> Language:
        found = _LANGUAGE.search(system)
        return found.group(1) if found else "en"  # type: ignore[return-value]

    def words(self, system: str) -> dict:
        """The fake's vocabulary in whichever language the prompt asked for.

        It matters that this is a real translation rather than English with a
        language tag: `LLM_MODE=fake` is how a Polish game gets walked in a
        browser without spending anything, and the language eval measures
        every player-facing string a run produces.
        """
        return _WORDS[self.language(system)]

    @property
    def location_count(self) -> int:
        return self._locations


#: Dimensions of the fake embedding. Small, and a power of two so the hash
#: spreads evenly across it.
FAKE_DIMENSIONS = 64
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _bag(text: str) -> list[float]:
    vector = [0.0] * FAKE_DIMENSIONS
    for token in _TOKEN.findall(text.lower()):
        vector[crc32(token.encode("utf-8")) % FAKE_DIMENSIONS] += 1.0
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector] if norm else vector


@register(StoryPlanDraft)
def _plan(fake: FakeLLM, prompt: str, system: str) -> StoryPlanDraft:
    rng = fake.rng(prompt)
    words = fake.words(system)
    count = fake.location_count
    locations = [
        PlannedLocationDraft(
            name=words["place"][i % len(words["place"])],
            description=f"{words['thing'][i % len(words['thing'])]}, and someone waiting.",
            # Always English: `visual` is an image prompt, and the language
            # rule carves it out of the story language for that reason.
            visual=f"a narrow room, low winter light, one figure at a table, detail {i}",
            locked=i == count - 1,
        )
        for i in range(count)
    ]
    return StoryPlanDraft(
        language=fake.language(system),
        title=words["title"],
        premise=words["premise"],
        locations=locations,
        beats=[
            BeatDraft(
                title=f"Beat {i + 1}",
                summary=f"{words['beat']} {loc.name}.",
                location_index=i,
            )
            for i, loc in enumerate(locations)
        ],
        open_question_count=1 + (rng.random() > 0.5),
        content_note=words["note"] if "SAFETY:" in system else "",
    )


#: The scene brief numbers its locations from zero and flags the ones that
#: should ask an open question. Read back rather than counted, so a question
#: lands on the location the plan chose rather than on the first few.
_LOCATION_LINE = re.compile(r"^(\d+)\. (.*)$", re.MULTILINE)


@register(ScenesDraft)
def _scenes(fake: FakeLLM, prompt: str, system: str) -> ScenesDraft:
    words = fake.words(system)
    listed = [
        (int(index), "[asks an open question]" in rest)
        for index, rest in _LOCATION_LINE.findall(prompt)
    ] or [(0, False)]

    scenes = []
    for index, asks in listed:
        thing = words["thing"][index % len(words["thing"])]
        scenes.append(
            SceneDraft(
                location_index=index,
                text=words["scene"].format(thing=thing),
                choices=[
                    ChoiceDraft(
                        text=words["verb"][position % len(words["verb"])],
                        consequence=words["consequence"],
                        on_canon=position == 0,
                    )
                    for position in range(CHOICES_PER_SCENE)
                ],
                open_question=words["question"] if asks else "",
            )
        )
    return ScenesDraft(language=fake.language(system), scenes=scenes)


@register(EndingDraft)
def _ending(fake: FakeLLM, prompt: str, system: str) -> EndingDraft:
    words = fake.words(system)
    count = sum(1 for line in prompt.splitlines() if re.match(r"^\d+\. ", line))
    return EndingDraft(
        language=fake.language(system),
        title=words["ending_title"],
        summary=words["ending_summary"],
        player_beats=[
            PlayerBeatDraft(beat_index=i, what_you_did=words["did"], matched=True)
            for i in range(count)
        ],
    )


# Builders for the news stages live in `app.news.fakes`, imported here so
# that importing `FakeLLM` is enough to register everything it can answer.
from app.news import fakes as _news_fakes  # noqa: F401  (side-effecting)

__all__ = ["TINY_PNG", "FakeLLM", "register"]
