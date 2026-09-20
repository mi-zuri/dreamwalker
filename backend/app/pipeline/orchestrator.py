"""Stage sequencing, progress, and the background work that follows a game.

Creating a game is a request that cannot be answered synchronously: live
generation takes the better part of ten seconds, and holding an HTTP request
open for it would mean a proxy timeout is indistinguishable from a failure.
So `start_game` registers a job, returns the id immediately, and the loading
screen reads the job's progress over SSE.

Mock games are built in a millisecond and then *pretend* to take time, walking
the same stage script with sleeps. That is not cosmetic: it means the loading
screen, the SSE plumbing and the client's stage handling are exercised by the
zero-cost path, so they are not first tested on the paid one.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import get_args

from app.errors import AppError
from app.llm import make_llm
from app.llm.base import LLM, GenerationError, Usage
from app.llm.mock import build_game as build_mock_game
from app.models.game import EndingComparison, GameState, NewGameRequest, Stage
from app.models.script import GameScript
from app.pipeline import ending as ending_stage
from app.pipeline import live
from app.settings import settings
from app.storage.assets import AssetStore, get_assets
from app.storage.base import GameStore

log = logging.getLogger(__name__)

#: Coarse labels only - the UI never learns what a stage actually does.
STAGE_SCRIPT: tuple[tuple[Stage, float], ...] = (
    ("story", 0.9),
    ("map", 0.7),
    ("images", 1.1),
    ("music", 0.6),
    ("finishing", 0.5),
)

assert [s for s, _ in STAGE_SCRIPT] == list(get_args(Stage)), "stage script must cover every stage"

#: Jobs are dropped this long after they finish. Long enough for a reload to
#: still find one, short enough that a busy hour does not accumulate them.
JOB_TTL_SECONDS = 600
#: Generation that has not finished by now is not going to.
GENERATION_TIMEOUT_SECONDS = 120


@dataclass
class Job:
    """One game being generated. Append-only, so a late subscriber sees it all."""

    game_id: str
    simulated: bool = False
    stages: list[Stage] = field(default_factory=list)
    error: AppError | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)
    tick: asyncio.Event = field(default_factory=asyncio.Event)
    #: The per-game bill, for logging and for the spend counter.
    usage: Usage = field(default_factory=Usage)
    #: Image generation that continues after the player starts reading.
    background: asyncio.Task | None = None
    #: Spend already reported to the store, so background work only adds what
    #: it newly cost rather than re-charging the whole game.
    spent: float = 0.0

    async def emit(self, stage: Stage) -> None:
        self.stages.append(stage)
        self._wake()

    def fail(self, error: AppError) -> None:
        self.error = error
        self.finish()

    def finish(self) -> None:
        self.done.set()
        self._wake()

    def _wake(self) -> None:
        self.tick.set()
        self.tick = asyncio.Event()


_jobs: dict[str, Job] = {}

#: Opened per game while its scenes are still being written, and set when they
#: land. `await_scenes` is what stops a fast walker reaching an empty room.
_scene_gates: dict[str, asyncio.Event] = {}

#: How long a move waits for scenes before giving up and letting the player
#: stay on the map. Scene generation takes about seven seconds; this is slack.
SCENE_WAIT_SECONDS = 30.0


def job_for(game_id: str) -> Job | None:
    return _jobs.get(game_id)


def _forget_later(game_id: str) -> None:
    async def sweep() -> None:
        await asyncio.sleep(JOB_TTL_SECONDS)
        _jobs.pop(game_id, None)
        _scene_gates.pop(game_id, None)

    task = asyncio.create_task(sweep())
    # Keeps the task from being garbage-collected mid-sleep.
    task.add_done_callback(lambda _: None)


async def check_budget(store: GameStore) -> None:
    """Hard month-to-date cap, checked before anything can spend.

    This is the only spend limit in the system: there is deliberately no
    per-user or per-day game cap, and image generation is uncapped.
    """
    spend = await store.month_spend()
    if spend >= settings.monthly_budget_usd:
        raise AppError(
            "budget_exceeded",
            f"month-to-date spend ${spend:.2f} reached the ${settings.monthly_budget_usd:.2f} cap",
        )


async def start_game(store: GameStore, uid: str, req: NewGameRequest) -> str:
    """Register the job and return its id. Generation continues in the background."""
    await check_budget(store)

    game_id = uuid.uuid4().hex[:16]
    job = Job(game_id=game_id, simulated=settings.llm_mode == "mock")
    _jobs[game_id] = job

    if job.simulated:
        state, script = build_mock_game(game_id, req)
        if state.safety_class == "blocked":
            _jobs.pop(game_id, None)
            raise AppError("blocked_event", "this event is not playable")
        await _persist(store, uid, state, script)
        await store.put_style_card(uid, game_id, state.style_card)
        job.finish()
        _forget_later(game_id)
        return game_id

    task = asyncio.create_task(_run(store, uid, req, job))
    task.add_done_callback(lambda _: None)
    return game_id


async def await_scenes(game_id: str, timeout: float = SCENE_WAIT_SECONDS) -> bool:
    """Block until this game's scenes exist. True if they do.

    Returns immediately for any game whose scenes were never deferred, which
    is every mock game and every game this process did not generate.
    """
    gate = _scene_gates.get(game_id)
    if gate is None:
        return True
    try:
        async with asyncio.timeout(timeout):
            await gate.wait()
    except TimeoutError:
        log.warning("scenes for %s did not arrive in %.0fs", game_id, timeout)
        return False
    return True


async def _run(store: GameStore, uid: str, req: NewGameRequest, job: Job) -> None:
    try:
        async with asyncio.timeout(GENERATION_TIMEOUT_SECONDS):
            await _generate(store, uid, req, job)
    except AppError as exc:
        job.fail(exc)
    except TimeoutError:
        log.exception("generation timed out for %s", job.game_id)
        job.fail(AppError("generation_failed", "generation took too long"))
    except Exception as exc:
        log.exception("generation failed for %s", job.game_id)
        job.fail(AppError("generation_failed", str(exc)))
    finally:
        _forget_later(job.game_id)


async def _generate(store: GameStore, uid: str, req: NewGameRequest, job: Job) -> None:
    llm = make_llm()
    job.usage = llm.usage
    assets = get_assets()

    if req.mode == "news":
        from app.pipeline import news_game

        opened = await news_game.build(
            llm, assets, game_id=job.game_id, req=req, uid=uid, store=store, progress=job.emit
        )
    else:
        from app.pipeline import idea_game

        opened = await idea_game.build(
            llm, assets, game_id=job.game_id, req=req, uid=uid, store=store, progress=job.emit
        )

    if opened.state.safety_class == "blocked":
        raise AppError("blocked_event", "this event is not playable")

    await _persist(store, uid, opened.state, opened.script)
    await store.put_style_card(uid, job.game_id, opened.state.style_card)
    await _report_spend(store, llm, job)
    log.info("game %s opened: %s", job.game_id, llm.usage.summary())

    # The player now reads the premise and walks, which is fifteen to twenty
    # seconds nobody was using. Everything else is written into that.
    _scene_gates[job.game_id] = asyncio.Event()
    job.finish()
    job.background = asyncio.create_task(_after_open(store, uid, llm, assets, job, opened))


async def _report_spend(store: GameStore, llm: LLM, job: Job) -> None:
    """Charge only what has been spent since the last report.

    The usage counter accumulates across the whole game, including the
    background work, so reporting it whole every time would bill the opening
    stages once per phase.
    """
    delta = llm.usage.usd - job.spent
    job.spent = llm.usage.usd
    if delta > 0:
        await store.add_spend(delta)


async def _after_open(
    store: GameStore,
    uid: str,
    llm: LLM,
    assets: AssetStore,
    job: Job,
    opened: live.OpenedGame,
) -> None:
    """Scenes first, then images: the player needs words before pictures."""
    gate = _scene_gates.get(job.game_id)
    try:
        await live.fill_scenes(
            llm, opened.script, opened.plan, opened.style, safety_class=opened.safety_class
        )
        await store.put_script(uid, opened.script)
        await _report_spend(store, llm, job)
    finally:
        # Released even on failure: `fill_scenes` leaves a playable fallback,
        # and a gate that never opened would hang every move until it timed out.
        if gate is not None:
            gate.set()

    try:
        filled = await live.fill_images(
            llm, assets, opened.script, opened.plan.locations, opened.state.style_card
        )
        if filled:
            await store.put_script(uid, opened.script)
            log.info("filled %d location images for %s", filled, job.game_id)
    except Exception:
        log.exception("background image fill failed for %s", job.game_id)
    finally:
        await _report_spend(store, llm, job)


async def _persist(store: GameStore, uid: str, state: GameState, script: GameScript) -> None:
    await asyncio.gather(store.put_state(uid, state), store.put_script(uid, script))


async def finish_ending(
    store: GameStore, uid: str, state: GameState, script: GameScript
) -> EndingComparison:
    """Write the ending once, the first time the player reaches it.

    The placeholder built at generation time is what a half-played game shows
    in the library; this replaces it with something that has actually read the
    turn log.
    """
    if script.ending_final or script.plan is None or settings.llm_mode == "mock":
        return script.ending

    llm = make_llm()
    try:
        script.ending = await ending_stage.write_ending(
            llm, state=state, script=script, plan=script.plan
        )
        script.ending_final = True
    except GenerationError:
        # Keep the placeholder rather than failing the last screen of a run
        # the player has already finished.
        log.exception("ending generation failed for %s", script.game_id)
    finally:
        await store.add_spend(llm.usage.usd)
    return script.ending


def played_at_now() -> str:
    return datetime.now(UTC).isoformat()


async def stream_progress(game_id: str) -> AsyncIterator[dict[str, str]]:
    """SSE events for the loading screen: `stage` several times, then `ready`.

    A job that has already finished replays its stages instantly, so a client
    that reconnects mid-load is not left staring at a blank screen.
    """
    job = _jobs.get(game_id)
    if job is None:
        # Nothing in flight: either the game is long since built, or this id
        # was never ours. Either way the client should go and look.
        yield _frame_ready()
        return

    if job.simulated:
        async for frame in _simulated():
            yield frame
        return

    index = 0
    while True:
        tick = job.tick
        while index < len(job.stages):
            yield {"event": "stage", "data": json.dumps({"stage": job.stages[index]})}
            index += 1
        if job.done.is_set():
            break
        await tick.wait()

    if job.error is not None:
        yield {
            "event": "error",
            "data": json.dumps({"kind": job.error.kind, "detail": job.error.detail}),
        }
        return
    yield _frame_ready()


def _frame_ready() -> dict[str, str]:
    return {"event": "ready", "data": json.dumps({"ready": True})}


async def _simulated() -> AsyncIterator[dict[str, str]]:
    for stage, delay in STAGE_SCRIPT:
        yield {"event": "stage", "data": json.dumps({"stage": stage})}
        if settings.mock_stage_scale:
            await asyncio.sleep(delay * settings.mock_stage_scale)
    yield _frame_ready()
