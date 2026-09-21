# The news pipeline

How News mode gets from "six RSS feeds" to "a playable event with a fact
timeline and a beat graph". Code lives in `backend/app/news/`.

```
sources ─▶ normalize ─▶ cluster ─▶ score ─▶ pool ─┐
 free        free       embeddings   1 call       │   refreshed lazily
                                                  ▼
                                    pick ─▶ enrich ─▶ brief ─▶ the game
                                  per player   per event, cached
```

## There is no scheduler

The original plan was a Cloud Scheduler job every 48 hours. At roughly $0.30 a
region a run that is about **$9 a month, spent whether or not anyone plays** —
most of a 10 PLN budget. So ingest is **lazy**: a News game checks whether the
region's pool is thin or stale and refreshes it first if it is. Nobody playing
means nothing spent.

That is only affordable because the expensive half was moved. A refresh
collects, clusters and scores — free feeds, a fraction of a cent of
embeddings, one batched scoring call. Reading articles and writing a beat
graph happens **per event, on the way into a game**, and is cached on the
event afterwards.

A refresh triggers when the pool has never been filled, holds fewer than
`POOL_MIN_PLAYABLE` playable events (12), or was last refreshed more than
`POOL_MAX_AGE_HOURS` (6) ago.

## 1. Sources

A source is anything that can produce `Article`s **without a model call**.
That is the whole interface, and it is deliberately narrow: collection is the
free part of the pipeline and stays free by having nowhere to put a model.

**World — English Wikipedia Current Events** is the only importance-filtered
source in the system. `Portal:Current_events/<date>` is a human-curated list
of the day's significant events, ~35–40 bullets a day, each with its own
citations, and *any past date is fetchable* — so a cold pool can be filled
from yesterday rather than waiting for news to happen. Bullets without a
citation are headings or context and are dropped. Plus BBC World, Guardian
World and NYT World as RSS.

**Poland — category feeds.** No Polish equivalent of the current-events portal
exists (`pl.wikipedia.org` answers `missingtitle`). Feed choice was measured,
not guessed: a category feed carries fewer items per hour than a firehose and
therefore reaches *further back in time* with the same fifty entries.

| Feed | Items | Time span |
|---|---|---|
| `wiadomosci.onet.pl/.feed` (firehose) | 20 | **5.3 h** |
| `rmf24.pl/fakty/feed` (firehose) | 51 | 22.9 h |
| `polsatnews.pl/rss/wszystkie.xml` (firehose) | 50 | 31.9 h |
| `rmf24.pl/fakty/polska/feed` (category) | 50 | **34.9 h** |
| `polsatnews.pl/rss/polska.xml` (category) | 50 | **54.3 h** |

For a pool that refreshes on demand rather than on a schedule, depth beats
freshness. Also in the Polish set: `tvn24.pl/najnowsze.xml`.

`feeds.reuters.com` is absent because it is dead — it fails to connect — not
by oversight. GDELT was considered as an importance signal and left out: its
limit is one request per 5 s per IP and sustained querying triggers blocks
that no retry interval clears.

Feeds are fetched with `httpx` and only then handed to `feedparser`, rather
than letting feedparser do its own networking. That is what makes every source
recordable: tests replay captured responses through `respx` and never touch
the network. A source that fails is skipped and logged — losing one feed
should cost a little pool depth, not a region.

## 2. Normalize

Every entry becomes an `Article` with a **canonical URL**: scheme and host
lowered, `www.` dropped, tracking parameters (`utm_*`, `fbclid`, `gclid`, …)
stripped, trailing slash removed. This does more work than it looks like —
two outlets syndicating the same wire story, or one outlet linking its own
article from three places, collapse to one URL and are deduped before
clustering has to think about them. Feed summaries arrive as HTML fragments
more often than not, so they are tag-stripped here.

## 3. Cluster

Six Polish feeds covering one afternoon produce the same story four or five
times over. Clustering turns "238 articles" into "about forty things that
happened", and gives each event its **source diversity** — the strongest
available signal that something actually mattered.

Greedy single-pass agglomeration over embeddings, newest first. Not the best
clustering algorithm, but the one whose failure mode is right: an article
matching nothing starts its own cluster, so the worst case is a duplicate
event rather than a lost one.

Two articles join only if they are within **72 hours** *and* score
**cosine ≥ 0.88** *and* share a distinctive word. That last condition is not
decoration. Measured on 120 real Polish articles: the same story scores
0.89–0.94, and two unrelated fatal road accidents score 0.89. **Cosine alone
cannot separate them at any threshold.** A token appearing in more than 2% of
the batch is a genre word — *tragedia*, *kierowca*, *minister* — and does not
count as distinctive.

## 4. Score

Split deliberately in two.

**Importance is computed, not asked.** How many outlets carried it, how many
*distinct* outlets, how recent it is — those are facts about the pool. A model
asked to rate them would be guessing at something that can be counted, and
counting is free, deterministic and testable.

**Interest, playability and safety are asked**, once, for a whole region, in
batches of 25. Playability does the most work: an event can be the most
important thing that happened and still be unplayable, because there is no
place to stand in it and nothing for a person to do. The call also returns
which protagonist roles the event could plausibly contain, and — for
`safe_mode` — a one-sentence content note.

Only the top 80 by computed importance are sent for judgement. A Polish
refresh clusters into ~160 events, most of them one article from one outlet;
scoring all of them would triple the bill to rank things that were never going
to reach the pool.

