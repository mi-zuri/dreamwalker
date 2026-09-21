"""The story plan: the one intermediate representation both modes produce.

Idea mode derives it from the player's sentence; News mode derives it from a
dossier. Everything after that point - map, scenes, images, turn engine,
ending - is written against this, and so has no idea which mode it is serving.

Two layers live here on purpose. The `*Draft` models are what a model is asked
to return: flat, id-free, and indexed by position, because a model that has to
invent `loc-c` will eventually invent `loc-q`. The domain models are what the
pipeline works with, and ids are assigned by us when a draft is normalized.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.game import Language

Certainty = Literal["high", "medium", "low"]

#: Hard bounds on plan size. The lower bound keeps a game from being one room;
#: the upper bound is what the 2-10 minute budget and the map letters allow.
MIN_LOCATIONS = 3
MAX_LOCATIONS = 5
MAX_OPEN_QUESTIONS = 2
CHOICES_PER_SCENE = 3


class PlannedLocation(BaseModel):
    id: str
    name: str
    description: str
    #: Always English - it goes straight into an image prompt.
    visual: str
    #: Location that must be resolved before this one opens; empty when free.
    locked_by: str = ""


class Beat(BaseModel):
    """One step of what happens - canon in News mode, intent in Idea mode."""

    id: str
    order: int
    title: str
    summary: str
    location_ref: str
    certainty: Certainty = "high"
    sources: list[str] = Field(default_factory=list)


class StoryPlan(BaseModel):
    title: str
    premise: str
    language: Language
    locations: list[PlannedLocation]
    beats: list[Beat] = Field(default_factory=list)
    #: Location ids whose scene asks the player to write something.
    open_question_at: list[str] = Field(default_factory=list)
    #: Shown before the game starts; only ever set in safe mode.
    content_note: str = ""


# ── What the model is asked for ─────────────────────────────────────────


class PlannedLocationDraft(BaseModel):
    name: str
    description: str
    visual: str
    #: True when this place should only open once somewhere else is resolved.
    locked: bool = False


class BeatDraft(BaseModel):
    title: str
    summary: str
    #: Index into `StoryPlanDraft.locations`.
    location_index: int


class StoryPlanDraft(BaseModel):
    #: Echoed back so the orchestrator can assert the language actually landed.
    language: Language
    title: str
    premise: str
    locations: list[PlannedLocationDraft]
    beats: list[BeatDraft]
    #: How many locations should ask an open question (0-2).
    open_question_count: int = 1
    #: What the player is about to encounter, in their own language - safe
    #: mode only, and an empty string otherwise. Required rather than
    #: defaulted: a model that may omit a field does omit it, and the fallback
    #: is the English note from ingest, which a Polish player should not see.
    content_note: str


class ChoiceDraft(BaseModel):
    text: str
    #: One clause on what this leads to, carried into the ending.
    consequence: str
    #: False marks the choice as a step away from what the plan expects.
    on_canon: bool = True


class SceneDraft(BaseModel):
    location_index: int
    text: str
    choices: list[ChoiceDraft]
    #: Empty string when this scene asks nothing.
    open_question: str = ""


class ScenesDraft(BaseModel):
    language: Language
    scenes: list[SceneDraft]


class PlayerBeatDraft(BaseModel):
    beat_index: int
    what_you_did: str
    #: True when the player's run actually hit this beat.
    matched: bool


class EndingDraft(BaseModel):
    language: Language
    title: str
    summary: str
    player_beats: list[PlayerBeatDraft] = Field(default_factory=list)
