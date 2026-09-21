"""The generation pipeline, run end to end against `FakeLLM`.

These are the tests that would catch a stage-sequencing or normalization bug.
`LLM_MODE=mock` cannot: it replays a recorded game and never runs any of this.
"""

import pytest

from app.llm.fake import TINY_PNG, FakeLLM
from app.models.game import NewGameRequest, StyleCard
from app.models.plan import (
    MAX_LOCATIONS,
    MAX_OPEN_QUESTIONS,
    BeatDraft,
    PlannedLocationDraft,
    StoryPlanDraft,
)
from app.pipeline import live
from app.pipeline.images import prompt_for
from app.pipeline.map_validator import validate_map
from app.pipeline.prompts import IMAGE_RULE
from app.pipeline.scenes import write_scenes
from app.pipeline.story import MAX_LOCKED, make_plan, normalize_plan
from app.storage.assets import MemoryAssets

STYLE = StyleCard(
    genre="noir",
    narrative_voice="second_present",
    tone="dry",
    protagonist_role="outsider",
    visual_style="ink_wash",
    music_mood="drone",
    pacing="slow_burn",
)


def request(**overrides) -> NewGameRequest:
    return NewGameRequest(
        **{
            "mode": "idea",
            "idea": "a night porter who keeps finding the same coat",
            "language": "en",
            **overrides,
        }
    )


async def build(*, scenes: bool = True, **overrides):
    """Open a game the way the orchestrator does, then optionally fill scenes.

    `scenes=False` is the state the player is actually handed at `ready`: the
    premise and the map, with the scenes still being written behind them.
    """
    llm = FakeLLM(locations=overrides.pop("locations", 4))
    assets = MemoryAssets()
    req = request(**overrides)
    stages: list[str] = []

    opened = await live.open_game(
        llm,
        assets,
        game_id="test-game",
        req=req,
        style=STYLE,
        brief=live.idea_brief(req.idea or "", req.language),
        progress=_record(stages),
        mode="idea",
    )
    if scenes:
        await live.fill_scenes(llm, opened.script, opened.plan, STYLE)
    return llm, assets, opened.state, opened.script, opened.plan, stages


def _record(stages: list[str]):
    async def progress(stage: str) -> None:
        stages.append(stage)

    return progress


# ── the plan stage ──────────────────────────────────────────────────────


async def test_a_plan_becomes_ids_locations_and_beats():
    plan = await make_plan(FakeLLM(), brief="anything", style=STYLE, language="en")
    assert plan.locations
    assert [loc.id for loc in plan.locations] == [
        f"loc-{c}" for c in "abcde"[: len(plan.locations)]
    ]
    assert all(beat.location_ref in {loc.id for loc in plan.locations} for beat in plan.beats)


def test_the_first_location_is_never_locked():
    draft = StoryPlanDraft(
        language="en",
        title="T",
        premise="P",
        content_note="",
        locations=[
            PlannedLocationDraft(name=f"L{i}", description="d", visual="v", locked=True)
            for i in range(4)
        ],
        beats=[],
    )
    plan = normalize_plan(draft, language="en")
    assert plan.locations[0].locked_by == ""
    assert sum(1 for loc in plan.locations if loc.locked_by) <= MAX_LOCKED


def test_a_plan_longer_than_the_map_can_hold_is_trimmed():
    draft = StoryPlanDraft(
        language="en",
        title="T",
        premise="P",
        content_note="",
        locations=[
            PlannedLocationDraft(name=f"L{i}", description="d", visual="v") for i in range(9)
        ],
        beats=[BeatDraft(title="b", summary="s", location_index=8)],
    )
    plan = normalize_plan(draft, language="en")
    assert len(plan.locations) == MAX_LOCATIONS
    # The beat pointed at a location that no longer exists, so it is dropped
    # rather than left dangling at an index nothing can resolve.
    assert plan.beats == []


async def test_open_questions_stay_within_their_budget():
    for count in range(5):
        draft = StoryPlanDraft(
            language="en",
            title="T",
            premise="P",
            content_note="",
            locations=[
                PlannedLocationDraft(name=f"L{i}", description="d", visual="v") for i in range(4)
            ],
            beats=[],
            open_question_count=count,
        )
        plan = normalize_plan(draft, language="en")
        assert len(plan.open_question_at) <= MAX_OPEN_QUESTIONS
        assert len(set(plan.open_question_at)) == len(plan.open_question_at)


