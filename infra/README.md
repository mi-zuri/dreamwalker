# infra

Everything needed to run Dreamwalker somewhere other than a laptop.

```
Dockerfile              one image: the API, with the built frontend inside it
cloudbuild.yaml         how that image gets built (on Cloud Build, not locally)
scripts/deploy.sh       build, roll out, check it answers
terraform/              the project: registry, identity, secret, service, alerts
```

## The shape of it

One Cloud Run service is the whole product. It answers `/api/...` and serves the
React bundle from the same origin, which is not the usual arrangement — Firebase
Hosting in front of Cloud Run would be — but Hosting's rewrites drop the
WebSocket upgrade and the music socket is not optional. One origin also means no
CORS and one thing to deploy.

| | |
|---|---|
| Region | `europe-west1` — inside Firestore's `eur3`, and able to map a custom domain without a load balancer |
| Scaling | 0 to 1 instances, concurrency 80, CPU always allocated |
| Data | Firestore `(default)`, rules denying every non-admin caller |
| Images | `gs://<project>-assets`, world-readable, fetched directly by the browser |
| Secret | `gemini-api-key` — Lyria RealTime only; text and images use the service account |
| Idle cost | nothing: no scheduler, no uptime check, no minimum instance |

## Deploying

Once, per machine:

```bash
brew install opentofu          # or use terraform; the config is plain HCL
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
$EDITOR infra/terraform/terraform.tfvars
```

Then, as often as you like:

```bash
infra/scripts/deploy.sh
```

It creates the state bucket if it is missing, applies enough Terraform to have
somewhere to push an image, uploads the Gemini key the first time, builds on
Cloud Build, rolls out, and curls `/health`. The image is tagged with the commit
sha, so a rollback is `tofu apply -var image=...:<older sha>`.

`deploy.sh` runs `tofu apply -auto-approve`. To read the plan first:

```bash
cd infra/terraform
tofu plan -var image=europe-west1-docker.pkg.dev/<project>/dreamwalker/app:<sha>
```

## The invite list

`allowed_emails` in `terraform.tfvars` is the only thing standing between this
project and a stranger's imagination. Adding someone:

```bash
$EDITOR infra/terraform/terraform.tfvars    # add the address
cd infra/terraform && tofu apply -var image=<the image currently deployed>
```

That rolls a new revision with the new environment. Nothing rebuilds.

## Continuous deployment

`.github/workflows/deploy.yml` builds and rolls out every push to `main`. It
holds no credentials: GitHub's OIDC token is exchanged for a Google one, and the
federation provider only trusts this repository. After the first `tofu apply`,
wire it up with the outputs:

```bash
cd infra/terraform
gh variable set WORKLOAD_IDENTITY_PROVIDER -b "$(tofu output -raw github_workload_identity_provider)"
gh variable set DEPLOY_SERVICE_ACCOUNT     -b "$(tofu output -raw github_service_account)"
gh variable set GCP_PROJECT                -b "$(tofu output -raw run_service_account | cut -d@ -f2 | cut -d. -f1)"
gh variable set GCP_REGION                 -b europe-west1
```

CI never runs Terraform. It ships code; changing what the infrastructure *is*
stays a deliberate act with a plan to read first.

## A custom domain

Cloud Run will map `dreamwalker.zur-i.com` directly, with a managed certificate
and no load balancer — but only once Google can see that you own `zur-i.com`,
which means verifying it at [Search Console](https://search.google.com/search-console).
That is the one step no script can do for you. Afterwards:

```bash
gcloud beta run domain-mappings create --service=dreamwalker \
  --domain=dreamwalker.zur-i.com --region=europe-west1
```

It prints the DNS records to add, then takes anywhere from 15 minutes to a day
to issue the certificate. Add the domain to Firebase Auth's authorized domains
at the same time, or Google sign-in will refuse it.

## What is deliberately not here

- **A load balancer.** ~$18/month before it serves a byte, against a budget of
  about $2.40. Cloud Run's own domain mapping covers what this needs.
- **Cloud SQL.** The data is single-owner documents, and Cloud SQL cannot scale
  to zero. See `docs/decisions.md`.
- **Cloud Scheduler.** News ingest is lazy by design; a scheduled job cost more
  idle than the game costs while being played.
- **An uptime check.** Polling a scale-to-zero service keeps it awake, which
  would cost more than everything else combined.
