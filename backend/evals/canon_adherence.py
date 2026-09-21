"""Does the match score mean what the ending screen says it means?

News mode's whole claim is that the number at the end reflects how closely the
player's run followed what actually happened. That claim is only worth making
if the score is *ordered*: following the canon must beat half-following it,
which must beat ignoring it, and hitting the last beat must count for more
than hitting the first. None of that is visible from a single run, so this
plays the same built game several ways and compares the results against each
other rather than against a constant.

The runs are real: the same turn engine the server uses, walking the same
generated map, resolving the same beats. Only the model underneath is fake.
"""

from app.llm.fake import FakeLLM
from evals import fixtures as fx
from evals.harness import Case, Context, check, equals

#: One event per trial, so a trial is a different story rather than a
#: different seed over the same one.
EVENTS = (
    "SpaceX lands a booster on the drone ship after night launch",
    "Brawl in the Sejm as opposition MPs storm the rostrum",
    "Divers reach the wreck and recover the ship's bell",
    "City council votes through the tram extension after a long night",
    "Researchers confirm the comet will pass closer than expected",
    "Striking dockers march to the port gate and hold it until dawn",
)

IDEAS = (
    "a lighthouse keeper finds the lamp already lit",
    "the last train of the night does not stop where it should",
    "someone inherits a house with one room they cannot enter",
)


async def _news_run(event_title: str, strategy_for) -> tuple:
    """Build once, then play the same game to the end with one strategy."""
    llm = FakeLLM()
    opened = await fx.open_news(llm, fx.make_event(event_title))
    count = len(fx.destination_positions(opened.state))
    state, ending = await fx.played_ending(llm, opened, strategy_for(count))
    return state, ending


async def run(ctx: Context) -> list[Case]:
    cases: list[Case] = []

    for title in EVENTS[: max(1, ctx.samples)]:
        label = title.split()[0].lower()

        canon, canon_end = await _news_run(title, lambda _n: fx.follow_canon)
        astray, astray_end = await _news_run(title, lambda _n: fx.leave_canon)
        mixed, mixed_end = await _news_run(title, lambda _n: fx.alternate)
        _, last_end = await _news_run(title, fx.only_last)
        _, first_end = await _news_run(title, fx.only_first)

        cases += [
            check(f"{label}/finishes", canon.finished, "the run never reached its ending"),
            equals(f"{label}/canon/score", canon_end.match_score, 1.0),
            equals(f"{label}/canon/divergence", canon.divergence, 0.0),
            check(
                f"{label}/canon/every-beat-matched",
                all(b.status == "matched" for b in canon.beat_progress),
                str([(b.beat_id, b.status) for b in canon.beat_progress]),
            ),
            equals(f"{label}/astray/score", astray_end.match_score, 0.0),
            equals(f"{label}/astray/divergence", astray.divergence, 1.0),
            check(
                f"{label}/astray/every-beat-diverged",
                all(b.status == "diverged" for b in astray.beat_progress),
                str([(b.beat_id, b.status) for b in astray.beat_progress]),
            ),
            check(
                f"{label}/ordered",
                (canon_end.match_score or 0)
                > (mixed_end.match_score or 0)
                > (astray_end.match_score or 0),
                f"canon {canon_end.match_score}, mixed {mixed_end.match_score}, "
                f"astray {astray_end.match_score}",
            ),
            check(
                f"{label}/later-beats-weigh-more",
                (last_end.match_score or 0) > (first_end.match_score or 0),
                f"last beat only {last_end.match_score}, first beat only {first_end.match_score}",
            ),
            check(
                f"{label}/nothing-left-pending",
                not any(b.status == "pending" for b in mixed.beat_progress),
                str([(b.beat_id, b.status) for b in mixed.beat_progress]),
            ),
            equals(
                f"{label}/player-beats-cover-the-plan",
                len(mixed_end.player),
                len(mixed.beat_progress),
            ),
            check(
                f"{label}/canon-is-shown-with-sources",
                bool(canon_end.canon) and all(b.sources for b in canon_end.canon),
                f"{len(canon_end.canon)} canon beats, "
                f"{sum(1 for b in canon_end.canon if b.sources)} with sources",
            ),
            check(
                f"{label}/ending-cites-the-reporting",
                bool(canon_end.sources),
                "the ending screen carries no source links",
            ),
        ]

    # Idea mode has no canon, so it must not produce a number that looks like
    # one. This is the other half of the claim: the score is absent, not zero.
    for idea in IDEAS[: max(1, min(ctx.samples, len(IDEAS)))]:
        llm = FakeLLM()
        opened = await fx.open_idea(llm, idea=idea)
        state, ending = await fx.played_ending(llm, opened, fx.leave_canon)
        label = f"idea/{idea.split()[1]}"
        cases += [
            check(f"{label}/no-match-score", ending.match_score is None, str(ending.match_score)),
            check(f"{label}/no-canon-shown", not ending.canon, f"{len(ending.canon)} canon beats"),
            check(f"{label}/still-finishes", state.finished, "the run never reached its ending"),
            check(
                f"{label}/still-recounts-every-beat",
                len(ending.player) == len(opened.plan.beats),
                f"{len(ending.player)} of {len(opened.plan.beats)}",
            ),
        ]
    return cases