async def test_the_language_instruction_reaches_every_stage():
    for language in ("pl", "en"):
        llm = FakeLLM()
        plan = await make_plan(llm, brief="x", style=STYLE, language=language)
        assert plan.language == language
        await write_scenes(llm, plan, style=STYLE)
        assert all(f'"{language}"' in system for _, system in llm.prompts)


# ── the scene stage ─────────────────────────────────────────────────────


async def test_every_location_gets_a_scene_and_three_choices():
    llm = FakeLLM(locations=5)
    plan = await make_plan(llm, brief="x", style=STYLE, language="en")
    bundle = await write_scenes(llm, plan, style=STYLE)

    for location in plan.locations:
        assert bundle.scenes[location.id].text
        assert len(bundle.choices[location.id]) == 3
        ids = [c.id for c in bundle.choices[location.id]]
        assert len(set(ids)) == 3


async def test_exactly_one_choice_per_scene_follows_the_plan():
    llm = FakeLLM()
    plan = await make_plan(llm, brief="x", style=STYLE, language="en")
    bundle = await write_scenes(llm, plan, style=STYLE)

    for location in plan.locations:
        flags = [bundle.outcomes[c.id].on_canon for c in bundle.choices[location.id]]
        assert any(flags) and not all(flags), "a scene needs a way on and a way off"


async def test_a_short_scene_list_still_leaves_every_location_playable():
    """A model that writes four scenes for five rooms must not strand the fifth."""
    from app.models.plan import SceneDraft, ScenesDraft
    from app.pipeline.scenes import assemble

    llm = FakeLLM(locations=5)
    plan = await make_plan(llm, brief="x", style=STYLE, language="en")
    short = ScenesDraft(
        language="en",
        scenes=[SceneDraft(location_index=0, text="only this one", choices=[])],
    )
    bundle = assemble(short, plan)
    assert set(bundle.scenes) == {loc.id for loc in plan.locations}
    assert bundle.scenes["loc-e"].text == plan.locations[4].description


async def test_the_planned_open_questions_survive_a_forgetful_scene_stage():
    from app.models.plan import ScenesDraft
    from app.pipeline.scenes import assemble

    llm = FakeLLM()
    plan = await make_plan(llm, brief="x", style=STYLE, language="pl")
    bundle = assemble(ScenesDraft(language="pl", scenes=[]), plan)
    assert set(bundle.open_questions) == set(plan.open_question_at)
    assert all(text for text in bundle.open_questions.values())


# ── images ──────────────────────────────────────────────────────────────


def test_image_prompts_are_english_and_forbid_text():
    from app.models.plan import PlannedLocation

    location = PlannedLocation(id="loc-a", name="Szopa", description="opis", visual="a wet shed")
    prompt = prompt_for(location, STYLE)
    assert prompt.endswith(IMAGE_RULE)
    assert "ink wash" in prompt
    assert "opis" not in prompt, "story-language prose must not reach an image prompt"


async def test_an_identical_prompt_is_never_paid_for_twice():
    from app.pipeline.images import generate_image

    llm, assets = FakeLLM(), MemoryAssets()
    first = await generate_image(llm, assets, "a wet shed")
    second = await generate_image(llm, assets, "a wet shed")
    assert first == second
    assert llm.usage.images == 1


async def test_a_refused_image_is_not_fatal():
    from app.models.plan import PlannedLocation
    from app.pipeline.images import image_for

    llm = FakeLLM(fail_stages=("images",))
    sourced = await image_for(
        llm,
        MemoryAssets(),
        PlannedLocation(id="loc-a", name="n", description="d", visual="v"),
        STYLE,
    )
    assert sourced.url is None


# ── the whole build ─────────────────────────────────────────────────────


async def test_a_built_game_is_playable_and_reports_its_stages():
    _, _, state, script, plan, stages = await build()

    assert stages == ["story", "map", "images", "music", "finishing"]
    assert state.view == "scene"
    assert state.current_scene.location_id == live.PROLOGUE
    assert state.choices == [], "the opening scene offers SET OFF, not choices"
    assert state.current_scene.image_url, "the opening image is on the critical path"

    report = validate_map(state.map)
    assert report.ok, report.as_diagnostics()
    assert {d.location_id for d in state.map.destinations} == {loc.id for loc in plan.locations}
    assert [b.beat_id for b in state.beat_progress] == [b.id for b in plan.beats]
    assert script.ending.title == plan.title
    assert script.ending_final is False


