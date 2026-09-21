"""The ending: what the run became, and - in News mode - how close it stayed.

This is the one stage that cannot be pregenerated, because it is the only one
that has seen what the player actually did. It runs once, when the player
finishes, and its result is what the library and the replay are titled after.

Idea mode gets no match score. There is nothing to be right about: the plan
was a suggestion the story was free to leave, and scoring a player against a
story that was invented for them would be scoring them against a coin toss.
"""

from app.llm.base import LLM, GenerationError
from app.models.game import (
    CanonBeat,
    EndingComparison,
    GameState,
    Language,
    Mode,
    PlayerBeat,
    SourceLink,
    StyleCard,
    StyleLabel,
)
from app.models.plan import EndingDraft, StoryPlan
from app.models.script import GameScript
from app.pipeline.prompts import SAFE_MODE_RULE, language_rule, style_block
from app.pipeline.style_card import describe, style_prompt

STAGE = "ending"


def _instructions(language: Language, mode: Mode, safe: bool) -> str:
    comparison = (
        "This story is based on a real event, and the player's run may have "
        "diverged from it. Say plainly where it went the same way and where it "
        "did not, without scolding the player for the difference."
        if mode == "news"
        else "This story was invented for this player. There is no correct "
        "version of it, so do not tell them what they should have done."
    )
    safety = f"\n\nSAFETY:\n{SAFE_MODE_RULE}" if safe else ""
    return f"""You write the closing page of a short interactive story the player has \
just finished.

{language_rule(language)}

Return:
- `title`: 2 to 5 words naming this particular run, not the story in general.
- `summary`: 4 to 6 sentences on what the player's run became - the shape of it, what \
they chose to do, and where it left things. Address the player directly. Do not list \
the choices back; tell it as a story. {comparison}
- `player_beats`: one entry per planned beat, in order, with its `beat_index`, a \
`what_you_did` of one sentence saying what the player actually did at that point, and \
`matched` set to whether their run went that way at all.{safety}"""


def _transcript(plan: StoryPlan, script: GameScript) -> str:
    lines = [f"TITLE: {plan.title}", f"PREMISE: {plan.premise}", "", "THE PLANNED BEATS:"]
    for index, beat in enumerate(plan.beats):
        lines.append(f"{index}. {beat.title}: {beat.summary}")

    lines += ["", "WHAT THE PLAYER DID, IN ORDER:"]
    for turn, choice_id in zip(script.turns, script.taken, strict=False):
        where = next(
            (loc.name for loc in plan.locations if loc.id == turn.scene.location_id),
            turn.scene.location_id,
        )
        outcome = script.outcomes.get(choice_id)
        note = f" ({outcome.consequence})" if outcome and outcome.consequence else ""
        drift = "" if outcome is None or outcome.on_canon else " [away from the plan]"
        lines.append(f'- at {where}: chose "{turn.chosen}"{note}{drift}')
        if turn.answer:
            lines.append(f'  and wrote: "{turn.answer}"')

    unvisited = [
        loc.name
        for loc in plan.locations
        if not any(t.scene.location_id == loc.id for t in script.turns)
    ]
    if unvisited:
        lines += ["", "NEVER REACHED: " + ", ".join(unvisited)]
    return "\n".join(lines)


def match_score(state: GameState) -> float:
    """Order-weighted fraction of beats the run actually hit.

    Later beats count for more, because reaching the end of a real event the
    way it went is a stronger result than getting its opening right.
    """
    if not state.beat_progress:
        return 0.0
    total = 0.0
    hit = 0.0
    for index, beat in enumerate(state.beat_progress):
        weight = index + 1
        total += weight
        if beat.status == "matched":
            hit += weight
    return round(hit / total, 3) if total else 0.0


def placeholder_ending(
    game_id: str, plan: StoryPlan, style: StyleCard, mode: Mode
) -> EndingComparison:
    """Stands in until the player finishes, so an abandoned run still has a title."""
    return EndingComparison(
        game_id=game_id,
        mode=mode,
        title=plan.title,
        summary=plan.premise,
        canon=canon_of(plan) if mode == "news" else [],
        style_card=style,
        style_labels=style_labels(style, plan.language),
        sources=sources_of(plan),
    )


def style_labels(style: StyleCard, language: Language) -> list[StyleLabel]:
    return [StyleLabel(axis=axis, label=text) for axis, text in describe(style, language)]


def canon_of(plan: StoryPlan) -> list[CanonBeat]:
    return [
        CanonBeat(id=b.id, title=b.title, summary=b.summary, sources=b.sources) for b in plan.beats
    ]


def sources_of(plan: StoryPlan) -> list[SourceLink]:
    seen: dict[str, SourceLink] = {}
    for beat in plan.beats:
        for url in beat.sources:
            seen.setdefault(url, SourceLink(url=url, title=beat.title))
    return list(seen.values())


async def write_ending(
    llm: LLM,
    *,
    state: GameState,
    script: GameScript,
    plan: StoryPlan,
) -> EndingComparison:
    draft = await llm.json(
        STAGE,
        f"{style_block(style_prompt(state.style_card))}\n\n{_transcript(plan, script)}",
        EndingDraft,
        system=_instructions(state.story_language, state.mode, state.safety_class == "safe_mode"),
        temperature=0.9,
    )
    return assemble(draft, state=state, plan=plan)


def assemble(draft: EndingDraft, *, state: GameState, plan: StoryPlan) -> EndingComparison:
    status = {b.beat_id: b.status for b in state.beat_progress}
    by_index = {d.beat_index: d for d in draft.player_beats}

    player: list[PlayerBeat] = []
    for index, beat in enumerate(plan.beats):
        item = by_index.get(index)
        recorded = status.get(beat.id, "pending")
        player.append(
            PlayerBeat(
                beat_id=beat.id,
                # What the run recorded wins over what the model says about it:
                # the engine was there and the model is inferring.
                status=recorded if recorded != "pending" else "skipped",
                what_you_did=(item.what_you_did.strip() if item else "")
                or _not_reached(state.story_language),
            )
        )

    if not draft.title.strip():
        raise GenerationError("the ending came back without a title")

    return EndingComparison(
        game_id=state.game_id,
        mode=state.mode,
        match_score=match_score(state) if state.mode == "news" else None,
        title=draft.title.strip(),
        summary=draft.summary.strip(),
        canon=canon_of(plan) if state.mode == "news" else [],
        player=player,
        style_card=state.style_card,
        style_labels=style_labels(state.style_card, state.story_language),
        sources=sources_of(plan),
    )


def _not_reached(language: Language) -> str:
    return "Nie dotarłeś tam." if language == "pl" else "You never got there."
