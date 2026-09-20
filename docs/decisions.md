# Decisions

The build log: the seventeen questions the plan ended on, the answers, and
every decision taken since, with the measurements behind them. Read
[architecture.md](architecture.md) for what the system *is*; this is why.
Settled 2026-09-20.

## Framing

A student project. Not promoted, not sold. Fun over polish, few gameplay
ceilings, but a **hard money cap**: target **~10 PLN/month while being played,
0 PLN when idle**.

That second half is the constraint that actually changes the architecture.

---

## Answers

| # | Question | Answer |
|---|---|---|
| 1 | Budget conflict | **Cut costs heavily.** ~10 PLN/month active, 0 idle |
| 2 | Per-user daily game cap | **None** |
| 3 | Global daily spend ceiling | **None** — monthly hard cap instead |
| 4 | Guest play | **Google-only** |
| 5 | Keep the name DREAMWALKER | **Yes** |
| 6 | Idea-mode ending without match score | **Yes** |
| 7 | Locations per game | **Variable, driven by the story** (shipped as 3–5) |
| 8 | Open-text questions | **Variable, 0–2, driven by the story** |
| 9 | Anti-repetition on ideas | **No** |
| 10 | PL player + world news → Polish story | **Yes** |
| 11 | Two regions only | **Yes** |
| 12 | Music on by default | **Yes** |
| 13 | Firebase Hosting for the frontend | **Yes** (see note below) |
| 14 | Custom domain | **dreamwalker.zur-i.com** |
| 15 | Launch visibility | **Invite-only** |
| 16 | Ship after Phase 4 | **Yes** — idea mode first |
| 17 | Full step-through replay | **Yes** |

---

## What "0 PLN when idle" changes

### The scheduled news ingest job is cancelled

It was the single largest fixed cost — roughly $0.30 per region per run, two
regions, every 48 hours, about **$9/month (~36 PLN) whether or not anybody
plays**. That alone exceeded the whole budget.

**Replaced with lazy, on-demand refresh.** When a player starts a news game and
that region's pool is empty or stale, the pool is refreshed inline during the
loading screen. When nobody plays, nothing runs and nothing bills.

What the inline refresh does differently from the cancelled job:

- Fetch the region's feeds in parallel (~2s, free).
- Rank with **cheap heuristics** — cluster size by shared entities, source
  count, recency — instead of embeddings across every article.
- One small batched LLM call to score playability and safety for the top ~10.
- **Enrich only the event actually chosen**, not the top 15–20.
- Cache the result as the pool for the next 48h, so only the first game after
  staleness pays for it.

Cost moves from fixed to marginal: ~$0.03–0.05 on the first news game after the
pool goes stale, and $0 otherwise. No Cloud Scheduler job, so nothing ticks.

Everything else already idles free: Cloud Run scales to zero, Firestore and
Cloud Storage stay inside their free tiers at this volume.

### Images stay generous, and cannot be made cheaper

Measured on the real model: `gemini-3.1-flash-lite-image` bills **1120 output
tokens = $0.0336 per image regardless of resolution.** Asking for 1K vs the
default produced identical token counts. Resolution is not a lever; **count is
the only lever that exists.**

Decision (2026-09-20): **do not cap image count.** Keep generation generous —
the look is a large part of the point, and the month-to-date spend cap already
bounds the damage. The practical effect is fewer games per month before the cap
trips, not a surprise bill.

Two things still reduce image spend without touching quality:

- News mode prefers real press photos, which are free, so it generates only
  what the photos do not cover.
- Q7's variable story length means a short story generates few images on its
  own.

Caching by style + location hash still applies, as the old code did.

### Revised cost model

| | Old plan | Now |
|---|---|---|
| Images | ~6 → $0.20 | uncapped, **~$0.20** typical |
| Text | $0.08 | **$0.05** (less pregeneration) |
| News ingest, per game | — | **$0.03–0.05** amortised |
| **Per game** | ~$0.28 | **~$0.25 idea / ~$0.20 news** |
| **Fixed monthly** | ~$9 | **$0** |

