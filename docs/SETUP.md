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

## 2. Create the project (5 min)

**Use a new project, not `mi-zuri-com`.** Three reasons specific to what is
already there:

- A project gets exactly one default Firestore database, and both its
  **location and its mode are permanent** once created — neither can be changed
  later without deleting the database. `mi-zuri-com` has not initialised
  Firestore yet, so that one-shot choice is still unspent. Do not spend it on a
  game inside the project that hosts your website.
- `mi-zuri-com` has **no budget alerts**. This app costs money per play and runs
  an unattended ingest job on a schedule. In its own project its spend is one
  line in a billing report and a budget can target it exactly.
- Teardown becomes one reversible command instead of unpicking resources by hand.

Projects are free and the same billing account links to both.

### 2a. Point gcloud at the account that owns billing

```bash
gcloud config set account michal.zurawski10@gmail.com
```

Both your accounts are logged in, but only this one owns billing account
`01C6F0-6B1488-53CEC3`. Creating the project here means the billing link needs
no cross-account permissions. Your git identity does not have to match.

### 2b. Create the project and attach billing

```bash
gcloud projects create dreamwalker-app --name="Dreamwalker"
gcloud billing projects link dreamwalker-app \
  --billing-account=01C6F0-6B1488-53CEC3
gcloud config set project dreamwalker-app
```

Line 1 creates it. Line 2 attaches billing — **without this, every API call
fails**, because Vertex AI has no free tier. Line 3 makes it the default so you
can drop `--project` from later commands.

Project ids are globally unique. If you get `already exists`, pick another
(`dreamwalker-mz`, `dreamwalker-game`) and **use it everywhere below** — the
simplest way is to set it once:

```bash
export DW_PROJECT=dreamwalker-app     # or whatever you actually created
```

`export` lasts only for that terminal window. If you open a new one, run it
again before continuing.

Check it worked:

```bash
gcloud billing projects describe $DW_PROJECT
```

You want `billingEnabled: true`.

### 2c. Set a budget alert

Not strictly required, but this app spends per play and runs unattended. Do it
before anything can bill.

```bash
gcloud services enable billingbudgets.googleapis.com --project=$DW_PROJECT

DW_NUMBER=$(gcloud projects describe $DW_PROJECT --format="value(projectNumber)")

gcloud billing budgets create \
  --billing-account=01C6F0-6B1488-53CEC3 \
  --display-name="Dreamwalker" \
  --budget-amount=20USD \
  --filter-projects="projects/$DW_NUMBER" \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0
```

The filter needs the project *number*, not its id, which is why `DW_NUMBER` is
looked up first. You get email at 50%, 90% and 100% of $20/month, scoped to
this project only. A budget **alerts, it does not cap** — the hard spending
limits are the per-user and per-day caps built into the app itself.

---

## 3. Application Default Credentials (2 min)

Vertex AI (text and images) authenticates as *you* locally, via ADC. This is
the step that is currently blocking everything.

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project $DW_PROJECT
```

The first opens a browser — approve it. The second says which project gets
billed for the quota these credentials consume; without it you get
`Your application is authenticating by using local Application Default
Credentials` warnings and quota errors.

Check:

```bash
ls -l ~/.config/gcloud/application_default_credentials.json
```

Note this is **separate** from `gcloud auth login`. Both are needed and they do
different things: one authenticates the `gcloud` CLI, the other authenticates
code running on your machine.

---

## 4. Enable APIs and create the data stores (5 min, mostly waiting)

### 4a. APIs

A fresh project has almost nothing enabled, so this turns on everything the
project needs now and in later phases:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  firebase.googleapis.com \
  identitytoolkit.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project=$DW_PROJECT
```

What each is for: `aiplatform` is Vertex AI (text + images); `firestore` stores
saves and played-event ids; `firebase` + `identitytoolkit` are Google sign-in;
`run` + `cloudbuild` + `artifactregistry` deploy the backend in Phase 8;
`cloudscheduler` triggers the news ingest job; `secretmanager` holds the Gemini
key; `storage` holds images, audio and press photos.

This takes a minute or two. Verify:

```bash
gcloud services list --enabled --project=$DW_PROJECT | grep -E "aiplatform|firestore|identitytoolkit"
```

### 4b. Firestore

```bash
gcloud firestore databases create --location=eur3 --project=$DW_PROJECT
```

`eur3` is the Europe multi-region. **This is permanent** — the location and the
mode cannot be changed afterwards, only deleted and recreated. The default
`--type` is `firestore-native`, which is what we want; do not pass
`datastore-mode`.

### 4c. Storage bucket

```bash
gcloud storage buckets create gs://$DW_PROJECT-assets \
  --location=europe-central2 \
  --uniform-bucket-level-access \
  --project=$DW_PROJECT
```

Naming it after the project keeps it unique without thinking about it. Bucket
names are one global namespace, so if it is somehow taken, add a suffix and
tell me the name you used. `--uniform-bucket-level-access` means permissions
are IAM-only rather than per-object ACLs, which is the current default
recommendation and simpler to reason about.

---

## 5. Local config (2 min)

```bash
cd "/Users/michu/VSCode Projects/dreamwalker/backend"
cp .env.example .env
```

