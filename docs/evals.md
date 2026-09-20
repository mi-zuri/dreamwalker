# Evals

```bash
make eval          # every dimension, offline, free
make eval-live     # the two a real model can be judged on. Spends money.
```

Roughly a thousand graded cases in under a second, no network, no spend.

## Why this is not the test suite

`backend/tests/` asserts invariants: one failure is a red build. The evals in
`backend/evals/` **measure** things that are allowed to be imperfect and report
a rate against a threshold.

The distinction earns its keep in exactly one place — style diversity. A
sampler that returned the same genre nineteen times in twenty would pass every
assertion anyone would think to write about its type, its range and its safety
gate, and would still make every game read alike. What catches that is a
number, taken over enough draws to mean something.

The unit is a **case**: one graded observation with a name. A dimension
produces many; the runner counts them; the report is the artifact.

## The four dimensions

| Dimension | Cases | Threshold | What it measures |
|---|---:|---:|---|
| `style-diversity` | ~540 | 99% | Axis entropy and catalog coverage across a player's 20 runs, plus the anti-repetition rule itself |
| `canon-adherence` | ~77 | 100% | The match score is ordered, weighted towards later beats, and absent in Idea mode |
| `safe-mode` | ~78 | 100% | Fourteen headlines classify correctly, and the pipeline honours the answer |
| `language` | ~263 | 100% | Every player-facing string is in the story language; image prompts are not |

### `style-diversity`

Simulates a player's twenty consecutive games, each draw seeing the five
before it, because the anti-repetition rule is part of what produces the
spread and measuring the raw sampler without it would measure something nobody
plays. Per axis it scores **normalised Shannon entropy** — a uniform draw
scores near 1.0, a sampler stuck on one value scores 0.0 — and **coverage**,
how much of the catalog twenty runs actually reach. Entropy says the draws are
balanced; coverage says they are not balanced across a favourite five of
eight.

Entropy is normalised against `log(min(pool, 20))`, not `log(pool)`: with more
values in the catalog than draws in a session, perfect spread still cannot
touch every value, and scoring against an unreachable maximum would penalise
the sampler for the length of the session. Safe mode is scored against the
pool *after* both gates, so the safety filter is not counted as a diversity
failure.

**The threshold is 99%, not 100%, and the missing percent is measured rather
than guessed.** Two tails are real behaviour: safe mode shrinks `pacing` to
three values against a five-card history, so about one draw in four hundred
cannot avoid repeating; and twenty draws over eight genres can miss one by
luck. A threshold of 100% would only mean the suite flakes.

### `canon-adherence`

Builds one News game and then plays it to the end five different ways —
always on canon, never on canon, alternating, last beat only, first beat only
— through the real turn engine on the real generated map. The assertions are
*relative*, because that is what the ending screen actually claims: following
the canon must beat half-following it, which must beat ignoring it, and
hitting the last beat must count for more than hitting the first.

It also checks the other half of the claim: Idea mode produces no match score
at all. Not zero — absent. There is nothing to be right about.

### `safe-mode`

Two separate questions, deliberately not conflated.

**Does the classifier get it right?** That is about a model. Offline it runs
against `FakeLLM`'s keyword scorer, which tells you the scoring prompt is
wired up and the pipeline reads the answer, and tells you nothing about
judgement. `--live` runs the same headlines through Vertex and gives the
number that matters.

**Does the pipeline honour the answer?** That is our own code and is fully
measurable offline: a blocked event never enters the pool, a safe-mode event
carries a content note and a restricted role, the restraint rule reaches every
prompt that writes prose, an allowed event does not carry it, and a private
individual's name is gone before any prompt can see it.

The headline set extends the six cases in [safety.md](safety.md) with
rephrasings and near neighbours, because a classifier that only works on the
exact wording of a design document is not a classifier.

**A classification stricter than expected is graded as a pass**, and the
detail always records the disagreement. That is a judgement about what the
dimension is for, not a way of flattering the number: refusing to make a game
of something we would have allowed costs a player one story, while making a
game of something we should have refused is the failure the whole stage exists
to prevent. The two are not the same size. A *looser* classification fails.

Measured live against `gemini-3.5-flash-lite` on 2026-09-20: **14 of 14**, one
of them stricter than the design expected — the terror attack naming victims
came back `blocked` rather than `safe_mode`, on the grounds of ongoing trauma
and privacy. That is a defensible reading and the eval reports it as one.

### `language`

Six combinations — both modes, both story languages, and the two settings
crossed, because `story_language` and `ui_language` are independent. For each
it builds a game, plays it to the end and checks **every** string a player
reads: the premise, each scene, each choice, each open question, the ending
title and summary, each player beat, and every style label. Then the two
places where the story language deliberately does not apply: image prompts,
which are always English, and the no-text rule attached to each one.

Language is detected with disjoint function-word lists rather than a
language-id dependency; two languages, both known in advance, is not a
modelling problem. Every short word that exists in both is left out on
purpose. `"What do you do?"` scored as Polish on the strength of two `do`s
until they were.

Offline, the prose comes from `FakeLLM`, so what is measured is the plumbing —
that the right instruction reaches every stage and the right language comes
back through every field. That is why `FakeLLM`'s vocabulary is a real Polish
translation rather than English with a language tag.

## Offline and live

`--live` swaps in Vertex for the dimensions marked live-capable and skips the
cases that read prompts rather than output. CI never passes it. `make eval` is
the one in the build; `make eval-live` is a thing a person runs on purpose.

## What the first run found

Worth recording, because it is the argument for having written this at all.

**The anti-repetition rule was failing on nearly half of all draws.** Seven
axes over pools of three to eight values mean two uniform cards share two or
more axes 40% of the time; a draw acceptable against five recent cards comes
up only 8% of the time; and ten rejection-sampling attempts therefore all
collided on 45% of draws, falling through to the escape hatch. The rule the
design advertises was not being delivered. The sampler now draws per axis from
the values the player has *not* seen lately, which makes most axes
collision-free by construction; measured violations went from 45% to 0% in
normal play and 0.26% in safe mode.

The live classifier was also run for the first time here, and it agreed with
the design on thirteen of fourteen headlines, disagreeing only by being
stricter — see `safe-mode` above.

Two smaller ones, both in map repair — the one part of the system that is
supposed to never fail: a duplicated door record made the repair erase a
legitimate door tile and then throw, and a grid that shipped fewer rows than
it declared was padded without the change being logged.

## Adding a dimension

One module in `backend/evals/` with `async def run(ctx) -> list[Case]`, and an
entry in `DIMENSIONS` in `backend/evals/__init__.py` naming its threshold.
`ctx.model()` gives the model, `ctx.rng(salt)` gives a generator that is stable
per dimension — salted by name so that adding one does not shift the numbers
of every dimension after it, which would make two reports incomparable for a
reason having nothing to do with the code under evaluation.