At ~10 PLN (~$2.45) that is roughly **10–12 games a month**. The saving that
matters is the fixed cost going to zero; images were deliberately left
generous. If that turns out too tight in practice the cheapest lever is image
count, and it can be capped later without touching anything else.

**Music is the remaining unknown and it is now load-bearing.** See below.

### The hard cap, built two ways

Q2 and Q3 say no gameplay ceilings, so the only limit is money, and it has to
actually hold.

1. **App-side, immediate.** Every generation adds its estimated cost to a
   month-to-date counter in Firestore. Before generating anything, the
   orchestrator checks the counter against the cap. Over it, the app stops
   generating and serves saved runs plus a "back next month" notice. This is
   the real protection, because it reacts instantly.
2. **Billing-side, as backstop.** The budget alert publishes to Pub/Sub, a tiny
   Cloud Run endpoint flips a `budget_exceeded` flag in Firestore. This lags by
   hours, so it is a safety net, not the mechanism.

Deliberately *not* doing the classic "disable billing on the project" trick — it
would take down Firestore and auth too, and recovering is manual.

---

## Notes on specific answers

**Q7/Q8 — variable length.** Story length now drives structure rather than a
fixed template: the plan stage picks the destinations and the scene stage picks
0–2 open questions to fit the story. The lower bound was later raised from one
to three - a single-room game is not a game - so the shipped range is 3–5. This both improves the feel and cuts cost
on short stories. The map validator must therefore handle a single-destination
map, and the mock fixtures need a short example.

**Q13/Q14 — hosting.** Firebase Hosting is fine and its site already exists.
Worth knowing before Phase 8: `zur-i.com` is on **Vercel DNS** (registrar
Name.com) and your apex site is served by Vercel, while
`dreamwalker.zur-i.com` currently resolves through a wildcard to
`DEPLOYMENT_NOT_FOUND` — so the subdomain is free. Firebase Hosting means
adding A/TXT records in the Vercel dashboard; deploying the frontend to Vercel
instead would need no DNS work at all and keeps GCP spend to the API alone.
Either is reversible; decide at Phase 8.

**Q12 — music.** On by default, with a mute control, sessions capped at 12
minutes.

---

---

## Phase 2 decisions

Made while building the backend contract. None of these change the budget.

**Movement commits once per walk, not once per tile.** The mock frontend fired
one call per step (90ms apart). Against a real backend that is ~20 requests for
one walk. The client now animates locally and commits the settled destination
after 140ms of stillness; the server BFS-validates that tile against its own
map and its answer overwrites the optimistic position. One walk, one request,
and still no way to walk through a wall or a locked door.

**Pregenerated content lives in a `GameScript`, not in `GameState`.** Scene
text, dialogue and the ending are stored server-side under
`users/{uid}/scripts/{game_id}` and never leave it. The player is handed only
the scene they have reached, and the generated OpenAPI schema stays as small as
the UI needs. The turn log is appended to the same document as the game is
played, which is what the replay is served from.

**One error shape: `{kind, detail}`.** `kind` is the same closed set the UI
branches on, so the client never parses prose. The model is declared in the
schema, so `AppErrorKind` is generated rather than hand-kept.

**The loading stream is read with `fetch`, not `EventSource`.** `EventSource`
cannot set an `Authorization` header, and putting an ID token in a URL puts it
in every access log along the way.

**`web/src/types.ts` is now a projection of the generated schema**, not a
parallel definition. The only hand-written part re-asserts collections that
Pydantic's `default_factory` marks optional but the server always sends.

**`web/src/mocks/` is gone.** The four recorded runs moved to
`backend/app/fixtures/games/*.json` and are replayed by `LLM_MODE=mock`, so the
mock path is now the real API with fake content rather than a second
implementation of the game that could drift.

---

## Phase 3 decisions

**The map is generated procedurally, not by a model.** This is a deliberate
departure from the plan, which had the grid come out of the generator prompt
with the validator re-prompting it on failure. Cost was not the reason - a
53x27 grid is about 500 output tokens, well under 2% of a game. The reasons
are that a model call in the `map` stage adds seconds to the "first scene
under 8s" budget; that models are unreliable at grid invariants (equal row
lengths, exactly one `@`, connectivity), so the repair loop would fire
constantly and the repaired result would be procedural anyway; and above all
that the arrangement of rooms carries no meaning. What *does* carry meaning -
which locations exist, what they are called, how many there are, and which one
is locked behind which - is decided by the story and passed in as arguments.

