# Architecture

How Dreamwalker is built, from the ground up. What it is *as a game* is in
[game-design.md](game-design.md); the news half has its own page,
[news-pipeline.md](news-pipeline.md); the cloud side is [gcp.md](gcp.md); the
reasoning behind individual choices is in [decisions.md](decisions.md).

## 1. The shape of it

```
                      ┌─────────────────────────────────────┐
  browser ──HTTP──────▶  Cloud Run: FastAPI + the SPA        │
     │                │                                      │
     │                │   pipeline ──▶ Vertex AI   text · images · embeddings
     │                │       │                              │
     │                │       ├─────▶ Firestore  games · pool · spend
     │                │       └─────▶ Cloud Storage  images · turn logs
     │                │                                      │
     └──WebSocket─────▶  music proxy ──▶ Gemini API  (Lyria RealTime)
                      └─────────────────────────────────────┘
```

**One service serves the API and the frontend.** Firebase Hosting in front of
Cloud Run is the usual arrangement and was rejected: its rewrites do not carry
a WebSocket upgrade, and the music socket is not optional. One origin also
means no CORS and one thing to deploy.

**There is no `shared/` folder.** `web/src/api/schema.d.ts` is generated from
the backend's own OpenAPI schema and CI fails on a diff, so the frontend
cannot drift from the contract.

## 2. Repo layout

```
web/                    React 19 · Vite 7 · TypeScript · Tailwind 4 · Zustand
  src/api/              generated schema + the fetch client
  src/components/       screens, the tile map, the header, the starfield
  src/game/map.ts       tile logic, mirrored from the backend
  src/store.ts          the single Zustand store
  src/i18n.ts           every UI string, pl + en

backend/
  app/
    main.py             HTTP surface, SSE, the music socket, the SPA
    settings.py         every switch, read from the environment
    auth.py             Firebase ID token verification
    errors.py           the error contract both sides speak
    game/map.py         pure tile logic (mirror of web/src/game/map.ts)
    models/             Pydantic: game state, plan, script
    llm/                Vertex wrapper, FakeLLM, mock replay, image rate limit
    pipeline/           every generation stage, the turn engine, the ending
    news/               sources, clustering, scoring, enrichment, the pool
    music/              Lyria session, captured loops, prompt building
    storage/            Firestore or memory; assets in GCS or memory
  tests/                invariants — red build on failure
  evals/                graded measurements — see evals.md

infra/                  Dockerfile, Cloud Build, Terraform, deploy script
```

## 3. The life of a game

| Step | Call |
|---|---|
| Sign in | Firebase Google sign-in in the browser; the ID token is a bearer token on every request |
| Create | `POST /api/games` → `{game_id}`, **immediately** |
| Watch | `GET /api/games/{id}/stream` — SSE, one coarse stage at a time |
| Load | `GET /api/games/{id}` → the full `GameState` |
| Walk | `POST /api/games/{id}/move` → state delta |
| Choose | `POST /api/games/{id}/choose` |
| Answer | `POST /api/games/{id}/answer` |
| Leave | `POST /api/games/{id}/set-off` |
| Finish | `GET /api/games/{id}/ending` |
| Library | `GET /api/games`, `GET /api/games/{id}/replay` |
| Music | `WS /api/music?game_id=` — binary PCM frames |

Creating a game cannot be answered synchronously: generation takes the better
part of ten seconds, and holding an HTTP request open for it would make a
proxy timeout indistinguishable from a failure. So `start_game` registers a
job, returns an id, and the loading screen reads progress over SSE.

The SSE stream emits a **coarse** enum only — `story · map · images · music ·
finishing` — and the UI shows vague labels. Progress is a reassurance, not a
debug trace.

## 4. The generation pipeline

Nine kinds of model call exist in the whole system. Nothing else talks to a
model, and every one of them is metered.

| Stage | When | Calls | In → out |
|---|---|---|---|
| `plan` | game start | 1 text | brief + style card → title, premise, 3–5 locations, a beat each |
| `scenes` | game start | 1 text | plan → prose, 3 choices and any open question **for every location at once** |
| `images` | start + background | 1 image per location | location `visual` + style axis → PNG |
| `ending` | on finish | 1 text | the turn log → what the run became |
| `cluster` | news refresh | embeddings | articles → events |
| `score` | news refresh | 1 text per 25 events | events → interest, playability, safety |
| `dossier` | first play of an event | 1 text | article bodies → facts, people, canon beats |
| `photo-safety` | first play of an event | 1 vision call per photo | press photo → caption + verdict |
| `photo-match` | news game start | 1 text | captions vs locations → which photo goes where |

