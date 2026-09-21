"""Offline evaluation suite.

Four dimensions, each measuring one risk the design took on:

* **style-diversity** - the risk that every game reads alike;
* **canon-adherence** - the risk that the match score is a decoration;
* **safe-mode** - the risk that restraint is claimed in a prompt and not
  enforced anywhere;
* **language** - the risk that a Polish game is Polish in most places.

`python -m evals` runs them all, free and offline, and reports a pass rate per
dimension. `--live` swaps in Vertex for the dimensions where a real model is
the thing under evaluation, and costs money.
"""

from evals import canon_adherence, language, safe_mode, style_diversity
from evals.harness import Dimension

DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        name="style-diversity",
        about="axis entropy across a player's 20 runs, and the anti-repetition rule",
        # Not 1.0, and the two per cent are measured rather than guessed. The
        # sampler avoids what a player has seen lately, so twenty runs almost
        # always reach every value on every axis and never repeat inside the
        # memory window - but "almost" is the honest word: safe mode shrinks
        # `pacing` to three values against a five-card history, and a run of
        # twenty draws over eight genres can miss one by luck. Both tails are
        # real behaviour, not defects, and a threshold of 1.0 would only mean
        # the suite flakes.
        threshold=0.99,
        run=style_diversity.run,
    ),
    Dimension(
        name="canon-adherence",
        about="the match score is ordered, weighted late, and absent in Idea mode",
        threshold=1.0,
        run=canon_adherence.run,
    ),
    Dimension(
        name="safe-mode",
        about="headlines classify correctly and the pipeline honours the answer",
        threshold=1.0,
        run=safe_mode.run,
        live_capable=True,
    ),
    Dimension(
        name="language",
        about="every player-facing string is in the story language; prompts are not",
        threshold=1.0,
        run=language.run,
        live_capable=True,
    ),
)

__all__ = ["DIMENSIONS"]