`world_map.build_map` therefore keeps the plan's bounded loop with the
generator swapped out: generate, validate, retry twice on a new seed, then
deterministic repair. The validator never learned anything about how the map
was made, so a model-authored grid could be dropped in later without touching
it.

**Locked rooms are leaves of the spanning tree.** A leaf cell has exactly one
corridor, so putting the door on that corridor is the only way in *by
construction* rather than by inspection. Extra loop corridors are never carved
next to a locked room, and every corridor is confined to the two lattice cells
it joins, so one room's corridor can never cut through another room and quietly
bypass its lock. The validator checks this anyway, via `door_decorative`.

**Issues are blocking or cosmetic.** A door that gates nothing makes a map
sloppy, not unplayable, so it is reported and tolerated - `build_map` retries
past it but will ship it rather than mangle a working map to avoid it. Only
blocking issues trigger repair.

**Repair prefers carving to giving up.** An unreachable room gets a corridor
tunnelled to the nearest reachable tile; a key locked behind its own door has
that door removed. Both always succeed, so a bad layout can cost the map some
of its shape but can never reach the player as an error. The one case repair
refuses is a grid too small to hold a game, which the caller answers by
generating a fresh one.

**The walking budget is a real limit, not a formality.** `MAX_PATH` is 120
tiles and the whole tour is capped at 90 seconds of walking at the client's
90ms per step. Generated maps come in around 10-20 seconds of walking, so the
caps exist to catch a pathological layout rather than to shape a normal one.

**`MOCK_MAP_SOURCE=generated`** swaps the recorded grid of a mock game for a
freshly generated one while keeping its locations, locks and story. It is how
the generator gets walked in a browser without spending anything, and it is the
seam Phase 4 replaces with a real story-driven map request.

---

## Phase 4 decisions

**The image quota, not the image price, is what shapes the pipeline.** Vertex
allows this project **two image-generation requests per minute**
(`GenContentImageGenRequestsPerMinutePerProjectPerBaseModelGlobal`, read live
from the Cloud Quotas API). That is project-wide and it is the real constraint;
at $0.0336 flat per image, cost never was. A game wants six pictures, so they
are generated in the order the player will arrive at them, one at a time,
through a shared token bucket. The picture nobody has reached yet is the one
that waits. A quota increase is a support request, not a setting - see below.

**Only the opening image blocks the loading screen, and only for six seconds.**
Everything else is generated while the player reads and walks.

**Scenes are written behind the loading screen, not on it.** Measured: the plan
call is 4-10s and the scene call for five Polish locations is another 6-7s.
Doing both before the player sees anything put a full-size game at 12-14s. So
`open_game` returns after the plan, the map and the opening image; `fill_scenes`
runs behind it, and a move to a location whose scene has not landed yet waits on
a gate rather than dropping the player into an empty room. Measured cost of the
restructure: ready fell from 12.3s to about 8s.

**A scene stage that fails must still leave a finishable game.** There is no
loading screen left to show an error on, so the fallback assembles each
location's own planned description plus three deliberately dull choices. A
location with no choices could never be resolved, which would strand the player
on the map forever.

**Which choice is "on canon" is server-side.** The player sees three equal
options. `GameScript.outcomes` holds the beat each one advances and whether it
follows the plan, so the ending can tell the difference without the game ever
rendering a hint.

**Style cards are sampled, never generated.** Enum ids only, so the sampler
costs nothing, adds no latency and behaves identically in both languages - the
catalog holds a Polish label, an English label and one English prompt fragment
per value. Anti-repetition is per player and rejects a draw sharing two or more
axes with any of that player's last five cards. Twenty consecutive draws produce
twenty distinct cards.