Stages never import `google.genai`. They ask an `LLM` for structured JSON or
for an image; `llm/vertex.py` owns the retry policy (2 retries, jittered
exponential backoff, a parse failure re-prompted with the validation error)
and the token accounting. That is what lets the entire pipeline run offline
against `FakeLLM`, and what makes the spend cap enforceable rather than
aspirational.

### Why the order is what it is

The shape of `pipeline/live.py` is dictated by one number: the player should
be looking at something within about **eight seconds**. Plan → map → five
scenes → five images → start is about twenty.

```
 plan ──▶ map ──▶ validate/repair ──┬─ scenes ─────────┐
 1 call     free        free        └─ opening image ──┴──▶ ready  (~8 s)
                                                             │
              the player reads the premise and walks ────────┤
                                                             ▼
                                         remaining location images
```

* **The plan** is the only call nothing else can start without. It decides
  what the game *is*; the map, the scenes, the images and the ending are all
  derived from it. The model returns a positional draft and the backend
  assigns the ids, so a location can never be referenced by a name the model
  invented two fields later.
* **The map** is procedural. It costs nothing and takes no time.
* **Scenes** are one batched call, not one per location. Five sequential
  calls would put four of them in front of the player, and a model writing
  all five together stops opening each one with the same image.
* **Images** — the first is awaited briefly, the rest fill in while the player
  is reading and walking, which is fifteen to twenty seconds they were going
  to spend anyway.
* **The ending** is the one stage that cannot be pregenerated, because it is
  the only one that has seen what the player did.

## 5. The turn engine

`pipeline/engine.py` is pure state transitions — no I/O, no model calls, 100%
covered by tests.

The client animates movement locally; this is the authority. A move is
BFS-validated against the server's own copy of the map, so a move to a tile
the player cannot actually reach is ignored rather than trusted. Locked doors
are walls until the destination that unlocks them is reached.

Which choice is "on canon" is decided at generation time and kept in the
server-side `GameScript`, never in the `GameState` the client sees. Choosing
off-canon advances divergence by a fixed step and marks the beat `diverged`.

## 6. The map

A grid of characters: `#` wall, `.` floor, `+` locked door, `@` start,
`A`–`E` destinations, each bound to a plan location. A location the plan
marked locked becomes a door, keyed to the destination that opens it.

`pipeline/map_validator.py` is a pure function over the grid:

1. structure — rectangular, walled border, exactly one `@`, every declared
   destination present exactly once;
2. BFS from `@` with locked doors treated as walls;
3. a fixpoint that unlocks any door whose prerequisite is now reachable, and
   re-runs the BFS until nothing changes;
4. every destination reachable, no path longer than `MAX_PATH`, the whole
   tour inside the walking budget.

On failure the generator is re-prompted with structured diagnostics. If that
does not fix it, a **deterministic repair** squares the grid off, renames
unusable keys, drops doors that cannot mean anything and carves corridors to
anything stranded. The repair always succeeds, so the loop is bounded: there
is no infinite regeneration and no user-visible map failure.

## 7. Images, and the constraint that shapes them

**The binding constraint is quota, not price.** Vertex allows this project
**two image-generation requests per minute**, project-wide and permanent. Cost
is flat and small at $0.0336 an image.

Two a minute sounds fatal for a game that wants six pictures, and would be if
they were demanded at once. They are not: images are generated in the order
the player will arrive at them, one token at a time through a bucket in
`llm/ratelimit.py`. The limiter exists so that the image *nobody has reached
yet* is the one that waits.

Nothing about an image is allowed to be fatal. A location without one renders
without one.

Image prompts are built from the location's `visual` line and the style card's
visual axis — never from the scene prose, because prose in the story language
drags the model towards rendering that language as text on the picture.

## 8. Music

Lyria RealTime is Gemini-API-only and has no ephemeral-token support, so the
browser cannot hold a music session; the backend proxies it over the same
origin. Prompts are rebuilt from the style card and the current location, and
nothing is re-sent when nothing changed.

The socket is capped at twelve minutes — past the long end of a game —
because Cloud Run bills a WebSocket for as long as it is open, and music is
the one line item with no natural ceiling.

