"""Sampling a style card, and turning one into prompt text.

The card is drawn from enum ids only - no model call, no cost, no latency -
and then threaded into every downstream stage. Two constraints shape the draw:

* **the safety gate**, which removes values that read badly over a real
  tragedy (and, in safe mode, restricts who the protagonist is allowed to be);
* **per-player anti-repetition**, which rejects a draw that shares two or more
  axis values with any of *this* player's last few games. There is deliberately
  no global check: two strangers drawing the same card is not a problem, and
  making it one would mean every player's variety depended on everyone else's.

The draw avoids what the player has recently seen *per axis* rather than
drawing uniformly and rejecting collisions afterwards, and that is not a
refinement - it is the only way the rule holds. Measured: seven axes over
pools of three to eight values mean two uniform cards share two or more axes
**40%** of the time, so a draw acceptable against five recent cards comes up
only 8% of the time, and rejection sampling fell through to its escape hatch
on nearly half of all draws. Drawing from the values a player has not seen
lately makes most axes collision-free by construction and leaves rejection to
handle the few axes too small to be fresh.
"""

from random import Random

from app.models.game import Language, SafetyClass, StyleCard
from app.pipeline.style_catalog import (
    AXES,
    CATALOG,
    SAFE_ROLES,
    Axis,
    Value,
    fragment,
    label,
)

#: How many of the player's recent cards the anti-repetition check looks at.
HISTORY_DEPTH = 5
#: A draw sharing this many axis values with a recent card is rejected.
MAX_SHARED_AXES = 2
#: Give up and take the last draw rather than loop forever on a small pool.
#: Forty rather than ten because safe mode shrinks every pool at once, which
#: pushes the per-draw collision rate to about 0.7; ten tries left three runs
#: in a hundred repeating, and this is a few hundred microseconds of pure
#: arithmetic with no I/O behind it.
MAX_RESAMPLES = 40


def pool_for(
    axis: Axis,
    safety_class: SafetyClass = "allowed",
    allowed_roles: set[str] | None = None,
) -> tuple[Value, ...]:
    """Every value this axis is allowed to take, under both gates.

    A role gate that admits nothing is ignored rather than honoured: News mode
    supplies roles a model chose for the event, and an empty intersection is a
    scoring mistake, not an instruction to ship a game with no protagonist.
    """
    values = CATALOG[axis]
    if safety_class == "safe_mode":
        values = tuple(v for v in values if v.safe)
        if axis == "protagonist_role":
            values = tuple(v for v in values if v.id in SAFE_ROLES)
    if axis == "protagonist_role" and allowed_roles:
        values = tuple(v for v in values if v.id in allowed_roles) or values
    return values


def default_card(safety_class: SafetyClass) -> StyleCard:
    """The first legal value on every axis - a card that is always allowed."""
    return StyleCard(**{axis: pool_for(axis, safety_class)[0].id for axis in AXES})


def _shared(card: StyleCard, other: StyleCard) -> int:
    return sum(1 for axis in AXES if getattr(card, axis) == getattr(other, axis))


def _draw(
    rng: Random,
    safety_class: SafetyClass,
    history: list[StyleCard],
    allowed_roles: set[str] | None,
) -> StyleCard:
    """One value per axis, preferring what this player has not seen lately.

    An axis whose whole pool is in the history - `pacing` has three values and
    the history holds five cards - falls back to the full pool, because the
    alternative is refusing to deal a card at all.
    """
    values = {}
    for axis in AXES:
        pool = pool_for(axis, safety_class, allowed_roles)
        seen = {getattr(card, axis) for card in history}
        fresh = tuple(v for v in pool if v.id not in seen)
        values[axis] = rng.choice(fresh or pool).id
    return StyleCard(**values)


def sample_style_card(
    *,
    safety_class: SafetyClass = "allowed",
    recent: list[StyleCard] | None = None,
    allowed_roles: set[str] | None = None,
    rng: Random | None = None,
) -> StyleCard:
    """Draw a card, honouring the safety gate and the player's recent history.

    `allowed_roles` narrows `protagonist_role` further still - News mode uses
    it to keep the player in a role the actual event could plausibly contain.
    """
    rng = rng or Random()
    history = (recent or [])[:HISTORY_DEPTH]

    card = _draw(rng, safety_class, history, allowed_roles)
    for _ in range(MAX_RESAMPLES):
        if all(_shared(card, old) < MAX_SHARED_AXES for old in history):
            return card
        card = _draw(rng, safety_class, history, allowed_roles)

    # Every draw collided, which means the pools left after both gates are
    # too small to avoid it. The last draw is still as fresh as the catalog
    # allows on every axis, so it beats serving one fixed fallback card to a
    # player over and over.
    return card


def style_prompt(card: StyleCard) -> str:
    """The card as instructions for a text stage."""
    return "\n".join(
        f"- {axis.replace('_', ' ')}: {fragment(axis, getattr(card, axis))}"
        for axis in AXES
        if axis != "visual_style"
    )


def visual_prompt(card: StyleCard) -> str:
    """The card's visual half, for an image prompt. Always English."""
    return fragment("visual_style", card.visual_style)


def music_prompt(card: StyleCard) -> str:
    return fragment("music_mood", card.music_mood)


def describe(card: StyleCard, language: Language) -> list[tuple[str, str]]:
    """`(axis id, localized label)` pairs, for the ending screen."""
    return [(axis, label(axis, getattr(card, axis), language)) for axis in AXES]