**`LLM_MODE=fake` is a third mode, not a synonym for `mock`.** Mock replays four
recorded games and never touches the pipeline. Fake runs the real pipeline -
planning, map generation, scene assembly, the turn engine, the ending - against
a synthetic model. A stage-sequencing bug can only show up under `fake`, which
is why the API tests use it.

**Measured, live, for a full Idea-mode game:** English three-location run $0.105,
Polish five-location run $0.177, against a $0.28 estimate. Both under, because
the model chooses fewer locations than the maximum and text came in cheaper than
modelled. `gemini-3.5-flash-lite` is available on Vertex for this project - the
allowlist fallback was never needed.

---

## Phase 5 decisions

**There is no scheduled ingest job.** The plan called for Cloud Scheduler every
48 hours per region, which is about $9 a month spent whether or not anybody
plays - most of a 10 PLN budget, in violation of "0 PLN when not playing". A
News game instead refreshes its region's pool first, and only when the pool is
thinner than 12 playable events or older than 6 hours. Nobody playing means
nothing spent.

**That is affordable because ingest was split in two.** Collecting, clustering
and scoring a whole region is feeds (free), embeddings (fractions of a cent) and
one batched scoring call. Reading real articles and writing a beat graph happens
per *event*, on the way into a game, and is cached on the event so the second
player to draw it pays nothing.

**Measured, live: $0.046 for both regions together**, against a $0.40 per region
per run budget. Poland yielded **47 playable events**, World **58**, both well
past the 30 the phase gates on - so the deferred 4h collector is still not
needed.

**Importance is counted; only judgement is asked for.** How many outlets carried
an event, how many distinct ones, and how recent it is are facts about the pool.
A model rating them would be guessing at something countable. Interest,
playability and safety are asked, once per region, for the top 80 events by
computed importance.

**The clustering threshold was measured, not assumed, and the plan's number was
wrong.** On 120 real Polish articles: the same story scores 0.89-0.94, and *two
unrelated fatal road accidents* score 0.89. The planned 0.82 would have merged
whole genres into single events. Cosine alone cannot separate them at any
threshold, so clustering now requires **0.88 cosine and at least one shared
distinctive word**, where "distinctive" means low document frequency across the
batch. Two crashes share tragedia, kierowca, nie zyje; they do not share
Kartuzy. That gate is what fixed it.

**Per-player dedup stays at 0.93 with a shared-canonical-URL escape hatch.**
Real embeddings have a high floor - two unrelated stories still score 0.72 - so
a strict threshold is right, and the URL test catches the common case of one
story being re-clustered under a new id on a later run.

**A private individual's name is dropped during enrichment**, not in a prompt
later. Nothing downstream can leak what it was never given.

**`feeds.reuters.com` is still dead** and is absent by decision, not oversight.
All six Polish feeds, all three World feeds and the Wikipedia Current Events
portal were re-verified live this phase; the Polish feeds carry a press photo on
better than 80% of items.

---

## Phase 6 decisions

**The canon comes from the dossier, not from the plan.** The plan stage decides
where the player walks and is explicitly asked for one location per canon beat,
in order; the titles, summaries and citations are then overwritten with what the
dossier recorded. Pairing by position only asks the model to count. Pairing by
name would ask it to echo an id, which it eventually will not.

**A private individual's name is dropped during enrichment**, before any prompt
sees it. Filtering later would mean the name existed somewhere it could leak
from; this way nothing downstream ever has it.

**The content note is written by the plan stage, in the player's language.**
Ingest writes an English one for the logs. Measured: telling the model "write
this in the story language" is not enough - it writes the premise in Polish and
the note in English anyway. Naming the language outright ("written in Polish")
fixes it. The field is also *required* rather than defaulted, because a model
that may omit a field does omit it.

**Press photos are matched on their captions, not by looking again.** Every
photo was already described by a vision model during the ingest safety check, so
matching is a text call over captions and location descriptions - a few hundred
tokens instead of re-uploading four images, using the same information. A photo
below 0.5 confidence is left unused: a wrong photograph of a real event is worse
than a generated picture.

