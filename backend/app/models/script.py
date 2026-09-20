"""Server-side content for a game, never exposed over the API.

Holds everything the pipeline pregenerates before play starts - the plan,
scene text, dialogue choices, the ending - plus the turn log recorded as the
player goes. Keeping it out of `GameState` keeps the client from being handed
scenes it has not reached yet, and keeps the generated OpenAPI schema down to
what the UI actually needs.

`outcomes` is the clearest case. The player sees three equal-looking choices;
which of them follows the planned beat is decided at generation time and kept
here, so it can shape the ending without ever being rendered as a hint.
"""

from pydantic import BaseModel, Field

from app.models.game import Choice, EndingComparison, ReplayTurn, Scene
from app.models.plan import StoryPlan


class ChoiceOutcome(BaseModel):
    beat_id: str | None = None
    #: False when taking this choice steps away from the planned beat.
    on_canon: bool = True
    #: One clause on what it led to, replayed to the ending stage.
    consequence: str = ""


class GameScript(BaseModel):
    game_id: str
    #: Which fixture this run was cloned from, under `LLM_MODE=mock`.
    fixture_id: str | None = None
    #: Absent for fixture games, which were recorded before plans existed.
    plan: StoryPlan | None = None
    #: Keyed by `location_id`.
    scenes: dict[str, Scene] = Field(default_factory=dict)
    #: Keyed by `location_id`.
    choices: dict[str, list[Choice]] = Field(default_factory=dict)
    #: Keyed by `choice_id`.
    outcomes: dict[str, ChoiceOutcome] = Field(default_factory=dict)
    #: Location id -> the question its scene asks. At most two per game.
    open_questions: dict[str, str] = Field(default_factory=dict)
    ending: EndingComparison
    #: False until the ending stage has actually written one; the value held
    #: before then is a placeholder built from the plan.
    ending_final: bool = False
    #: Appended to as the player plays; served back as the replay.
    turns: list[ReplayTurn] = Field(default_factory=list)
    #: Choice ids in the order they were taken, for the ending stage.
    taken: list[str] = Field(default_factory=list)
    #: Set when the player answers before choosing, so the two land on one turn.
    pending_answer: str | None = None
