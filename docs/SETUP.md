# Setup — what you need to do by hand

Everything here is a one-off. Steps 1–2 work right now; 3–6 unblock the real
generation pipeline in Phase 2 and later. Nothing in the repo needs any of this
to run in mock mode.

Facts already confirmed on this machine, so you can skip checking them:

- `gcloud` is installed and both your accounts are logged in.
- Billing account `01C6F0-6B1488-53CEC3` is active and attached to `mi-zuri-com`.
- `mi-zuri-com` holds your sites: two static buckets, one scheduler job
  (`fetch-projects-hourly`), one secret (`github-token`), some BigQuery work.
  No Cloud Run services, no Firestore, no Firebase Auth, no budget alerts.
- Still missing everywhere: Application Default Credentials, the Vertex AI API,
  Firestore.

---

## 1. Play the current build (2 min)

```bash
cd "/Users/michu/VSCode Projects/dreamwalker"
bun install
bun run dev:web
```

Open http://localhost:5174 — sign-in is faked, everything runs on mock data.

Try: leave the idea box empty and press BEGIN for a news run; type something in
it for an idea run; switch `story language` and `interface` independently; click
`[mocks]` bottom-right to force error screens or jump between screens.

To run the API alongside it (health check only for now):

```bash
bun run dev          # web on :5174, backend on :8000
```

---

## 2. Create a project for the game (3 min)

**Use a new project, not `mi-zuri-com`.** Three reasons specific to what is
already there:

- A project has exactly one default Firestore database, and both its **location
  and its mode are permanent** once created — they cannot be moved or changed
  later without deleting the database. `mi-zuri-com` has not initialised
  Firestore yet, so that one-shot choice is still unspent. Do not spend it on a
  game inside the project that hosts your website.
- `mi-zuri-com` has **no budget alerts at all**. This app spends money per play
  and runs an unattended ingest job on a schedule. In its own project, its cost
  is one line in a billing report and a budget can target it exactly; shared, it
  is blended with your site's costs.
- Tearing the game down later is one command instead of unpicking Firestore,
  buckets, Cloud Run services, scheduler jobs and service accounts by hand.

Projects are free and the same billing account attaches to both, so this costs
nothing but the commands below.

```bash
gcloud projects create dreamwalker-app --name="Dreamwalker"
gcloud billing projects link dreamwalker-app \
  --billing-account=01C6F0-6B1488-53CEC3
gcloud config set project dreamwalker-app
```

Project ids are globally unique. If `dreamwalker-app` is taken, add a suffix
(`dreamwalker-app-mz`) and use that everywhere below.

Set a budget alert while you are here — the console is the quickest path:
https://console.cloud.google.com/billing/01C6F0-6B1488-53CEC3/budgets
Scope it to `dreamwalker-app` and set something you would not mind losing, e.g.
$20/month at 50/90/100%.

### Which account?

`gcloud` is active as **michal.zurawski10@gmail.com**, which owns the billing
account. Create the project with that account so billing links without
cross-account permission work. Your git identity
(michal.zurawski02@gmail.com) does not need to match.

## 3. Application Default Credentials (2 min) — **this is the current blocker**

Text and image generation go through Vertex AI, which authenticates with ADC.
This opens a browser window.

```bash
gcloud config set project dreamwalker-app
gcloud auth application-default login
gcloud auth application-default set-quota-project dreamwalker-app
```

Verify:

```bash
ls ~/.config/gcloud/application_default_credentials.json
```

---

## 4. Enable the remaining APIs (3 min, mostly waiting)

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  firebase.googleapis.com \
  identitytoolkit.googleapis.com \
  --project=dreamwalker-app
```

Create the Firestore database and the asset bucket (names must be globally
unique — change them if taken):

```bash
gcloud firestore databases create --location=eur3 --project=dreamwalker-app

gcloud storage buckets create gs://dreamwalker-app-assets \
  --location=europe-central2 --project=dreamwalker-app
