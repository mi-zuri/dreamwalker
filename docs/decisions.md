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

### Images are capped, because they cannot be made cheaper

Measured on the real model: `gemini-3.1-flash-lite-image` bills **1120 output
tokens = $0.0336 per image regardless of resolution.** Asking for 1K vs the
default produced identical token counts. Resolution is not a lever; **count is
the only lever.**

- **Hard cap of 3 generated images per game.**
- News mode prefers real press photos, which are free, so it often generates
  1–2.
- Q7's variable story length helps directly: a two-location story generates two
  images.
- Aggressive caching by style + location hash, as the old code already did.

### Revised cost model

| | Old plan | Cheap mode |
|---|---|---|
| Images | ~6 → $0.20 | ≤3 → **$0.10**, often less |
| Text | $0.08 | **$0.05** (less pregeneration) |
| News ingest, per game | — | **$0.03–0.05** amortised |
| **Per game** | ~$0.28 | **~$0.15 idea / ~$0.12 news** |
| **Fixed monthly** | ~$9 | **$0** |

At ~10 PLN (~$2.45) that is roughly **16–20 games a month**. Enough for a
project you and some friends play; not enough to hand around widely — which is
what invite-only (Q15) is for.

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

## Still needed

**The actual Lyria RealTime cost.** At a 10 PLN budget this is no longer a
detail — if live music costs more than a few groszy per minute it will dominate
everything above and `MUSIC_MODE` flips to the pregenerated loop library
(~$1.20 once, then free forever).

Worth checking whether the Gemini API key is on the free tier: an image call
with that key returned `429 RESOURCE_EXHAUSTED`, which suggests free-tier
limits, and free-tier Lyria usage may cost nothing at all. That would explain
"costs are fine" and would make live music essentially free.
