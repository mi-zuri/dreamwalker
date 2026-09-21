#!/usr/bin/env bash
#
# Build the image and roll out the infrastructure that runs it.
#
# Safe to run repeatedly: everything here is either idempotent or handled by
# Terraform's own plan. Reads its settings from infra/terraform/terraform.tfvars.
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT="$PWD"
TF_DIR="$ROOT/infra/terraform"
TF="${TF:-tofu}"

tfvar() {
  # Values in terraform.tfvars are the single source of truth; reading them
  # back here keeps the script from growing a second, drifting copy.
  sed -n "s/^${1}[[:space:]]*=[[:space:]]*\"\(.*\)\"[[:space:]]*$/\1/p" "$TF_DIR/terraform.tfvars" | head -1
}

PROJECT="$(tfvar project_id)"
REGION="$(tfvar region)"
: "${PROJECT:?set project_id in infra/terraform/terraform.tfvars}"
REGION="${REGION:-europe-west1}"

STATE_BUCKET="${PROJECT}-tfstate"
REPO="${REGION}-docker.pkg.dev/${PROJECT}/dreamwalker"
TAG="$(git rev-parse --short HEAD)$(git diff --quiet || echo -dirty)"
IMAGE="${REPO}/app:${TAG}"

echo "==> project ${PROJECT}, region ${REGION}, image ${IMAGE}"

# ── State bucket ────────────────────────────────────────────────────────
# Private and versioned, and deliberately not the assets bucket: that one is
# world-readable so the browser can fetch images straight from it, and state
# holds the invite list.
if ! gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="$PROJECT" >/dev/null 2>&1; then
  echo "==> creating state bucket gs://${STATE_BUCKET}"
  gcloud storage buckets create "gs://${STATE_BUCKET}" \
    --project="$PROJECT" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning
fi

cd "$TF_DIR"
$TF init -upgrade -reconfigure \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="prefix=terraform/state"

# ── Enough infrastructure to hold an image ──────────────────────────────
# The registry has to exist before there is anything to build into it, and
# the secret before the service that mounts it. Everything else waits.
$TF apply -auto-approve -var "image=${IMAGE}" \
  -target=google_project_service.required \
  -target=google_artifact_registry_repository.app \
  -target=google_secret_manager_secret.gemini_api_key

# ── The music key ───────────────────────────────────────────────────────
# Only added when the secret has no version yet; rotating it is a deliberate
# act, not a side effect of deploying.
if ! gcloud secrets versions describe latest --secret=gemini-api-key --project="$PROJECT" >/dev/null 2>&1; then
  KEY="$(sed -n 's/^GEMINI_API_KEY=//p' "$ROOT/backend/.env" | head -1)"
  if [ -z "$KEY" ]; then
    echo "!! no GEMINI_API_KEY in backend/.env; music will fall back to loops" >&2
  else
    printf '%s' "$KEY" | gcloud secrets versions add gemini-api-key --data-file=- --project="$PROJECT"
    echo "==> added the first version of gemini-api-key"
  fi
fi

# ── Build ───────────────────────────────────────────────────────────────
cd "$ROOT"
echo "==> building"
# The build pushes both `$IMAGE` and the `latest` cache tag; see
# infra/cloudbuild.yaml for why the tag is not moved afterwards.
gcloud builds submit --project="$PROJECT" --config=infra/cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE},_CACHE=${REPO}/app:latest" .

# ── Roll out ────────────────────────────────────────────────────────────
cd "$TF_DIR"
$TF apply -auto-approve -var "image=${IMAGE}"

URL="$($TF output -raw url)"
echo
echo "==> live at ${URL}"
echo "==> checking it answers"
curl -fsS "${URL}/health" && echo
