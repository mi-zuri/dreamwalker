"""Server-side content for a game, never exposed over the API.

Holds everything the pipeline pregenerates before play starts - scene text,
dialogue choices, the ending - plus the turn log recorded as the player goes.
Keeping it out of `GameState` keeps the client from being handed scenes it has
not reached yet, and keeps the generated OpenAPI schema to what the UI needs.
"""

from pydantic import BaseModel, Field

from app.models.game import Choice, EndingComparison, ReplayTurn, Scene


class GameScript(BaseModel):
    game_id: str
    #: Which fixture this run was cloned from, under `LLM_MODE=mock`.
    fixture_id: str | None = None
    #: Keyed by `location_id`.
    scenes: dict[str, Scene] = Field(default_factory=dict)
    #: Keyed by `location_id`.
    choices: dict[str, list[Choice]] = Field(default_factory=dict)
    #: Location whose scene asks the player to write something.
    open_question_at: str | None = None
    ending: EndingComparison
    #: Appended to as the player plays; served back as the replay.
    turns: list[ReplayTurn] = Field(default_factory=list)
    #: Set when the player answers before choosing, so the two land on one turn.
    pending_answer: str | None = None
