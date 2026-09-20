"""Sampling a style card, and turning one into prompt text.

The card is drawn from enum ids only - no model call, no cost, no latency -
and then threaded into every downstream stage. Two constraints shape the draw:

* **the safety gate**, which removes values that read badly over a real
  tragedy (and, in safe mode, restricts who the protagonist is allowed to be);
* **per-player anti-repetition**, which rejects a draw that shares two or more
  axis values with any of *this* player's last few games. There is deliberately
  no global check: two strangers drawing the same card is not a problem, and
  making it one would mean every player's variety depended on everyone else's.
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
MAX_RESAMPLES = 10


def _pool(axis: Axis, safety_class: SafetyClass) -> tuple[Value, ...]:
    values = CATALOG[axis]
    if safety_class != "safe_mode":
        return values
    values = tuple(v for v in values if v.safe)
    if axis == "protagonist_role":
        values = tuple(v for v in values if v.id in SAFE_ROLES)
    return values


def default_card(safety_class: SafetyClass) -> StyleCard:
    """The first legal value on every axis - a card that is always allowed.

    Used when resampling keeps colliding with the player's history, which is
    what happens once a pool is small enough that repetition is unavoidable.
    """
    return StyleCard(**{axis: _pool(axis, safety_class)[0].id for axis in AXES})


def _shared(card: StyleCard, other: StyleCard) -> int:
    return sum(1 for axis in AXES if getattr(card, axis) == getattr(other, axis))


def _draw(rng: Random, safety_class: SafetyClass) -> StyleCard:
    return StyleCard(**{axis: rng.choice(_pool(axis, safety_class)).id for axis in AXES})


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

    card = _draw(rng, safety_class)
    for _ in range(MAX_RESAMPLES):
        if allowed_roles and card.protagonist_role not in allowed_roles:
            legal = [v.id for v in _pool("protagonist_role", safety_class) if v.id in allowed_roles]
            if legal:
                card = card.model_copy(update={"protagonist_role": rng.choice(legal)})
        if all(_shared(card, old) < MAX_SHARED_AXES for old in history):
            return card
        card = _draw(rng, safety_class)

    # Every draw collided. Repetition is now unavoidable, so take the last one
    # rather than serving the same fallback card to a player over and over.
    if allowed_roles and card.protagonist_role not in allowed_roles:
        legal = [v.id for v in _pool("protagonist_role", safety_class) if v.id in allowed_roles]
        if legal:
            card = card.model_copy(update={"protagonist_role": legal[0]})
        else:
            return default_card(safety_class)
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