**Photos of war are frequently refused, and that is correct.** The Polish live
run drew a bombardment story and kept none of its photographs. Wikipedia-sourced
World events carry no photographs at all. Both fall through to generated images,
which is the designed behaviour rather than a failure.

**A pool that can still serve is refreshed behind the player.** Measured: a
cold-pool News game took 40s to open, because collecting six feeds, clustering
200 articles and scoring 80 events happened in front of the player. With the
refresh moved behind them, the same game opens in **10.0s**. Only a genuinely
empty pool still blocks.

**Measured, live:** a Polish safe-mode game about drone incursions and a World
game about a Japan-Fiji rugby final. Both produced valid maps, canon beats with
citations, and playable runs to the ending. $0.134 and $0.200.

---

## Phase 7 decisions

**Lyria RealTime works, and there is still no published price.** Verified live
through the app's own wrapper: `models/lyria-realtime-exp` opens, streams 48kHz
stereo 16-bit PCM at 192,000 bytes per second of audio, and steers on a prompt
change. What a minute of it costs is not documented anywhere, so it is **metered
rather than billed**: minutes are counted per player per day and capped, and no
invented number goes into the spend total. `python -m app.music.cli check` is
how that gets re-measured.

**The loop fallback is captured from Lyria, not from `lyria-3-clip-preview`.**
That model exists on the Gemini API but the installed SDK has no method that
reaches it, and hand-rolling a REST call for a fallback path is a bad trade.
Capturing twenty seconds per mood from RealTime uses an API that is already
verified, gives the same model family and the same prompts, and costs six short
sessions once. `python -m app.music.cli build-loops`.

**The fallback is a URL, not a stream.** Streaming a twenty-second loop back
over the socket for twelve minutes would be the same bytes over and over. The
browser is handed the WAV's URL and loops it itself, which also lets it cache.

**Sessions are capped at twelve minutes.** Cloud Run bills a WebSocket for as
long as it is open, and twelve minutes is past the long end of a 2-10 minute
game. Music is the only line item with no natural ceiling; everything else is
paid once per game.

**The music follows the player.** The client sends the location id it is looking
at; the backend rebuilds the prompt from the style card's mood axis and that
location's English `visual` line. The old code's "skip the call if the prompt
string is unchanged" guard is kept - it was the only thing stopping that version
calling the API on every step.

**The token rides in the query string, and only here.** A browser cannot set
headers on a WebSocket. That puts the token in access logs, which is why the SSE
stream deliberately does not do the same - it reads its body with `fetch` so its
token can stay in a header.

**`server/` is gone.** Its last live responsibility was the Lyria proxy. Its
`.env`, `node_modules` and `dist` are untracked and were left on disk rather
than deleted, because deleting an untracked `.env` is unrecoverable.

---

## Phase 8 decisions

**Two images per minute is permanent.** The project's
`GenContentImageGenRequestsPerMinutePerProjectPerBaseModelGlobal` quota is fixed
at 2 and will not be raised. Nothing above changes: the pacing already falls out
of the token bucket, only the prologue image is on the critical path, and a
location that never gets its picture renders without one. It is written down
here as a constraint rather than a to-do so nobody designs against a larger
number later.

**One Cloud Run service serves the API *and* the frontend.** The obvious shape
was Firebase Hosting in front of a Cloud Run backend - free CDN, free
certificate, easy custom domain. It does not work here: **Hosting's rewrites do
not carry a WebSocket upgrade**, and the music socket is not optional. Splitting
the difference - Hosting for the page, a direct `run.app` origin for the socket -
would mean two origins, CORS, and a token crossing between them. So the
container holds the built frontend and FastAPI serves it, registered after every
API route. Same origin, no CORS, one thing to deploy, and `/api/...` that misses
returns a 404 rather than a page of HTML for the client to parse as JSON.

**europe-west1, not europe-central2.** Warsaw is ~20ms closer to the player and
is where the assets bucket already lives, and it was still the wrong choice.
europe-west1 sits *inside* Firestore's `eur3` multi-region, so the several state
reads on every move are in-region rather than across one; and it is one of the
ten regions where Cloud Run can map a custom domain without a load balancer,
which europe-central2 is not. A global load balancer costs about $18/month
before it serves a byte - more than seven times the entire monthly budget.

