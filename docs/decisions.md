# Decisions

Answers to `open-questions.md`, plus the design changes they force.
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
| 7 | Locations per game | **Variable, 1–5, driven by the story** |
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
fixed template: the map stage picks 1–5 destinations and the scene stage picks
0–2 open questions to fit the story. This both improves the feel and cuts cost
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

## Still needed

**The actual Lyria RealTime cost.** At a 10 PLN budget this is no longer a
detail — if live music costs more than a few groszy per minute it will dominate
everything above and `MUSIC_MODE` flips to the pregenerated loop library
(~$1.20 once, then free forever).

Worth checking whether the Gemini API key is on the free tier: an image call
with that key returned `429 RESOURCE_EXHAUSTED`, which suggests free-tier
limits, and free-tier Lyria usage may cost nothing at all. That would explain
"costs are fine" and would make live music essentially free.
