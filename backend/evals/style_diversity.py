"""Does the style card actually vary, or does it collapse to a house style?

This is the risk the style system exists to answer, and it is not something a
unit test can settle: a sampler that returned the same genre nineteen times
out of twenty would pass every assertion about its type and still make every
game read alike. So the measurement is *entropy* - how evenly a player's
twenty runs spread across each axis, normalised against the best a draw of
that size could do.

The sampling is done the way a real player experiences it: twenty games in a
row, each draw seeing the five before it, because the anti-repetition rule is
part of what produces the spread and evaluating the raw sampler without it
would measure something nobody plays.
"""

from collections import Counter
from math import log
from random import Random

from app.models.game import SafetyClass, StyleCard
from app.pipeline.style_card import (
    HISTORY_DEPTH,
    MAX_SHARED_AXES,
    pool_for,
    sample_style_card,
)
from app.pipeline.style_catalog import AXES, CATALOG, SAFE_ROLES
from evals.harness import Case, Context, check

#: The plan's number: "axis entropy across 20 runs".
RUN_LENGTH = 20

#: Normalised entropy an axis must reach. A perfectly uniform draw of this
#: size scores close to 1.0; a sampler stuck on one value scores 0.0. The bar
#: is set below 1.0 because twenty draws over eight values cannot be even.
MIN_ENTROPY = 0.85

#: News mode narrows the protagonist to roles the event could contain.
NEWS_ROLES = {"witness", "journalist", "official"}


def _session(
    rng: Random,
    *,
    safety_class: SafetyClass = "allowed",
    allowed_roles: set[str] | None = None,
) -> list[StyleCard]:
    """Twenty consecutive games by one player, newest last."""
    drawn: list[StyleCard] = []
    for _ in range(RUN_LENGTH):
        drawn.append(
            sample_style_card(
                safety_class=safety_class,
                recent=drawn[::-1][:HISTORY_DEPTH],
                allowed_roles=allowed_roles,
                rng=rng,
            )
        )
    return drawn


def _entropy(values: list[str], pool: int) -> float:
    """Shannon entropy over the observed values, normalised to [0, 1].

    Normalised against `log(min(pool, n))` rather than `log(pool)`: with more
    values in the catalog than draws in the session, perfect spread still
    cannot touch every value, and scoring against the unreachable maximum
    would penalise a sampler for the length of the session.
    """
    ceiling = min(pool, len(values))
    if ceiling <= 1:
        return 1.0
    total = len(values)
    observed = -sum((c / total) * log(c / total) for c in Counter(values).values())
    return observed / log(ceiling)


def _spread(cards: list[StyleCard], label: str, safety_class: SafetyClass) -> list[Case]:
    cases = []
    for axis in AXES:
        # The pool the sampler actually drew from, both gates applied - not
        # the catalog. Scoring safe mode against the full catalog would mark
        # the safety gate down as a diversity failure.
        pool = len(pool_for(axis, safety_class))
        score = _entropy([getattr(c, axis) for c in cards], pool)
        cases.append(
            check(
                f"{label}/entropy/{axis}",
                score >= MIN_ENTROPY,
                f"normalised entropy {score:.2f} over {pool} values, need {MIN_ENTROPY:.2f}",
            )
        )
        # Entropy says the draws are balanced; coverage says they reach the
        # whole catalog. A sampler favouring five of eight genres evenly would
        # score well on the first and badly on this.
        seen = len({getattr(c, axis) for c in cards})
        want = min(pool, len(cards))
        cases.append(
            check(f"{label}/coverage/{axis}", seen == want, f"{seen} of {want} values used")
        )
    return cases


def _anti_repetition(cards: list[StyleCard], label: str) -> list[Case]:
    """The rule itself: no draw may share two axes with the five before it."""
    cases = []
    for index, card in enumerate(cards):
        worst = 0
        for old in cards[max(0, index - HISTORY_DEPTH) : index]:
            worst = max(worst, sum(1 for a in AXES if getattr(card, a) == getattr(old, a)))
        cases.append(
            check(
                f"{label}/no-repeat/{index:02d}",
                worst < MAX_SHARED_AXES,
                f"shares {worst} axes with a recent card, limit {MAX_SHARED_AXES - 1}",
            )
        )
    return cases


async def run(ctx: Context) -> list[Case]:
    cases: list[Case] = []
    for trial in range(ctx.samples):
        rng = ctx.rng(f"style/{trial}")

        allowed = _session(rng, safety_class="allowed")
        cases += _spread(allowed, f"allowed/{trial}", "allowed")
        cases += _anti_repetition(allowed, f"allowed/{trial}")

        safe = _session(rng, safety_class="safe_mode")
        cases += _spread(safe, f"safe/{trial}", "safe_mode")
        cases += _anti_repetition(safe, f"safe/{trial}")
        for index, card in enumerate(safe):
            unsafe = [
                axis
                for axis in AXES
                if not next(v.safe for v in CATALOG[axis] if v.id == getattr(card, axis))
            ]
            cases.append(
                check(
                    f"safe/{trial}/gate/{index:02d}",
                    not unsafe and card.protagonist_role in SAFE_ROLES,
                    f"unsafe on {unsafe or 'no axis'}, role {card.protagonist_role!r}",
                )
            )

        news = _session(rng, allowed_roles=NEWS_ROLES)
        for index, card in enumerate(news):
            cases.append(
                check(
                    f"news-roles/{trial}/{index:02d}",
                    card.protagonist_role in NEWS_ROLES,
                    f"role {card.protagonist_role!r} is not one this event could contain",
                )
            )
    return cases
