"""Fixture replay - the zero-spend stand-in for the generation pipeline.

Under `LLM_MODE=mock` a new game is a clone of one of the four recorded runs
in `app/fixtures/games/`, picked to match the player's menu selection. The
clone is then re-keyed and re-languaged, so the rest of the backend cannot
tell the difference between a mock game and a generated one.
"""

import json
from functools import lru_cache
from pathlib import Path
from zlib import crc32

from pydantic import BaseModel, Field

from app.game.map import START
from app.models.game import (
    Choice,
    EndingComparison,
    GameState,
    NewGameRequest,
    Pos,
    Scene,
)
from app.models.script import ChoiceOutcome, GameScript
from app.pipeline.ending import style_labels
from app.pipeline.map_validator import gated_destinations
from app.pipeline.world_map import DoorSpec, build_map, layout_for
from app.settings import settings

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "games"

#: Prompts for the one open-text question, per language.
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
    """Closest recorded run: mode, then language, then region.

    Language is a hard filter; region is only a preference. Recorded prose
    cannot be re-languaged, only relabelled, so matching the region first
    would hand a player who asked for English a game written in Polish -
    the one thing the language toggle promises never to do.
    """
    fixtures = load_fixtures()
    by_mode = [f for f in fixtures if f.request.mode == req.mode] or list(fixtures)
    pool = [f for f in by_mode if f.request.language == req.language] or by_mode
    return next((f for f in pool if f.request.region == req.region), pool[0])


def build_game(game_id: str, req: NewGameRequest) -> tuple[GameState, GameScript]:
    fixture = pick_fixture(req)

    state = fixture.state.model_copy(deep=True)
    state.game_id = game_id
    # The menu is authoritative for language, even when the fixture differs.
    # `pick_fixture` has already made sure it does not, for the text.
    state.language = req.language
    if settings.mock_map_source == "generated":
        _regenerate_map(state)

    ending = fixture.ending.model_copy(deep=True)
    ending.game_id = game_id
    # The fixtures were recorded before the catalog could translate a card.
    ending.style_labels = style_labels(state.style_card, state.language)

    choices = {k: [c.model_copy(deep=True) for c in v] for k, v in fixture.choices.items()}
    script = GameScript(
        game_id=game_id,
        fixture_id=fixture.id,
        scenes={k: v.model_copy(deep=True) for k, v in fixture.scenes.items()},
        choices=choices,
        outcomes=_recorded_outcomes(choices, state),
        open_questions=_recorded_questions(fixture, state.language),
        ending=ending,
        ending_final=True,
    )
    return state, script


def _recorded_questions(fixture: MockGame, language: str) -> dict[str, str]:
    """The fixtures predate multiple open questions and record one location."""
    if not fixture.open_question_at:
        return {}
    prompt = OPEN_QUESTION_PROMPT.get(language, OPEN_QUESTION_PROMPT["en"])
    return {fixture.open_question_at: prompt}


def _recorded_outcomes(
    choices: dict[str, list[Choice]], state: GameState
) -> dict[str, ChoiceOutcome]:
    """Fixtures record no canon, so the first choice at each place is it.

    That is arbitrary, and it is meant to be: it exists so the turn engine has
    exactly one code path, not so a mock run has a meaningful match score.
    """
    beats = [b.beat_id for b in state.beat_progress]
    outcomes: dict[str, ChoiceOutcome] = {}
    for index, (location_id, options) in enumerate(sorted(choices.items())):
        beat_id = beats[index] if index < len(beats) else None
        for position, choice in enumerate(options):
            outcomes[choice.id] = ChoiceOutcome(beat_id=beat_id, on_canon=position == 0)
    return outcomes


def _regenerate_map(state: GameState) -> None:
    """Swap the recorded grid for a freshly generated one.

    The fixture keeps its locations, its locks and its story; only the floor
    plan changes. Which destination each recorded door was guarding is not
    written down anywhere, so it is recovered from the grid itself.
    """
    recorded = state.map
    specs = [
        DoorSpec(gates=gated[0], unlock_from=door.unlock_from)
        for door in recorded.doors
        if (gated := gated_destinations(recorded, door))
    ]
    state.map = build_map(
        recorded.destinations,
        specs,
        layout=layout_for(state.style_card.pacing),
        seed=crc32(state.game_id.encode()),
    )
    state.player_pos = _start_of(state.map)


def _start_of(game_map) -> Pos:
    for y, row in enumerate(game_map.tiles):
        if START in row:
            return Pos(x=row.index(START), y=y)
    raise RuntimeError("generated map has no start tile")