async def test_ready_does_not_wait_for_the_scenes():
    """The opening is the premise and the map; scenes land behind the player."""
    llm, _, state, script, plan, _ = await build(scenes=False)
    assert script.scenes == {}
    assert state.current_scene.text == plan.premise
    assert llm.usage.by_stage.keys() == {"plan", "images"}

    await live.fill_scenes(llm, script, plan, STYLE)
    assert set(script.scenes) == {loc.id for loc in plan.locations}


async def test_a_failed_scene_stage_still_leaves_every_room_finishable():
    """There is no loading screen left to fail on, so it must degrade instead."""
    _, _, _, script, plan, _ = await build(scenes=False)
    broken = FakeLLM(fail_stages=("scenes",))
    await live.fill_scenes(broken, script, plan, STYLE)

    for location in plan.locations:
        assert script.scenes[location.id].text
        assert script.choices[location.id], "a room with no choices can never be resolved"


async def test_a_locked_location_is_gated_on_the_map():
    _, _, state, _, plan, _ = await build(locations=4)
    locked = [loc for loc in plan.locations if loc.locked_by]
    assert locked, "the fake plan locks its last location"

    from app.game.map import reachable_from
    from app.pipeline.live import start_pos

    key = next(d.key for d in state.map.destinations if d.location_id == locked[0].id)
    tile = next(
        (x, y) for y, row in enumerate(state.map.tiles) for x, char in enumerate(row) if char == key
    )
    assert tile not in reachable_from(state.map, start_pos(state.map), [])


async def test_only_the_opening_image_is_generated_up_front():
    llm, assets, _, script, plan, _ = await build()
    assert llm.usage.images == 1
    assert all(not scene.image_url for scene in script.scenes.values())

    filled = await live.fill_images(llm, assets, script, plan.locations, STYLE)
    assert filled == len(plan.locations)
    assert all(scene.image_url for scene in script.scenes.values())
    assert llm.usage.images == 1 + len(plan.locations)


async def test_a_game_costs_roughly_what_the_cost_model_promised():
    """Not the real price - the shape. One text call per stage, one image per place."""
    llm, assets, _, script, plan, _ = await build()
    await live.fill_images(llm, assets, script, plan.locations, STYLE)

    assert llm.usage.images == len(plan.locations) + 1
    assert set(llm.usage.by_stage) == {"plan", "scenes", "images"}
    assert llm.usage.usd > 0


async def test_a_polish_game_is_planned_and_written_in_polish():
    _, _, state, script, plan, _ = await build(language="pl")
    assert plan.language == "pl"
    assert state.language == "pl"
    assert script.open_questions


async def test_generation_failure_propagates():
    from app.llm.base import GenerationError

    llm = FakeLLM(fail_stages=("plan",))
    with pytest.raises(GenerationError):
        await make_plan(llm, brief="x", style=STYLE, language="en")


# ── the ending ──────────────────────────────────────────────────────────


async def test_the_ending_scores_news_and_does_not_score_idea():
    from app.pipeline.ending import match_score, write_ending

    llm, _, state, script, plan, _ = await build()
    state.beat_progress[0].status = "matched"
    state.beat_progress[1].status = "diverged"

    idea_ending = await write_ending(llm, state=state, script=script, plan=plan)
    assert idea_ending.match_score is None
    assert idea_ending.canon == []
    assert len(idea_ending.player) == len(plan.beats)

    state.mode = "news"
    news_ending = await write_ending(llm, state=state, script=script, plan=plan)
    assert news_ending.match_score == match_score(state)
    assert 0.0 < news_ending.match_score < 1.0
    assert len(news_ending.canon) == len(plan.beats)


def test_the_match_score_weights_later_beats_more_heavily():
    """Finishing a real event the way it went counts for more than starting it."""
    from types import SimpleNamespace

    from app.models.game import BeatProgress
    from app.pipeline.ending import match_score

    def run(*statuses: str) -> float:
        return match_score(
            SimpleNamespace(
                beat_progress=[
                    BeatProgress(beat_id=str(i), status=s) for i, s in enumerate(statuses)
                ]
            )
        )

    assert run("matched", "diverged") < run("diverged", "matched")
    assert run("matched", "matched") == 1.0
    assert run("diverged", "diverged") == 0.0


def test_the_fake_model_draws_a_real_png():
    assert TINY_PNG.startswith(b"\x89PNG\r\n")