```

Bucket names share one global namespace, so if that one is taken add a suffix
and tell me the name you used. Firestore's `eur3` location is **permanent** —
it cannot be changed later without deleting the database.

---

## 5. Local config file (1 min)

```bash
cd "/Users/michu/VSCode Projects/dreamwalker/backend"
cp .env.example .env
```

Then edit `backend/.env`:

```
GCP_PROJECT=dreamwalker-app
GCP_LOCATION=global
GEMINI_API_KEY=<your existing key>
LLM_MODE=mock
MUSIC_MODE=realtime
```

Your existing Gemini key is still in the old `server/.env` as `GOOGLE_API_KEY`.
To copy it across without printing it:

```bash
cd "/Users/michu/VSCode Projects/dreamwalker"
grep '^GOOGLE_API_KEY=' server/.env | sed 's/^GOOGLE_API_KEY=/GEMINI_API_KEY=/' >> backend/.env
```

`backend/.env` is gitignored.

---

## 6. Verify the models and measure what Lyria costs (5 min)

```bash
cd "/Users/michu/VSCode Projects/dreamwalker/backend"
uv run python scripts/verify_models.py
```

Expect all three to pass. If the text check reports that `gemini-3.5-flash-lite`
is unavailable and it fell back to `gemini-3.1-flash-lite`, that is fine —
tell me and I will pin the fallback.

**The one thing only you can do:** Lyria RealTime has no published price. The
script streams ~20 seconds of audio and prints how much it produced, but not
what it cost. A few minutes later, check:

https://console.cloud.google.com/billing/01C6F0-6B1488-53CEC3/reports?project=dreamwalker-app

Filter to today and look for the Lyria / Generative Language line. Tell me the
number. It decides whether live music stays the default or whether we switch to
the pregenerated loop library (~$1.20 one-off, then free).

To skip the music check while testing the other two:

```bash
uv run python scripts/verify_models.py --skip-music
```

---

## 7. Firebase sign-in (5 min, console only) — needed for Phase 2

Google sign-in cannot be enabled from the CLI.

1. Go to https://console.firebase.google.com and click **Add project**.
2. Choose the **existing** `dreamwalker-app` project rather than creating a new one.
3. **Build → Authentication → Get started → Sign-in method → Google → Enable**, then save.
4. **Project settings → General → Your apps → Web (`</>`)**, register an app called
   `dreamwalker-web`, and copy the `firebaseConfig` block it shows you.
5. Paste that block into this chat, or save it to `web/.env.local` as:

```
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_APP_ID=...
```

These are public by design — they identify the project, they do not authorise
anything. `web/.env.local` is gitignored.

---

## 8. Answer the open design questions

Five are still open from the plan (`~/.claude/plans/task-plan-a-rosy-tulip.md`,
Part I). None block Phase 2, but #6 shapes how much gets built before launch:

1. Keep the name **DREAMWALKER**? (I kept it; it is a one-line change.)
2. Idea-mode ending has no match score — already built that way. Confirm?
3. Should idea mode also avoid repeating *ideas* per player, or only style cards?
4. Replay: full step-through (built) or a condensed transcript?
5. A Polish player picking world news gets the story in Polish. Intended?
6. **Ship idea mode publicly after Phase 4, or hold launch until news mode lands
   at Phase 6?**

---

## If you ever want it gone

Because the game lives in its own project, removing it completely is:

```bash
gcloud projects delete dreamwalker-app
```

That is reversible for 30 days, then permanent.

---

## Quick reference

| What | Command |
|---|---|
| Play the mock build | `bun run dev:web` |
| Web + backend together | `bun run dev` |
| Backend only | `bun run dev:backend` |
| Regenerate frontend API types | `bun run gen:api` (backend must be running) |
| Backend tests | `bun run test` — exits 5 ("no tests ran") until Phase 3 adds the map validator suite |
| Typecheck + build the web app | `cd web && bunx tsc --noEmit && bun run build` |
| Verify models | `cd backend && uv run python scripts/verify_models.py` |