**The Firebase config is served, not compiled in.** `/api/config` hands the
browser the project identifiers at boot. Those six values are public by design,
so this is not about secrecy - it is that one built image now runs anywhere, a
config change is a redeploy rather than a rebuild, and CI needs no secret to
build the frontend. The real win is that `AUTH_MODE` on the backend became the
only switch: in `dev` the backend sends no config and the browser uses its local
stub, so the two halves can no longer disagree about whether this install has
real accounts. That disagreement is exactly what opened a live Google sign-in
popup during Phase 7 browser testing.

**CPU stays allocated while an instance lives.** Cloud Run's default throttles
CPU between requests, and this app does its real work *after* the response:
scenes, the remaining images and photo matching all run behind the player.
Throttling would stall precisely that. `cpu_idle = false` costs nothing extra
while nobody is playing, because the instance still scales to zero.

**One instance, maximum.** A generation job lives in memory between the POST
that starts it and the SSE stream that watches it, so a request has to reach the
instance that owns it. Cloud Run's session affinity is best-effort; one instance
is not. It doubles as the ceiling on what a bad day can cost, and at
concurrency 80 it is far more than an invite list will ever need.

**No uptime check.** The plan asked for one. It is incompatible with the budget:
polling a scale-to-zero service keeps an instance alive around the clock, which
turns a free idle month into roughly $30. What replaced it is an alert on the
thing that actually matters unattended - more than five ERROR logs in ten
minutes, with `EVALUATION_MISSING_DATA_INACTIVE` so a quiet night is not an
incident - plus the billing budget. Nobody is paged when the game is asleep,
which is the correct behaviour for a game that is asleep.

**No service-account key anywhere.** GitHub Actions authenticates by Workload
Identity Federation, with the provider restricted to this one repository. A key
file in a repo secret is a permanent credential in a place neither of us can
rotate.

**CI ships code; it does not change infrastructure.** The deploy workflow builds
and rolls out a revision. It never runs Terraform. Who can reach the app, what
the budget is and what the invite list contains stay deliberate acts from a
workstation, with a plan to read first.

**Terraform state is not in the assets bucket.** That bucket is world-readable so
browsers can fetch generated images straight from it. State holds the invite
list, so it gets its own private, versioned bucket.

**Firestore rules deny everything.** The backend reaches Firestore through the
Admin SDK, which bypasses rules entirely. The rules exist to stop anything else:
the web SDK ships in the bundle with the project id in it, and without them a
stranger could read every saved game from a browser console.

**The custom domain is live.** `https://dreamwalker.zur-i.com` serves the
service on a Google-managed certificate with no load balancer. `zur-i.com`
stays on Vercel's nameservers; the subdomain is a `CNAME` to
`ghs.googlehosted.com`. The certificate took about fifty minutes to issue,
during which the mapping reported the ACME challenge as "not visible through
the public internet" even though DNS was already correct on every resolver
checked - that message means *not yet*, not *misconfigured*.

The Search Console `TXT` record at the apex must stay in place permanently.
Google re-checks it, and removing it lapses ownership of the verification the
mapping depends on.

---

## Phase 9 decisions

**Evals are a separate thing from tests, in a separate directory.** `tests/`
asserts invariants: one failure is a red build. `evals/` measures things that
are allowed to be imperfect and reports a rate against a threshold. The
distinction pays for itself in exactly one place — a style sampler that
returned the same genre nineteen times in twenty would pass every assertion
anyone would write about its type, its range and its safety gate, and would
still make every game read alike. What catches that is a number.

**The style sampler was rewritten because the eval said so.** This is the
finding that justified the phase. Seven axes over pools of three to eight
values mean two uniform cards share two or more axis values **40%** of the
time; a draw acceptable against a five-card history therefore comes up only
**8%** of the time; and ten rejection-sampling attempts all collided on
**45%** of draws, falling through to the escape hatch. The anti-repetition
rule the design advertises was not being delivered on nearly half of all
games, and nothing in the test suite could have noticed, because every
individual draw was type-correct and inside its safety gate.

