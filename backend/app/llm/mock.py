"""Fixture replay - the zero-spend stand-in for the generation pipeline.

Under `LLM_MODE=mock` a new game is a clone of one of the four recorded runs
in `app/fixtures/games/`, picked to match the player's menu selection. The
clone is then re-keyed and re-languaged, so the rest of the backend cannot
tell the difference between a mock game and a generated one.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from app.models.game import (
    Choice,
    EndingComparison,
    GameState,
    NewGameRequest,
    Scene,
)
from app.models.script import GameScript

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "games"

#: Prompts for the one open-text question, per story language.
OPEN_QUESTION_PROMPT = {"pl": "Co powiedziałeś?", "en": "What did you say?"}


class MockGame(BaseModel):
    """One recorded run, as exported from the Phase 1 frontend fixtures."""

    id: str
    request: NewGameRequest
    state: GameState
    scenes: dict[str, Scene] = Field(default_factory=dict)
    choices: dict[str, list[Choice]] = Field(default_factory=dict)
    open_question_at: str | None = Field(default=None, alias="openQuestionAt")
    ending: EndingComparison

    model_config = {"populate_by_name": True}


@lru_cache(maxsize=1)
def load_fixtures() -> tuple[MockGame, ...]:
    files = sorted(FIXTURE_DIR.glob("*.json"))
    if not files:
        raise RuntimeError(f"no mock fixtures found in {FIXTURE_DIR}")
    return tuple(MockGame.model_validate(json.loads(f.read_text("utf-8"))) for f in files)


def pick_fixture(req: NewGameRequest) -> MockGame:
    """Closest recorded run: same mode first, then language, then region."""
    fixtures = load_fixtures()
    by_mode = [f for f in fixtures if f.request.mode == req.mode]
    pool = by_mode or list(fixtures)
    exact = next(
        (
            f
            for f in pool
            if f.request.story_language == req.story_language
            and (req.mode == "idea" or f.request.region == req.region)
        ),
        None,
    )
    return exact or pool[0]


def build_game(game_id: str, req: NewGameRequest) -> tuple[GameState, GameScript]:
    fixture = pick_fixture(req)

    state = fixture.state.model_copy(deep=True)
    state.game_id = game_id
    # The menu is authoritative for language, even when the fixture differs.
    state.story_language = req.story_language
    state.ui_language = req.ui_language

    ending = fixture.ending.model_copy(deep=True)
    ending.game_id = game_id

    script = GameScript(
        game_id=game_id,
        fixture_id=fixture.id,
        scenes={k: v.model_copy(deep=True) for k, v in fixture.scenes.items()},
        choices={k: [c.model_copy(deep=True) for c in v] for k, v in fixture.choices.items()},
        open_question_at=fixture.open_question_at,
        ending=ending,
    )
    return state, script
