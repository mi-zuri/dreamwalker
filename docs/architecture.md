# Architecture

How Dreamwalker is put together, and why it is put together that way. For the
decisions themselves, with the measurements behind them, see
[decisions.md](decisions.md); this is the map.

## The shape of it

```
browser ──HTTP──▶ FastAPI ──▶ pipeline ──▶ Vertex AI  (text, images, embeddings)
   │                 │            │
   │                 │            └──────▶ Firestore  (games, pool, spend)
   │                 │            └──────▶ Cloud Storage (images, turn logs)
   └──WebSocket──────┘ ─────────────────▶ Gemini API  (Lyria RealTime, music only)
```

One Cloud Run service serves the API *and* the built frontend. Firebase
Hosting would have been the obvious front door and was measured and rejected:
its rewrites do not carry a WebSocket upgrade, and the music socket is not
optional. Serving both from one origin also removes CORS entirely.

There is no `shared/` folder. `web/src/api/schema.d.ts` is generated from the
backend's own OpenAPI schema and CI fails on a diff, so the frontend cannot
drift from the contract.

## Directories

```
web/       React 19, Vite 7, TypeScript, Tailwind 4 (CSS-first), Zustand
backend/   FastAPI, Pydantic v2, uv-managed, Python 3.12+
  app/
    main.py          HTTP surface, SSE, the music socket, the SPA
    auth.py          Firebase ID token verification
    errors.py        the error contract both sides speak
    game/map.py      pure tile logic, mirrored in web/src/game/map.ts
    llm/             Vertex wrapper, FakeLLM, mock replay, image rate limit
    models/          Pydantic: game state, plan, script
    music/           Lyria session, captured loops, prompts
    news/            sources, clustering, scoring, enrichment, the pool
    pipeline/        every generation stage, the turn engine, the ending
    storage/         Firestore and in-memory, assets in GCS or memory
  evals/     graded measurements — see evals.md
  tests/     invariants
infra/     one Dockerfile, Terraform, the deploy script
```

## A game, end to end

`POST /api/games` returns an id immediately and generation continues behind
it. Holding an HTTP request open for ten seconds would make a proxy timeout
indistinguishable from a failure, so the loading screen reads progress from
`GET /api/games/{id}/stream` over SSE instead.

The whole shape of `pipeline/live.py` is dictated by one number: the player
should be looking at something within about eight seconds. The obvious
ordering — plan, map, five scenes, five images, start — is about twenty.

```
 plan ──▶ map ──▶ validate/repair ──▶ ┬─ scenes ─────────┐
  (1 call)  (free)     (free)         └─ opening image ──┴──▶ ready
                                                              │
                        the player reads the premise and walks │
                                                              ▼
                                            remaining location images
```

* **The plan** is the only call on the critical path nothing else can start
  without. It decides what the game *is* — title, premise, 1–5 locations,
  one beat each, how many open questions.
* **The map** is procedural and costs nothing. Destinations are the plan's
  locations in order; a location the plan marked `locked` becomes a door.
* **Scenes** are one batched call for every location at once, not one per
  location: five sequential calls would put four of them in front of the
  player, and a model writing all five together stops opening each with the
  same image.
* **Images** — the opening one is awaited briefly; the rest are filled while
  the player is reading and walking, which is fifteen to twenty seconds they
  were going to spend anyway.
* **The ending** is the one stage that cannot be pregenerated, because it is
  the only one that has seen what the player did. It runs once, when they
  finish.

### The turn engine

`pipeline/engine.py` is pure state transitions: no I/O, no model calls. The
client animates movement locally, but this is the authority — a move is
BFS-validated against the server's own copy of the map, so a move to a tile
the player cannot actually reach is ignored rather than trusted.

Which choice is "on canon" is decided at generation time and kept in the
server-side `GameScript`. The player sees three equal options; only the ending
knows which way the story leaned.

### Map validation and repair

`pipeline/map_validator.py` is a pure function over a grid. It checks
structure, BFS-reachability from the start, a fixpoint over locked doors, and
the walking budget. On failure the generator is re-prompted with structured
diagnostics, and after that a **deterministic repair** squares the grid off,
renames unusable keys, drops doors that cannot mean anything and carves
corridors to anything stranded. The repair always succeeds, so the loop is
bounded and there is no user-visible failure and no infinite regeneration.

## The two modes

They share everything after the brief.

**Idea mode** has no research step, no safety classification and no canon. The
player's sentence is the brief, quoted rather than paraphrased, and the style
card supplies what the sentence does not say.

**News mode** has to find an event this player has not seen, decide whether we
are willing to dramatize it at all, read it properly, and hand the plan stage
a factual brief plus a beat graph the run is measured against.

```
feeds ─▶ normalize ─▶ cluster ─▶ score ─▶ pool ─▶ pick ─▶ enrich ─▶ brief
```

* **Sourcing.** English Wikipedia Current Events for World, because it is an
  importance-filtered source and any past date is fetchable. Poland has no
  curated equivalent, so category feeds are used — they carry fewer items per
  hour and therefore reach further back than a firehose.
* **Scoring** is split. Importance is *computed* from the pool — how many
  outlets carried it, how many distinct ones, how recent — because those are
  facts we can count and a model asked to rate them would be guessing.
  Interest, playability and safety are *asked*, once, batched for a whole
  region.
* **The pool refreshes lazily.** A region that is already deep and recent
  costs nothing, which is what keeps an idle month at zero. A refresh needed
  by a player who can still be served happens behind them.
* **Enrichment is cached on the event**, so the second player to draw a story
  pays nothing for the dossier the first one paid for.