The fix is to draw per axis from the values the player has *not* seen lately,
rather than drawing uniformly and rejecting collisions afterwards. Most axes
then become collision-free by construction and rejection only has to handle
the axes too small to be fresh. Measured violations: 45% → 0% in normal play,
0.26% in safe mode, at 24µs per draw. `MAX_RESAMPLES` went from 10 to 40,
which is a few hundred microseconds of arithmetic with no I/O behind it.

**The style-diversity threshold is 99%, not 100%.** The missing percent is
measured rather than conceded: safe mode shrinks `pacing` to three values
against a five-card history, so a repeat is occasionally unavoidable, and
twenty draws over eight genres can miss one by luck. Both are real behaviour.
A threshold of 100% would not make the sampler better, it would make the suite
flake.

**Two map-repair bugs, in the one part of the system that must never fail.**
A duplicated door record made the repair erase the tile the *kept* door owned
and then throw `MapRepairError`; and a grid shipping fewer rows than it
declared was padded silently, because the change was logged by comparing
declared dimensions rather than actual ones. Both are fixed; the repair is
supposed to be the thing that guarantees a playable map, so it is not allowed
to be the thing that raises.

**`FakeLLM` now writes real Polish.** It used to emit English prose with a
Polish language tag, which meant the language eval could not measure anything
and `LLM_MODE=fake` was not a usable Polish demo. It also placed open
questions by counting rather than by reading which locations the plan asked
for.

**Coverage went to the state engine and the map validator, not to a number.**
`pipeline/engine.py` is at 100% and `map_validator.py` at 99%, and the six
lines left are defensive `raise`s for conditions that cannot currently be
reached. The engine got its own test file against a hand-drawn seven-by-five
grid, because everywhere else it is exercised through a generated map — which
is the right way to catch integration problems and the wrong way to catch the
engine refusing an action it should have taken.

**Errors:**

- The budget message said "daily limit reached. come back tomorrow." The cap
  is monthly and there is no daily cap, so it now says so.
- The error screen no longer shows `detail` to a player. It carries exception
  text, dollar amounts and endpoint names — useful while developing, nothing a
  player should be handed. It is shown under `import.meta.env.DEV` only.
- An unhandled exception now returns the error contract rather than FastAPI's
  default 500 body. Without `kind`, the client fell back to "cannot reach the
  server" for a server that answered perfectly well, and the traceback was the
  only record of what actually happened.
- `[RETRY]` became `[BACK TO THE MENU]`, which is what the button does.

**`make` is the entry point, not a list of commands in a README.** `make`
runs exactly what CI runs. `make eval-live` exists, spends money, and says so;
CI never passes `--live`.

**No live eval in CI.** The safe-mode and language dimensions can be run
against Vertex with `--live`, and that is the number that matters for
classification judgement — but it is a thing a person runs on purpose, not
something that fires on every push against a 10 PLN budget.

**The README screenshots were taken from a live game, not a mock one.** One
Idea-mode run against Vertex, locally, measured at about $0.19 — under the
$0.28 estimate. Mock mode draws placeholder images, and a README hero showing
a procedural noise blob would misrepresent the product it is documenting.

---

## Still needed

**The actual Lyria RealTime cost.** At a 10 PLN budget this is no longer a
detail — if live music costs more than a few groszy per minute it will dominate
everything above and `MUSIC_MODE` flips to the pregenerated loop library
(~$1.20 once, then free forever).

Worth checking whether the Gemini API key is on the free tier: an image call
with that key returned `429 RESOURCE_EXHAUSTED`, which suggests free-tier
limits, and free-tier Lyria usage may cost nothing at all. That would explain
"costs are fine" and would make live music essentially free.

**Somebody who is not the author playing a game in production.** Phase 8's
exit criterion. Production sign-in itself is no longer untested - a real Google
account on the invite list signs in and plays through
`https://dreamwalker.zur-i.com` - but both addresses on that list are the
author's, so the criterion as written is still open. Add a third party to
`allowed_emails` in `infra/terraform/terraform.tfvars` and `tofu apply`: a new
revision, no rebuild.
