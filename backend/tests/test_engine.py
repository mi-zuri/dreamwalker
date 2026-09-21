"""The turn engine on its own, against a hand-drawn map.

Everywhere else the engine is exercised through a generated game, which is the
right way to catch integration problems and the wrong way to catch the engine
refusing an action it should have taken: a generated map is different every
run, and the interesting cases - a door that is still shut, a choice id that
does not exist, an answer typed before the choice it belongs to - are hard to
arrange on purpose.

So this draws seven columns by five rows and drives the state machine
directly. No model, no store, no pipeline.

    #######
    #@.A..#      `@` start, `A` and `B` destinations
    #.#####      `+` a door that opens once `A` is finished
    #+..B.#
    #######

`B` has no way in except the door, which is the point.
"""

import pytest

from app.models.game import (
    BeatProgress,
    Choice,
    Destination,
    Door,
    EndingComparison,
    GameMap,
    GameState,
    Pos,
    Scene,
    StyleCard,
)
from app.models.script import ChoiceOutcome, GameScript
from app.pipeline.engine import (
    DIVERGENCE_STEP,
    apply_answer,
    apply_choice,
    apply_move,
    set_off,
    to_saved,
)

START = Pos(x=1, y=1)
AT_A = Pos(x=3, y=1)
AT_B = Pos(x=4, y=3)
DOOR = Pos(x=1, y=3)

STYLE = StyleCard(
    genre="noir",
    narrative_voice="second_present",
    tone="dry",
    protagonist_role="witness",
    visual_style="ink_wash",
    music_mood="drone",
    pacing="slow_burn",
)


def make_map() -> GameMap:
    return GameMap(
        width=7,
        height=5,
        tiles=["#######", "#@.A..#", "#.#####", "#+..B.#", "#######"],
        destinations=[
            Destination(key="A", location_id="loc-a", name="The Landing"),
            Destination(key="B", location_id="loc-b", name="The Back Room"),
        ],
        doors=[Door(key="+", pos=DOOR, unlock_from="A")],
    )


def make_state() -> GameState:
    return GameState(
        game_id="g1",
        mode="news",
        region="world",
        language="en",
        style_card=STYLE,
        map=make_map(),
        player_pos=START.model_copy(),
        current_scene=Scene(id="start", location_id="start", text="You arrive."),
        beat_progress=[
            BeatProgress(beat_id="beat-1", status="pending"),
            BeatProgress(beat_id="beat-2", status="pending"),
        ],
    )


def make_script(*, questions: dict[str, str] | None = None) -> GameScript:
    return GameScript(
        game_id="g1",
        scenes={
            "loc-a": Scene(id="s-a", location_id="loc-a", text="A landing, and a door."),
            "loc-b": Scene(id="s-b", location_id="loc-b", text="The back room, finally."),
        },
        choices={
            "loc-a": [
                Choice(id="a-c1", text="Follow the plan"),
                Choice(id="a-c2", text="Do something else"),
            ],
            "loc-b": [
                Choice(id="b-c1", text="Follow the plan"),
                Choice(id="b-c2", text="Do something else"),
            ],
        },
        outcomes={
            "a-c1": ChoiceOutcome(beat_id="beat-1", on_canon=True),
            "a-c2": ChoiceOutcome(beat_id="beat-1", on_canon=False),
            "b-c1": ChoiceOutcome(beat_id="beat-2", on_canon=True),
            "b-c2": ChoiceOutcome(beat_id="beat-2", on_canon=False),
        },
        open_questions=questions or {},
        ending=EndingComparison(game_id="g1", mode="news", title="", summary="", style_card=STYLE),
    )


@pytest.fixture
def game():
    return make_state(), make_script(questions={"loc-a": "What do you say?"})


# ── walking ─────────────────────────────────────────────────────────────


def test_arriving_at_a_destination_opens_its_scene(game):
    state, script = game
    apply_move(state, script, AT_A)

    assert state.player_pos == AT_A
    assert state.view == "scene"
    assert state.current_scene.location_id == "loc-a"
    assert [c.id for c in state.choices] == ["a-c1", "a-c2"]
    assert state.open_question is not None
    assert state.visited == ["A"]


def test_a_locked_destination_cannot_be_walked_to_until_it_is_unlocked(game):
    state, script = game
    apply_move(state, script, AT_B)
    assert state.player_pos == START, "the door let the player through while shut"

    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")
    apply_move(state, script, AT_B)
    assert state.player_pos == AT_B


def test_walking_into_a_wall_is_ignored_rather_than_an_error(game):
    state, script = game
    apply_move(state, script, Pos(x=0, y=0))
    assert state.player_pos == START


def test_standing_still_is_not_a_move(game):
    state, script = game
    apply_move(state, script, START.model_copy())
    assert state.visited == []


def test_a_plain_floor_tile_moves_the_player_and_nothing_else(game):
    state, script = game
    apply_move(state, script, Pos(x=2, y=1))

    assert state.player_pos == Pos(x=2, y=1)
    assert state.visited == []
    assert state.choices == []


def test_a_destination_with_no_scene_leaves_the_player_where_they_stand(game):
    """Generation can fail; the map is already drawn by the time it does."""
    state, script = game
    del script.scenes["loc-a"]

    apply_move(state, script, AT_A)

    assert state.player_pos == AT_A, "the move itself is still legal"
    assert state.choices == []
    assert state.current_scene.location_id == "start"


