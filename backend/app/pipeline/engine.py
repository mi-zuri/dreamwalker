"""The turn engine.

Pure state transitions: given a `GameState` and its `GameScript`, apply one
player action. No I/O and no model calls, so the whole game loop is testable
offline and behaves identically under mock and live generation.

The client animates movement locally but this is the authority: a move is
BFS-validated against the server's own copy of the map, and a move to a tile
the player cannot actually reach is ignored rather than trusted.
"""

from app.game.map import destination_at, path_to
from app.models.game import (
    BeatProgress,
    GameState,
    OpenQuestion,
    Pos,
    ReplayTurn,
    SavedGame,
)
from app.models.script import GameScript

#: How much a single off-canon choice moves the divergence needle.
DIVERGENCE_STEP = 0.25


def _enter(state: GameState, script: GameScript, dest_key: str, location_id: str) -> None:
    """Swap in a destination's scene, or send the player back to travel."""
    scene = script.scenes.get(location_id)
    if scene is None:
        return

    state.current_scene = scene.model_copy(deep=True)
    done = dest_key in state.resolved
    state.view = "travel" if done else "scene"
    state.choices = [] if done else [c.model_copy() for c in script.choices.get(location_id, [])]
    question = script.open_questions.get(location_id)
    state.open_question = (
        OpenQuestion(id=f"q-{location_id}", prompt=question) if question and not done else None
    )


def _beat_for(state: GameState, script: GameScript, choice_id: str) -> BeatProgress | None:
    """The beat this choice resolves, or the next pending one if it names none."""
    outcome = script.outcomes.get(choice_id)
    if outcome is not None and outcome.beat_id:
        named = next((b for b in state.beat_progress if b.beat_id == outcome.beat_id), None)
        if named is not None:
            return named
    return next((b for b in state.beat_progress if b.status == "pending"), None)


def apply_move(state: GameState, script: GameScript, to: Pos) -> GameState:
    """Walk to `to`. Unreachable targets are a no-op, not an error."""
    if state.finished:
        return state
    if (to.x, to.y) == (state.player_pos.x, state.player_pos.y):
        return state
    if not path_to(state.map, state.player_pos, to, state.unlocked):
        return state

    state.player_pos = to
    dest = destination_at(state.map, to)
    if dest is None:
        return state

    if dest.key not in state.visited:
        state.visited.append(dest.key)
    if dest.key not in state.unlocked:
        state.unlocked.append(dest.key)
    _enter(state, script, dest.key, dest.location_id)
    return state


def apply_choice(state: GameState, script: GameScript, choice_id: str) -> GameState:
    if state.finished:
        return state

    index = next((i for i, c in enumerate(state.choices) if c.id == choice_id), -1)
    if index < 0:
        return state
    choice = state.choices[index]
    shown_scene = state.current_scene.model_copy(deep=True)
    state.turn += 1

    # Whether this choice follows the planned beat was decided at generation
    # time and kept server-side, so the player never sees which one is "right".
    outcome = script.outcomes.get(choice_id)
    on_canon = outcome.on_canon if outcome is not None else index == 0
    beat = _beat_for(state, script, choice_id)
    if beat is not None:
        beat.status = "matched" if on_canon else "diverged"
    if not on_canon:
        state.divergence = min(1.0, state.divergence + DIVERGENCE_STEP)
    script.taken.append(choice_id)

    state.choices = []
    state.current_scene = state.current_scene.model_copy(
        update={"id": f"{state.current_scene.id}-t{state.turn}"}
    )

    script.turns.append(
        ReplayTurn(
            turn=state.turn,
            scene=shown_scene,
            player_pos=state.player_pos.model_copy(),
            chosen=choice.text,
            answer=script.pending_answer,
        )
    )
    script.pending_answer = None

    here = destination_at(state.map, state.player_pos)
    if here is not None and here.key not in state.resolved:
        state.resolved.append(here.key)

    if len(state.resolved) >= len(state.map.destinations):
        state.finished = True
    else:
        state.view = "travel"
    return state


def apply_answer(state: GameState, script: GameScript, text: str) -> GameState:
    if state.open_question is None:
        return state
    state.open_question = None

    answer = text.strip()
    if not answer:
        return state

    # The player may answer before or after choosing; either way it belongs to
    # the turn taken at this location.
    location_id = state.current_scene.location_id
    for turn in reversed(script.turns):
        if turn.scene.location_id == location_id:
            turn.answer = answer
            return state
    script.pending_answer = answer
    return state


def set_off(state: GameState) -> GameState:
    """Leave the current scene and go back to the map."""
    if not state.finished:
        state.view = "travel"
    return state


def to_saved(state: GameState, script: GameScript, played_at: str) -> SavedGame:
    return SavedGame(
        game_id=state.game_id,
        mode=state.mode,
        region=state.region,
        title=script.ending.title,
        played_at=played_at,
        story_language=state.story_language,
        match_score=script.ending.match_score,
        image_url=state.current_scene.image_url,
    )
