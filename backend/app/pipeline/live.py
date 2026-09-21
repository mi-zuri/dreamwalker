"""Assembling a real game, stage by stage.

The shape of this file is dictated by one number: the player should be looking
at something within about eight seconds. That rules out doing the obvious
thing - plan, then map, then five scenes, then five images, then start - which
is something like twenty.

So: the plan is the only call on the critical path that nothing else can start
without. The map is procedural and costs no time at all. Scenes and the
opening image then run together, and the remaining location images run *after*
the player is already reading the premise and walking towards the first place,
which is fifteen to twenty seconds they were going to spend anyway.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from string import ascii_uppercase
from zlib import crc32

from app.game.map import START
from app.llm.base import LLM
from app.models.game import (
    BeatProgress,
    Destination,
    GameMap,
    GameState,
    Language,
    Mode,
    NewGameRequest,
    Pos,
    SafetyClass,
    Scene,
    Stage,
    StyleCard,
)
from app.models.plan import Beat, PlannedLocation, ScenesDraft, StoryPlan
from app.models.script import GameScript
from app.news.models import Photo
from app.pipeline import ending as ending_stage
from app.pipeline.images import STAGE as IMAGE_STAGE
from app.pipeline.images import SourcedImage, generate_image, image_for, prompt_for
from app.pipeline.map_validator import validate_map
from app.pipeline.prompts import IMAGE_RULE
from app.pipeline.scenes import assemble, write_scenes
from app.pipeline.story import make_plan
from app.pipeline.style_card import visual_prompt
from app.pipeline.world_map import DoorSpec, build_map, layout_for
from app.settings import settings
from app.storage.assets import AssetStore

log = logging.getLogger(__name__)

Progress = Callable[[Stage], Awaitable[None]]


@dataclass(frozen=True)
class OpenedGame:
    """What the loading screen waits for, plus what the background needs next."""

    state: GameState
    script: GameScript
    plan: StoryPlan
    style: StyleCard
    safety_class: SafetyClass = "allowed"
    #: News mode's press photos, matched to locations after the player is
    #: already playing - matching is a model call and does not belong on the
    #: critical path when the reward is a picture.
    photos: tuple[Photo, ...] = ()


#: The opening scene's id. It is not a destination, so it never appears on the
#: map - the player reads it, presses SET OFF and walks.
PROLOGUE = "start"


def idea_brief(idea: str, language: Language) -> str:
    """The player's sentence, quoted rather than paraphrased.

    Their exact words matter more than anything we could add around them, so
    the brief stays short and the style card does the rest of the work.
    """
    cleaned = " ".join(idea.split())[:600]
    return (
        f'THE PLAYER\'S IDEA, in their own words:\n"{cleaned}"\n\n'
        "Build the story around this. It is the whole point of the run: if the "
        "player cannot see their own idea in what you write, you have failed. "
        "Take it literally before you take it as a metaphor."
    )


def map_for(plan: StoryPlan, style: StyleCard, seed: int) -> GameMap:
    """A floor plan whose destinations are the plan's locations, in order.

    The grid speaks in letters and the rest of the game speaks in location
    ids; `Destination` is where the two are tied together, so nothing else
    ever has to know that `loc-c` is drawn as `C`.
    """
    keys = {loc.id: ascii_uppercase[i] for i, loc in enumerate(plan.locations)}
    destinations = [
        Destination(key=keys[loc.id], location_id=loc.id, name=loc.name) for loc in plan.locations
    ]
    doors = [
        DoorSpec(gates=keys[loc.id], unlock_from=keys[loc.locked_by])
        for loc in plan.locations
        if loc.locked_by and loc.locked_by in keys
    ]
    return build_map(destinations, doors, layout=layout_for(style.pacing), seed=seed)


def start_pos(game_map: GameMap) -> Pos:
    for y, row in enumerate(game_map.tiles):
        if START in row:
            return Pos(x=row.index(START), y=y)
    raise RuntimeError("generated map has no start tile")


def prologue_prompt(plan: StoryPlan, style: StyleCard) -> str:
    """An establishing shot: the first location seen from outside, at a distance."""
    opening = plan.locations[0].visual if plan.locations else plan.premise
    return (
        f"{visual_prompt(style)}. Wide establishing shot, seen from a distance: "
        f"{opening.strip()}. {IMAGE_RULE}"
    )


async def open_game(
    llm: LLM,
    assets: AssetStore,
    *,
    game_id: str,
    req: NewGameRequest,
    style: StyleCard,
    brief: str,
    progress: Progress,
    safety_class: SafetyClass = "allowed",
    content_note: str = "",
    source_note: str | None = None,
    mode: Mode | None = None,
    canon: list[Beat] | None = None,
    opening_image: SourcedImage | None = None,
    photos: tuple[Photo, ...] = (),
) -> OpenedGame:
    """Everything the player needs to see something. Scenes are not in here.

    The returned script has no scenes yet: they are written by `fill_scenes`
    while the player reads the premise and walks, which is the only way a
    five-location game opens in under eight seconds. `apply_move` waits for
    them if the player gets there first.
    """
    mode = mode or req.mode
    language = req.language

    await progress("story")
    plan = await make_plan(
        llm,
        brief=brief,
        style=style,
        language=language,
        safety_class=safety_class,
        content_note=content_note,
    )
    if plan.language != language:
        # The stage echoes the language back precisely so this is catchable.
        log.warning("plan came back in %s, expected %s", plan.language, language)
    if canon:
        apply_canon(plan, canon)

    await progress("map")
    game_map = map_for(plan, style, crc32(game_id.encode()))
    report = validate_map(game_map)
    if not report.ok:  # pragma: no cover - build_map repairs before returning
        raise RuntimeError(f"generated map is unplayable:\n{report.as_diagnostics()}")

    await progress("images")
    # News mode usually has a real photograph of the event, which is free and
    # immediate; only Idea mode has to generate the one image on the critical
    # path.
    opening = opening_image or SourcedImage(await _prologue_image(llm, assets, plan, style))

    await progress("music")
    await progress("finishing")

    state = _state(
        game_id=game_id,
        req=req,
        mode=mode,
        plan=plan,
        style=style,
        game_map=game_map,
        opening=opening,
        safety_class=safety_class,
        content_note=content_note,
        source_note=source_note,
    )
    script = GameScript(
        game_id=game_id,
        plan=plan,
        ending=ending_stage.placeholder_ending(game_id, plan, style, mode),
    )
    return OpenedGame(state=state, script=script, plan=plan, style=style, safety_class=safety_class)


async def fill_scenes(
    llm: LLM,
    script: GameScript,
    plan: StoryPlan,
    style: StyleCard,
    *,
    safety_class: SafetyClass = "allowed",
) -> None:
    """Write every scene into an existing script.

    Failure here is survivable and must be: the player is already past the
    loading screen, so there is nowhere left to show an error. An empty draft
    assembles into each location's own planned description plus a set of dull
    choices - a worse game than intended, but a finishable one.
    """
    try:
        bundle = await write_scenes(llm, plan, style=style, safety_class=safety_class)
    except Exception:
        log.exception("scene generation failed for %s; falling back to the plan", script.game_id)
        bundle = assemble(ScenesDraft(language=plan.language, scenes=[]), plan)

    script.scenes = bundle.scenes
    script.choices = bundle.choices
    script.outcomes = bundle.outcomes
    script.open_questions = bundle.open_questions


async def _prologue_image(
    llm: LLM, assets: AssetStore, plan: StoryPlan, style: StyleCard
) -> str | None:
    """The one image on the critical path, and the only one with a deadline.

    Every other picture is generated while the player reads and walks, so it
    can wait for image quota indefinitely. This one cannot: past its timeout
    the game opens without a picture rather than holding the loading screen.
    """
    try:
        return await generate_image(
            llm,
            assets,
            prologue_prompt(plan, style),
            timeout=settings.prologue_image_timeout,
        )
    except Exception as exc:  # noqa: BLE001 - never block the opening on a picture
        log.warning("prologue image failed: %s", exc)
        return None


def _state(
    *,
    game_id: str,
    req: NewGameRequest,
    mode: Mode,
    plan: StoryPlan,
    style: StyleCard,
    game_map: GameMap,
    opening: SourcedImage,
    safety_class: SafetyClass,
    content_note: str,
    source_note: str | None,
) -> GameState:
    return GameState(
        game_id=game_id,
        mode=mode,
        view="scene",
        region=req.region if mode == "news" else None,
        language=req.language,
        safety_class=safety_class,
        content_note=content_note or None,
        source_note=source_note,
        style_card=style,
        map=game_map,
        player_pos=start_pos(game_map),
        current_scene=Scene(
            id=PROLOGUE,
            location_id=PROLOGUE,
            text=plan.premise,
            image_url=opening.url,
            image_credit=opening.credit,
        ),
        choices=[],
        beat_progress=[BeatProgress(beat_id=b.id, status="pending") for b in plan.beats],
    )


def apply_canon(plan: StoryPlan, canon: list[Beat]) -> StoryPlan:
    """Replace the plan's invented beats with what actually happened.

    The plan is asked for one beat per canon beat, in the same order, so the
    canon supplies the title, the summary and the citations while the plan
    supplies the location each one is tied to. Getting that pairing from the
    model by name would mean trusting it to echo an id; getting it by position
    only requires it to count.
    """
    beats: list[Beat] = []
    for order, source in enumerate(canon):
        if order < len(plan.beats):
            location_ref = plan.beats[order].location_ref
        else:
            location_ref = plan.locations[min(order, len(plan.locations) - 1)].id
        beats.append(
            Beat(
                id=f"beat-{order + 1}",
                order=order,
                title=source.title,
                summary=source.summary,
                location_ref=location_ref,
                certainty=source.certainty,
                sources=source.sources,
            )
        )
    plan.beats = beats
    return plan


async def fill_images(
    llm: LLM,
    assets: AssetStore,
    script: GameScript,
    locations: list[PlannedLocation],
    style: StyleCard,
    *,
    preset: dict[str, SourcedImage] | None = None,
) -> int:
    """Generate the per-location images, in arrival order, into an existing script.

    Sequential and in plan order on purpose. Image quota is two a minute for
    the whole project, so the question is never how fast they can all be made
    but which one is made first - and that should be the one the player is
    walking towards. One at a time also means an abandoned game stops costing
    money almost immediately, and the whole pass gives up at a deadline rather
    than queueing behind quota for a game nobody is still playing.
    """
    preset = preset or {}
    deadline = time.monotonic() + settings.background_image_seconds
    filled = 0
    for location in locations:
        if time.monotonic() > deadline:
            # Past this the player has almost certainly finished or left, and
            # a picture nobody will see is not worth waiting on image quota for.
            log.info("stopped filling images for %s at the deadline", script.game_id)
            break
        scene = script.scenes.get(location.id)
        if scene is None or scene.image_url:
            continue
        # A real photograph of the real place beats a generated one, and costs
        # nothing against the two-a-minute generation quota.
        sourced = preset.get(location.id) or await image_for(llm, assets, location, style)
        if sourced.url:
            scene.image_url = sourced.url
            scene.image_credit = sourced.credit
            filled += 1
    return filled


def image_prompts(plan: StoryPlan, style: StyleCard) -> list[str]:
    """Every prompt a full run would generate - used to price one offline."""
    return [prologue_prompt(plan, style)] + [
        prompt_for(location, style) for location in plan.locations
    ]


__all__ = [
    "IMAGE_STAGE",
    "PROLOGUE",
    "OpenedGame",
    "apply_canon",
    "fill_images",
    "fill_scenes",
    "idea_brief",
    "image_prompts",
    "map_for",
    "open_game",
    "prologue_prompt",
    "start_pos",
]