def test_a_finished_game_ignores_further_movement(game):
    state, script = game
    state.finished = True
    apply_move(state, script, AT_A)
    assert state.player_pos == START


def test_returning_to_a_finished_destination_shows_the_map_not_the_scene(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")
    apply_move(state, script, Pos(x=2, y=1))
    apply_move(state, script, AT_A)

    assert state.view == "travel"
    assert state.choices == []
    assert state.open_question is None


# ── choosing ────────────────────────────────────────────────────────────


def test_an_on_canon_choice_matches_its_beat_and_does_not_diverge(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")

    assert state.beat_progress[0].status == "matched"
    assert state.divergence == 0.0
    assert script.taken == ["a-c1"]
    assert state.turn == 1


def test_an_off_canon_choice_diverges_the_beat_it_names(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c2")

    assert state.beat_progress[0].status == "diverged"
    assert state.beat_progress[1].status == "pending", "only the named beat moved"
    assert state.divergence == DIVERGENCE_STEP


def test_a_choice_that_names_no_beat_resolves_the_next_pending_one(game):
    state, script = game
    script.outcomes["a-c1"] = ChoiceOutcome(beat_id=None, on_canon=True)

    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")

    assert state.beat_progress[0].status == "matched"


def test_a_choice_naming_a_beat_that_does_not_exist_falls_back_to_the_next_pending(game):
    state, script = game
    script.outcomes["a-c1"] = ChoiceOutcome(beat_id="beat-nine", on_canon=True)

    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")

    assert state.beat_progress[0].status == "matched"


def test_an_unknown_choice_id_changes_nothing(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "not-a-choice")

    assert state.turn == 0
    assert len(state.choices) == 2
    assert script.taken == []


def test_a_finished_game_ignores_further_choices(game):
    state, script = game
    apply_move(state, script, AT_A)
    state.finished = True
    apply_choice(state, script, "a-c1")
    assert state.turn == 0


def test_divergence_never_passes_one(game):
    state, script = game
    state.beat_progress = [BeatProgress(beat_id=f"b{i}", status="pending") for i in range(10)]
    script.choices["loc-a"] = [Choice(id=f"a-c{i}", text="off") for i in range(10)]
    for i in range(10):
        script.outcomes[f"a-c{i}"] = ChoiceOutcome(on_canon=False)

    apply_move(state, script, AT_A)
    for i in range(10):
        state.choices = [Choice(id=f"a-c{i}", text="off")]
        state.finished = False
        apply_choice(state, script, f"a-c{i}")

    assert state.divergence == 1.0


def test_resolving_every_destination_finishes_the_game(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")
    assert not state.finished
    assert state.view == "travel"

    apply_move(state, script, AT_B)
    apply_choice(state, script, "b-c1")
    assert state.finished
    assert sorted(state.resolved) == ["A", "B"]


def test_the_turn_log_records_the_scene_as_it_was_shown(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")

    turn = script.turns[0]
    assert turn.turn == 1
    assert turn.chosen == "Follow the plan"
    assert turn.scene.text == "A landing, and a door."
    assert turn.player_pos == AT_A


# ── answering ───────────────────────────────────────────────────────────


def test_an_answer_typed_before_the_choice_lands_on_the_same_turn(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_answer(state, script, "  I tell her the truth.  ")

    assert state.open_question is None
    assert script.pending_answer == "I tell her the truth."

    apply_choice(state, script, "a-c1")
    assert script.turns[0].answer == "I tell her the truth."
    assert script.pending_answer is None


def test_an_answer_typed_after_the_choice_is_attached_to_it(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_choice(state, script, "a-c1")
    state.open_question = state.open_question or _question()
    apply_answer(state, script, "Afterwards, I said it anyway.")

    assert script.turns[0].answer == "Afterwards, I said it anyway."
    assert script.pending_answer is None


def test_a_blank_answer_dismisses_the_question_without_recording_it(game):
    state, script = game
    apply_move(state, script, AT_A)
    apply_answer(state, script, "   ")

    assert state.open_question is None
    assert script.pending_answer is None
    assert not script.turns


def test_answering_when_nothing_was_asked_does_nothing(game):
    state, script = game
    apply_move(state, script, Pos(x=2, y=1))
    apply_answer(state, script, "unprompted")
    assert script.pending_answer is None


def _question():
    from app.models.game import OpenQuestion

    return OpenQuestion(id="q-loc-a", prompt="What do you say?")


# ── leaving, and saving ─────────────────────────────────────────────────


def test_setting_off_returns_to_the_map(game):
    state, script = game
    apply_move(state, script, AT_A)
    set_off(state)
    assert state.view == "travel"


def test_a_finished_game_stays_on_its_ending(game):
    state, _ = game
    state.finished = True
    state.view = "scene"
    set_off(state)
    assert state.view == "scene"


def test_a_saved_game_carries_what_the_library_lists(game):
    state, script = game
    script.ending = script.ending.model_copy(update={"title": "What The Room Kept"})
    script.ending.match_score = 0.5
    state.current_scene.image_url = "/api/media/x.png"

    saved = to_saved(state, script, "2026-09-20T10:00:00+00:00")

    assert saved.game_id == "g1"
    assert saved.title == "What The Room Kept"
    assert saved.match_score == 0.5
    assert saved.language == "en"
    assert saved.image_url == "/api/media/x.png"
