# Open questions

> **All seventeen of these are answered.** The answers, and what they changed,
> are in [decisions.md](decisions.md). This page is kept as the record of what
> was asked and what was recommended at the time — useful for reading the
> decisions against the reasoning they were made from, and nothing here should
> be treated as still open.

Everything I need a decision on. Each has my recommendation, so you can reply
"defaults except 3 and 9" and I will take it from there.

Ordered by when it blocks work, not by importance.

---

## Urgent — one of these is a real conflict

### 1. The budget does not cover the plan

You set a **30 PLN/month** alert. The news ingest job alone is estimated at
**~$9/month (~36 PLN)**: roughly $0.30 per region per run, two regions, every
48 hours. That exceeds the alert *before a single game is played*. Games are
~$0.28 each on top (idea) or ~$0.19 (news), plus Lyria.

Pick one:

- **a. Raise the budget** to ~150 PLN/month and keep the plan as designed.
- **b. Keep 30 PLN and cut the ingest**: one region instead of two, and/or run
  it every 96h instead of 48h. Fewer, staler events.
- **c. Keep 30 PLN and make news mode invite-only**, so idea mode (which has no
  ingest cost) is what the public sees.

*My recommendation: (a) while building, then reassess from real numbers once
Phase 5 has run the ingest a few times for real. 30 PLN is a fine alert for
"something has gone wrong" but it is below the resting cost of the design you
approved.*

### 2. Per-user daily game cap

The app enforces its own limit before generating anything.

*Recommendation: 5 games/user/day.*

### 3. Global daily spend ceiling

A hard stop in the app, independent of the billing alert. Over it, the app
serves replays and a friendly notice instead of generating.

*Recommendation: set it to 1/20th of whatever you choose in Q1, so a runaway
bug costs at most a day's worth.*

### 4. Guest play?

Plan says Google sign-in from the start. Allowing anonymous play would widen
the funnel but makes per-player dedup and rate limiting much weaker — the two
things that keep costs bounded.

*Recommendation: Google-only, as planned.*

---

## Phase 4 — idea mode

### 5. Keep the name DREAMWALKER?

It is in the header, the start screen and the aesthetic, but the game is no
longer about dreams. One-line change in `i18n.ts` and `Header.tsx`.

*Recommendation: keep it. It is a good name and the alternative is a rename
across screenshots, docs and the project id.*

### 6. Idea-mode ending has no match score

There is no canon to compare against, so the ending is a "what your story
became" recap plus a style retrospective. Already built this way.

*Recommendation: confirm as-is.*

### 7. Locations per game

Currently 5 destinations on a 53x27 map. Drives the length of a run.

*Recommendation: keep 5, and measure a real playthrough in Phase 4 against the
2-10 minute target before changing it.*

### 8. Open-text questions per game

The plan said 1-2. The mocks currently ask 1.

*Recommendation: 2 — one early, one near the end. It is the most distinctive
mechanic and one feels like a token gesture.*

### 9. Anti-repetition on ideas as well as style cards?

Style cards already avoid repeating within a player's recent games. Should
typing the same idea twice also be steered somewhere new?

*Recommendation: no. If someone retypes an idea they probably want that story
again, and the style card already guarantees it plays differently.*

---

## Phase 6 — news mode

### 10. Polish player, world news, Polish story

Story language is independent of region, so a Polish player picking world news
gets a Polish story about an English-language event.

*Recommendation: confirm — this is what the plan specifies and it is the right
behaviour.*

### 11. Only two regions?

Poland and World. A third (Europe? local city?) is possible but each region
doubles ingest cost and needs its own curated sources.

*Recommendation: two, as planned.*

---

## Phase 7 — music

### 12. Music on by default, or opt-in?

You confirmed the Lyria cost is acceptable. Two things still argue for a
toggle: a 10-minute game streams **~115MB**, which is real Cloud Run egress,
and it holds a WebSocket open for the whole session.

*Recommendation: on by default with a mute control, but cap a session at 12
minutes and meter music-minutes per user per day separately from games.*

---

## Phase 8 — deployment

### 13. Frontend hosting

Firebase already provisioned a hosting site (`mi-zuri-dreamwalker-app`) when
you enabled auth. The alternative is serving the built frontend from Cloud Run.

*Recommendation: Firebase Hosting. It is free at this scale, has a CDN, and is
already there.*

### 14. Custom domain?

You have other domains in `mi-zuri-com`. Want this on a subdomain, or is a
`*.web.app` URL fine?

*Recommendation: `*.web.app` to start; a domain is a five-minute change later.*

### 15. Public or invite-only at launch?

The strongest cost control is simply who can reach it.

*Recommendation: invite-only (an allowlist of emails) for the first week, then
open it once you have seen real per-game costs.*

---

## Scheduling

### 16. Ship after Phase 4, or hold for Phase 6?

Phases 0-4 give a complete, deployable **idea mode** game. News mode lands at
Phase 6 and is most of the remaining work — ingest, dossiers, safety, canon
beats, comparison.

*Recommendation: ship idea mode after Phase 4. It gets the thing in front of
people, proves the deployment and the cost model on the simpler half, and makes
Phase 5-6 lower risk.*

### 17. Replay fidelity

Full step-through of every turn with images and text (built) versus a condensed
transcript plus the ending comparison.

*Recommendation: keep the full step-through. It already works and it is the
more interesting artefact.*