**Safety is classified here** rather than at game start, so a `blocked` event
never enters the pool at all.

## 5. The pool

The pool **accumulates**. A refresh adds what it found and expires what has
aged out; it never replaces. A failed run, or a source that goes down, leaves
yesterday's pool exactly where it was — which is the property that makes
refreshing on demand safe. The worst outcome of a bad refresh is a slightly
staler pool, never an empty one.

An event already enriched keeps its dossier and photos through a re-ingest,
because those cost real money.

| | |
|---|---|
| Lifetime | 7 days, then it reads as history |
| Offered | `playable` and rank ≥ 0.35 |
| Shown to the player | the top 7 they have not seen, by **importance** |
| Drawn for them | the top 12 they have not seen |
| Weighting | rank × 1.6 if fresh × 0.55 per repeat of the same subject |

There are two ways out of the pool, and they order it differently.

**The player chooses.** News mode shows seven stories and they pick one. That
list is ordered by `importance` — what actually mattered — rather than by
`rank`, which weights playability highest. Playability still filters: an event
nobody can act inside is not a game however large it was. It just stops
deciding the order, because the question a player is answering is "which of
these do I want to live through", not "which of these makes the best game".

**The machine chooses**, which is what `LLM_MODE=mock` and any future
unattended path do. That draw is weighted-random over the top 12 rather than
"take the best": always serving the highest-ranked event would mean every
player in a day plays the same thing, and would make the pool's depth
pointless.

## 6. Per-player dedup

Per player **only**. Two strangers drawing the same event is not a problem
worth solving, and solving it would make one player's variety depend on
everyone else's.

Either test is enough: a **shared canonical URL** (exact and cheap; catches
the same story re-clustered under a new id on a later run), or an **embedding
within cosine 0.93 inside a ±14-day window**. Cluster ids drift between runs,
so the id is never trusted alone.

0.93 is deliberately strict. "Another rocket landing" and "another brawl in
the Sejm" are supposed to pass as new events; only something recognisably the
same story is blocked. Comparison is brute-force cosine in Python against the
handful of events *that player* has seen — no vector index.

## 7. Enrich — the scraping

This is the expensive half, and it runs for one event at a time, only when
somebody is about to play it. The result is cached on the event, so the second
player to draw a story pays nothing for the dossier the first one paid for.

**Fetching article bodies.** A feed summary is one or two sentences: enough to
cluster and score, nowhere near enough for a dossier. Up to **4 articles per
event** are fetched in full, **6000 characters** kept from each — past that it
is comment threads and related links, and it is the dossier prompt's input
bill.

Two rules constrain this and both are checked, not assumed:

* **robots.txt**, fetched once per host and cached. None of the chosen outlets
  disallow article paths for `*`, but that is a fact that can change, and this
  re-checks it rather than trusting a note in a design document.
* **NYT is summary-only**, on ToS grounds rather than robots grounds. Its
  bodies are never fetched, however permissive its robots file is.

Requests carry an identifying user agent
(`dreamwalker/0.1 (student project; contact via repository)`) and a 12-second
timeout. There is no readability library: a news article's body is what is
inside its `<p>` tags, and the failure mode of getting that slightly wrong is
a dossier with a little navigation furniture in it, which the dossier stage
ignores.

**The dossier** is one model call over those bodies: who, what, where, when; a
fact timeline with per-fact sources and a certainty rating; conflicting
claims; and people tagged `public_figure` or `private`. **Private individuals
are dropped here**, not in a prompt later, so nothing downstream ever holds a
name it could leak.

**The canon beats** come out of the same stage — 3 to 5 of them. Fewer than
three is not a story; more than five will not fit a ten-minute game. They come
from the dossier, not from the plan: the plan decides where the player walks,
but what actually happened is not its to invent.

**Press photos.** Up to 4 per event are downloaded to Cloud Storage with their
source URL and credit, capped at 6 MB each (bigger than that is a hero banner
or an ad). Every one gets a **vision safety check** that also writes a
caption.

**Photo matching**, at game start, is therefore a *text* call over those
captions and the location descriptions — a few hundred tokens instead of
re-uploading four images, using exactly the same information. Every photo that
lands on a location saves a generated one, which matters more than the money:
generated images are capped at two a minute, press photos are not capped at
all.

Everything here stays in the **source language**. Translating the dossier
would be a separate call and a separate bill; instead the scene stage is
handed the dossier as it stands plus an instruction about which language to
write in, and does the adaptation inside a call it was making anyway.

## 8. When it goes wrong

| Failure | What happens |
|---|---|
| One source down | Skipped and logged; the rest still collect |
| Every source down | The existing pool is served untouched |
| No article bodies | Summary-only dossier, flagged low-confidence, fewer beats |
| Dossier too thin | Event dropped, the next candidate is drawn |
| Player's pool exhausted | `pool_empty` — a friendly "come back later" |
| Event classified `blocked` | Never entered the pool in the first place |

## 9. Running it by hand

```bash
cd backend
uv run python -m app.news.cli collect --region pl    # fetch and dedup only
uv run python -m app.news.cli refresh --region pl    # collect, cluster, score, merge
uv run python -m app.news.cli show    --region pl    # what is currently playable
```

Every source has recorded HTTP fixtures, so the whole pipeline runs offline
under `LLM_MODE=fake` in the test suite — cluster counts, scores, dedup
decisions and pool accumulation are all asserted without touching the network.