* **The canon beats come from the dossier, not the plan.** The plan decides
  where the player walks; what actually happened is not its to invent.
* **Dossiers stay in the source language.** The scene stage is told which
  language to write in and adapts inside a call it was making anyway, so there
  is no translation stage and no extra cost.

Divergence is tracked per turn; the ending's `match_score` is the
order-weighted fraction of beats the run actually hit, weighted towards the
later ones because reaching the end of a real event the way it went is a
stronger result than getting its opening right.

## Style cards

Sampled from seven axes of language-neutral enum ids, threaded into every
downstream prompt. The catalog in `pipeline/style_catalog.py` holds a Polish
label, an English label and one English prompt fragment per value — that split
is what makes style cards work identically in both languages: the fragment
says *how to write*, a separate instruction says *which language*.

Two constraints shape the draw: a **safety gate** that removes values reading
badly over a real tragedy, and **per-player anti-repetition** against the
player's last five cards. There is deliberately no global check — two
strangers drawing the same card is not a problem, and making it one would mean
every player's variety depended on everyone else's.

The draw avoids values the player has seen lately *per axis* rather than
drawing uniformly and rejecting collisions, which is not a refinement but the
only way the rule holds; see [evals.md](evals.md) for the measurement that
forced it.

## Language

`story_language` and `ui_language` are independent, and `story_language` is
independent of region — a Polish player can play World news in Polish. Every
generation stage is told the language explicitly and echoes a `language` field
back, which the orchestrator checks.

**Image prompts are always English**, with a mandatory clause forbidding text,
letters, numbers, signage and watermarks. Text on an image is the one failure
mode that would break the language setting in a way nothing downstream could
fix.

## Safety

Classification happens during scoring, so a blocked event never enters the
pool at all. `safe_mode` restricts the protagonist to rescuer, witness,
official, journalist or volunteer; adds a restraint rule to every prompt that
writes prose; and shows a content note before the game starts, with a way to
decline. A private individual's name is dropped during enrichment rather than
in a prompt later, so nothing downstream can leak what it never had.
[safety.md](safety.md) has the cases.

## Music

Lyria RealTime is Gemini-API-only and has no ephemeral-token support, so the
browser cannot hold a music session; the backend proxies it. The socket is
capped at twelve minutes — past the long end of a game — because Cloud Run
bills a WebSocket for as long as it is open, and music is the one line item
with no natural ceiling. Prompts are rebuilt from the style card and the
current location, and nothing is re-sent when nothing changed.

If Lyria will not start or drops out, the session falls back to captured loops
and tells the browser over the same socket, so the failure is a change of
message rather than a silence.

## Models and spend

| Need | Model |
|---|---|
| Text | `gemini-3.5-flash-lite` on Vertex AI |
| Images | `gemini-3.1-flash-lite-image` on Vertex AI |
| Embeddings | `gemini-embedding-001` at 768 dimensions |
| Music | `models/lyria-realtime-exp`, Gemini API |

Stages never touch `google.genai`: they ask an `LLM` for structured JSON or an
image, and every call is metered. That is what lets the whole pipeline run
offline against `FakeLLM`, and what makes the monthly cap enforceable rather
than aspirational — it is checked in the store before anything can spend.

**The binding constraint is not price, it is quota.** Image generation is
limited to two requests per minute for the whole project and that will not be
raised, so images are rate-limited through a token bucket and a missing image
is never fatal: the scene renders without it.

## Three run modes

| `LLM_MODE` | What it does | Spends |
|---|---|---|
| `mock` | Replays four recorded games. Never reaches the pipeline. | nothing |
| `fake` | The **real** pipeline with the model substituted at the bottom. | nothing |
| `live` | Vertex AI. | yes |

`mock` and `fake` are genuinely different and both earn their place. Mock is
what makes the loading screen, the SSE plumbing and the client's stage
handling get exercised by the zero-cost path rather than first tested on the
paid one. Fake is what the tests and evals run against, because a bug in stage
sequencing or draft normalization shows up there and cannot show up under
mock.

## Storage

Firestore, because saves are deeply nested single-owner documents read and
written whole — in Postgres they would be a `jsonb` column, which is Firestore
with extra steps — and because Cloud Run scales to zero and Cloud SQL does
not. Access is `by user`, `by user + game`, `by region + score`; no joins, no
cross-user aggregation.

```
users/{uid}/games/{gameId}            state and script
users/{uid}/played_events/{eventId}   canonical urls + embedding, for dedup
events/{region}/pool/{eventId}        the region's playable events
budget/{yyyy-mm}                      month-to-date spend
```

Per-player dedup needs vector comparison, but only against the handful of
events *that player* has seen, so it is brute-force cosine in Python with no
index. Security rules deny every read and write: the backend uses the Admin
SDK, which bypasses them, and nothing else should be reaching the database at
all.

## Frontend

Zustand holds one store; `App.tsx` maps a `screen` enum onto nine components.
Movement is optimistic — the client walks the player locally and commits one
request after the path settles, so a click-to-move across the map is one call
rather than fourteen. `web/src/game/map.ts` mirrors `app/game/map.py` exactly,
because both sides must agree on what is walkable.

Firebase configuration is fetched from `/api/config` at startup rather than
compiled in, which is what lets one container image run locally and in
production, and makes `AUTH_MODE` the single switch that decides whether the
app has real accounts.

The terminal look lives entirely in `web/src/index.css`: one palette, a
two-layer parallax starfield, square corners enforced globally, and
`image-rendering: pixelated` on every generated image. Tailwind 4 is used
CSS-first — there is no `tailwind.config.*` and no `@theme` block.