Copy your existing Gemini key across without ever printing it — it is only
needed for Lyria, which is not on Vertex AI:

```bash
cd "/Users/michu/VSCode Projects/dreamwalker"
grep '^GOOGLE_API_KEY=' server/.env \
  | sed 's/^GOOGLE_API_KEY=/GEMINI_API_KEY=/' >> backend/.env
```

Then open `backend/.env` and set the project (it is already open-able in your
editor):

```
GCP_PROJECT=dreamwalker-app
GCP_LOCATION=global
LLM_MODE=mock
MUSIC_MODE=realtime
```

`GCP_LOCATION=global` is where Vertex serves Gemini from. `LLM_MODE=mock` stays
until Phase 4 — the pipeline runs on recorded fixtures and spends nothing.
`backend/.env` is gitignored.

Check the key landed exactly once:

```bash
grep -c GEMINI_API_KEY backend/.env      # expect: 1
```

---

## 6. Verify the models, and measure Lyria (5 min)

```bash
cd "/Users/michu/VSCode Projects/dreamwalker/backend"
uv run python scripts/verify_models.py
```

This reads `backend/.env` itself, then calls all three models for real and
prints tokens, latency and cost. It spends a few cents. Expect
`text=PASS image=PASS music=PASS`.

If text reports that `gemini-3.5-flash-lite` is unavailable and it fell back to
`gemini-3.1-flash-lite`, that is a known possibility — tell me and I will pin
the fallback. To check the other two without opening a music session:

```bash
uv run python scripts/verify_models.py --skip-music
```

### The one thing only you can do

Lyria RealTime has **no published price**. The script measures how much audio it
produced but cannot price it. A few minutes after running it, open:

https://console.cloud.google.com/billing/01C6F0-6B1488-53CEC3/reports

Filter to today, group by SKU, and look for the Lyria or Generative Language
line. **Tell me that number.** It decides whether live music stays the default
or whether we fall back to the pregenerated loop library (~$1.20 once, then
free forever).

---

## 7. Firebase sign-in (5 min) — console only

There is no CLI for enabling an auth provider: it needs an OAuth consent screen
and an OAuth client, which only the console creates. Exact clicks:

1. Open https://console.firebase.google.com
2. **Create a project** → **Add Firebase to an existing Google Cloud project**,
   and pick `dreamwalker-app`. Do **not** let it create a new project.
3. Decline Google Analytics unless you want it.
4. Left sidebar → **Build** → **Authentication** → **Get started**.
5. **Sign-in method** tab → **Google** → toggle **Enable**.
6. Set the support email to your own address, then **Save**.
7. Gear icon → **Project settings** → **General** → scroll to **Your apps** →
   click the web icon **`</>`**.
8. Nickname it `dreamwalker-web`. Leave "Firebase Hosting" unticked — we decide
   hosting in Phase 8. **Register app**.
9. It shows a `firebaseConfig` object. Copy it.

Then save those values locally:

```bash
cd "/Users/michu/VSCode Projects/dreamwalker"
cat > web/.env.local <<'ENV'
VITE_FIREBASE_API_KEY=paste_apiKey_here
VITE_FIREBASE_AUTH_DOMAIN=paste_authDomain_here
VITE_FIREBASE_PROJECT_ID=paste_projectId_here
VITE_FIREBASE_APP_ID=paste_appId_here
ENV
```

These four values are **public by design** — they identify the project, they do
not authorise anything. Security comes from Firestore rules and the backend
verifying ID tokens. `web/.env.local` is gitignored anyway.

You can also just paste the `firebaseConfig` block into the chat and I will
wire it up.

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

## Appendix: steps 2–4 as one block

If you would rather paste once and read the explanations only if something
fails. Stop and check the output if any line errors.

```bash
set -e
export DW_PROJECT=dreamwalker-app
export DW_BILLING=01C6F0-6B1488-53CEC3

gcloud config set account michal.zurawski10@gmail.com
gcloud projects create "$DW_PROJECT" --name="Dreamwalker"
gcloud billing projects link "$DW_PROJECT" --billing-account="$DW_BILLING"
gcloud config set project "$DW_PROJECT"

gcloud services enable billingbudgets.googleapis.com --project="$DW_PROJECT"
DW_NUMBER=$(gcloud projects describe "$DW_PROJECT" --format="value(projectNumber)")
gcloud billing budgets create \
  --billing-account="$DW_BILLING" \
  --display-name="Dreamwalker" \
  --budget-amount=20USD \
  --filter-projects="projects/$DW_NUMBER" \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0

gcloud auth application-default login
gcloud auth application-default set-quota-project "$DW_PROJECT"

gcloud services enable \
  aiplatform.googleapis.com firestore.googleapis.com firebase.googleapis.com \
  identitytoolkit.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com \
  --project="$DW_PROJECT"

gcloud firestore databases create --location=eur3 --project="$DW_PROJECT"
gcloud storage buckets create "gs://$DW_PROJECT-assets" \
  --location=europe-central2 --uniform-bucket-level-access \
  --project="$DW_PROJECT"

echo "done - project $DW_PROJECT ready"
```

Steps 5 and 6 come next; step 7 is console-only.

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
