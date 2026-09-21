# On Google Cloud

What exists in the cloud project, why each piece is there, and how code gets
from a laptop to the live URL. To build it from nothing the first time, follow
[SETUP.md](SETUP.md) — this page is the reference, not the runbook.

Live at **https://dreamwalker.zur-i.com**.

## 1. The shape of it

**One Cloud Run service is the whole product.** It answers `/api/...` and
serves the React bundle from the same origin. Firebase Hosting in front of
Cloud Run is the usual arrangement and does not work here: Hosting's rewrites
drop the WebSocket upgrade, and the music socket is not optional. One origin
also means no CORS and one thing to deploy.

```
GitHub ──push to main──▶ Cloud Build ──▶ Artifact Registry ──▶ Cloud Run
                             ▲                                    │
                     Workload Identity                            ├─▶ Vertex AI
                     (no stored keys)                             ├─▶ Firestore
                                                                  ├─▶ Cloud Storage
                                                                  ├─▶ Secret Manager
                                                                  └─▶ Gemini API (music)
```

## 2. The inventory

Everything below is Terraform in `infra/terraform/`. Nothing is clicked into
existence except the four things in §6.

| Resource | Notes |
|---|---|
| **Cloud Run** `dreamwalker` | `europe-west1`. 0→1 instances, concurrency 80, 1 vCPU / 1 GiB, 900 s timeout, CPU always allocated, startup boost, public invoker. |
| **Artifact Registry** `dreamwalker` | Docker images, tagged with the commit sha. |
| **Firestore** `(default)` | `eur3`, which is why the service is in `europe-west1`. |
| **Cloud Storage** `<project>-assets` | Generated images and long turn logs. World-readable; the browser fetches them directly. |
| **Secret Manager** `gemini-api-key` | Lyria RealTime only. Text and images use the service account. |
| **Service account** `run` | The service's identity — see §3. |
| **Service account** `deploy` | GitHub's identity — see §5. |
| **Firestore rules** | Deny every read and write. |
| **Log metric + alert** | More than five `ERROR` logs in ten minutes → email. |
| **Billing budget** | 10 PLN/month with threshold alerts. |

APIs enabled: Run, Artifact Registry, Cloud Build, Vertex AI, Firestore,
Firebase Rules, Identity Toolkit, Secret Manager, Storage, Monitoring,
Logging, IAM Credentials.

**Idle cost is nothing.** No scheduler, no uptime check, no minimum instance,
no load balancer.

## 3. Identity

The service runs as its own account with five roles and no more:

| Role | For |
|---|---|
| `aiplatform.user` | text, image and embedding generation |
| `datastore.user` | Firestore documents |
| `storage.objectAdmin` (bucket-scoped) | writing generated images |
| `logging.logWriter`, `monitoring.metricWriter` | structured logs and metrics |
| `firebaseauth.viewer` | verifying ID tokens |

Application Default Credentials everywhere. **There is no service-account key
file** — not on the laptop, not in GitHub, not in the image.

The one credential that exists at all is the Gemini API key, because Lyria
RealTime is not on Vertex and has no ADC path. It lives in Secret Manager and
is mounted as an environment variable at start.

## 4. Configuration

The image is identical everywhere; the environment decides what it is. Cloud
Run sets `LLM_MODE=live`, `AUTH_MODE=firebase`, `STORAGE_MODE=firestore`,
`ASSETS_MODE=gcs`, `MUSIC_MODE=realtime`, the Firebase web identifiers, the
assets bucket, `MONTHLY_BUDGET_USD` and the invite list. `GEMINI_API_KEY`
comes from the secret.

Firebase identifiers are served to the browser from `/api/config` at startup
rather than compiled into the bundle, which is what lets one image run locally
and in production.

## 5. Deploying

### By hand

```bash
infra/scripts/deploy.sh
```

Creates the state bucket if missing, applies enough Terraform to have
somewhere to push an image, uploads the Gemini key on first run, builds on
Cloud Build, rolls out, and curls `/health`. To read the plan first:

```bash
cd infra/terraform
tofu plan -var image=europe-west1-docker.pkg.dev/<project>/dreamwalker/app:<sha>
```

A rollback is `tofu apply -var image=...:<older sha>`.

### From GitHub