If Lyria will not start or drops out, the session falls back to captured loops
and says so over the same socket, so the failure is a change of message rather
than a silence.

## 9. Language

`story_language` and `ui_language` are independent fields on the game state,
and the story language is independent of the region. Every generation stage is
told the language explicitly and echoes a `language` field back, which the
orchestrator checks.

Image prompts are always English, with a mandatory clause forbidding text,
letters, numbers, signage and watermarks.

## 10. Safety

Classification happens during news scoring, so a blocked event never enters
the pool at all. `safe_mode` gates the style card's role axis, adds a
restraint rule to every prompt that writes prose, and shows a content note
before the game starts. A private individual's name is dropped during
enrichment rather than in a later prompt, so nothing downstream can leak what
it never had. Cases and the measured behaviour: [safety.md](safety.md).

## 11. Storage

Firestore. Saves are deeply nested single-owner documents read and written
whole — in Postgres they would be a `jsonb` column, which is Firestore with
extra steps — and Cloud Run scales to zero where Cloud SQL cannot. Access is
`by user`, `by user + game`, `by region + score`: no joins, no cross-user
aggregation.

```
users/{uid}/games/{gameId}            state and script
users/{uid}/played_events/{eventId}   canonical urls + embedding, for dedup
events/{region}/pool/{eventId}        the region's playable events
budget/{yyyy-mm}                      month-to-date spend
```

Images and long turn logs go to Cloud Storage; the game document keeps a
reference, because a Firestore document stops at 1 MiB.

Security rules deny every read and write. The backend uses the Admin SDK,
which bypasses them, and nothing else should be reaching the database.

`storage/memory.py` implements the same interface in RAM, which is what local
development and the whole test suite run against.

## 12. Access and spend

**Auth.** Google sign-in through Firebase; the ID token is verified on every
request and everything user-scoped hangs off the uid. `AUTH_MODE=dev` skips
verification for local work. `invite_only` plus `allowed_emails` is what keeps
a public URL from being a public bill.

**Budget.** Every call's tokens and images are priced at the list rate and
added to `budget/{yyyy-mm}`. `check_budget` runs *before* a game starts, and
over the cap the API answers `budget_exceeded` and the UI says the month's
budget is spent. The default cap is $2.40.

**Errors.** Six kinds — `network`, `generation_failed`, `pool_empty`,
`budget_exceeded`, `blocked_event`, `auth` — each with a status code and a
frontend string. Anything unhandled is caught, logged with its traceback, and
returned as `generation_failed` with only the exception's type name, so
nothing internal reaches the browser.

## 13. Frontend

One Zustand store; `App.tsx` maps a `screen` enum onto the screen components.
Movement is optimistic — the client walks the player locally and commits one
request once the path settles, so crossing the map is one call rather than
fourteen. `web/src/game/map.ts` mirrors `app/game/map.py` exactly, because
both sides must agree on what is walkable.

Firebase configuration is fetched from `/api/config` at startup rather than
compiled in, which is what lets one container image run both locally and in
production.

The terminal look lives entirely in `web/src/index.css`: one palette, a
two-layer parallax starfield, square corners enforced globally, and
`image-rendering: pixelated` on every generated image. Tailwind 4 is used
CSS-first — no `tailwind.config.*`, no `@theme` block.

## 14. Run modes

| `LLM_MODE` | What it does | Spends |
|---|---|---|
| `mock` | Replays four recorded games. Never reaches the pipeline. | nothing |
| `fake` | The **real** pipeline with the model substituted at the bottom. | nothing |
| `live` | Vertex AI. | yes |

Both zero-cost modes earn their place. Mock is what makes the loading screen,
the SSE plumbing and the client's stage handling get exercised for free rather
than first tested on the paid path — mock games are built instantly and then
*pretend* to take time, walking the same stage script with sleeps. Fake is
what the tests and evals run against, because a bug in stage sequencing or
draft normalization shows up there and cannot show up under mock.

`STORAGE_MODE` and `ASSETS_MODE` switch Firestore and GCS for memory
independently, which is why the test suite touches no cloud service at all.

## 15. Tests and evals

They answer different questions and are kept apart.

* **`backend/tests/`** assert invariants. A failure is a red build.
* **`backend/evals/`** *measure* — style diversity, canon adherence, safe-mode
  behaviour, language correctness — and report a pass rate against a
  threshold. See [evals.md](evals.md).

`make` runs what CI runs: lint, tests, evals, the frontend build and the
schema contract.