`.github/workflows/ci.yml` runs lint, tests, evals, the frontend build and the
OpenAPI schema check on every push and PR. `.github/workflows/deploy.yml`
builds and rolls out every push to `main`.

**The deploy workflow holds no credentials.** GitHub's OIDC token is exchanged
for a Google one through Workload Identity Federation, and the provider only
trusts this repository. Wire it up once, from the Terraform outputs:

```bash
cd infra/terraform
gh variable set WORKLOAD_IDENTITY_PROVIDER -b "$(tofu output -raw github_workload_identity_provider)"
gh variable set DEPLOY_SERVICE_ACCOUNT     -b "$(tofu output -raw github_service_account)"
gh variable set GCP_PROJECT                -b "<project id>"
gh variable set GCP_REGION                 -b europe-west1
```

**CI never runs Terraform.** It ships code; changing what the infrastructure
*is* stays a deliberate act with a plan to read first.

### The invite list

`allowed_emails` in `terraform.tfvars` is the only thing between this project
and a stranger's imagination. Adding someone rolls a new revision and rebuilds
nothing:

```bash
$EDITOR infra/terraform/terraform.tfvars
cd infra/terraform && tofu apply -var image=<the image currently deployed>
```

## 6. What Terraform cannot do

Four things need a human in a console, once:

1. **Create the project and attach billing.**
2. **Enable Google sign-in** in the Firebase console, and add the custom
   domain to Firebase Auth's authorized domains — otherwise sign-in refuses
   it.
3. **Verify the domain** at [Search Console](https://search.google.com/search-console),
   under the same account that runs `gcloud`. The `TXT` record at the apex has
   to stay **permanently**: Google re-checks it, and removing it lapses the
   ownership the mapping depends on.
4. **Create the domain mapping**, which prints the DNS records to add —
   generated per mapping, not a fixed set copied from a guide:

```bash
gcloud beta run domain-mappings create --service=dreamwalker \
  --domain=dreamwalker.zur-i.com --region=europe-west1
```

Then wait. Certificate issuance took about **fifty minutes** here, inside a
stated window of 15 minutes to 24 hours. Until it finished, the mapping
reported the ACME challenge as "not visible through the public internet" while
DNS was already correct on every resolver checked. **That message means *not
yet*, not *misconfigured*.** Check `dig +short CNAME <domain>` against the
authoritative nameservers once; if it answers, wait rather than change
anything. Your own machine's DNS cache will also keep serving the old answer
long after the world has moved on.

Two region notes: domain mappings are **unsupported in `europe-central2`**
(hence `europe-west1`), and `europe-west1` sits inside Firestore's `eur3`.

## 7. Cost and what guards it

| | |
|---|---|
| Idle | **$0** — nothing runs, nothing is provisioned |
| A game | ~$0.19 measured live (Idea mode, end to end) |
| Hard cap | `MONTHLY_BUDGET_USD`, default $2.40, checked in Firestore *before* every game starts |
| Billing alert | 10 PLN/month, with threshold notifications |

The two numbers are deliberately different things: the app's cap is in USD
because that is the currency the models are priced in and it adds up tokens
and images, not invoice lines; the billing budget must be denominated in the
billing account's own currency and is a round 10 PLN rather than a converted
figure.

The real ceiling on images is not money — it is a **project-wide quota of two
image generations per minute**, which will not be raised.

## 8. Monitoring

A log metric counts `ERROR` records; more than five in ten minutes emails the
alert address. That is the whole of it, on purpose: an uptime check would poll
a scale-to-zero service and keep it awake, which would cost more than
everything else combined.

Logs are structured JSON. `gcloud run services logs read dreamwalker
--region europe-west1` is the fastest way in.

## 9. Deliberately absent

| Not there | Why |
|---|---|
| **Load balancer** | ~$18/month before serving a byte, against a ~$2.40 budget. Cloud Run's own domain mapping covers it. |
| **Cloud SQL** | Single-owner documents, and it cannot scale to zero. |
| **Cloud Scheduler** | News ingest is lazy; a scheduled job cost more idle than the game costs while being played. See [news-pipeline.md](news-pipeline.md). |
| **Uptime check** | Would defeat scale-to-zero. |
| **A separate dev project** | One project, three run modes, and local development spends nothing. |
