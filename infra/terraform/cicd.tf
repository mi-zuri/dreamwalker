# GitHub Actions deploys without a service-account key: it presents its own
# OIDC token and federation exchanges it for a short-lived Google one. A key
# file in a repo secret would be a permanent credential sitting in a place
# neither of us can rotate from.

locals {
  cicd = var.github_repo == "" ? 0 : 1
}

resource "google_iam_workload_identity_pool" "github" {
  count                     = local.cicd
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = local.cicd
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # Without this, any repository on GitHub could mint a token for this pool.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deploy" {
  count        = local.cicd
  account_id   = "dreamwalker-deploy"
  display_name = "Dreamwalker CI deploys"
}

resource "google_service_account_iam_member" "deploy_from_github" {
  count              = local.cicd
  service_account_id = google_service_account.deploy[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repo}"
}

resource "google_project_iam_member" "deploy" {
  for_each = local.cicd == 0 ? toset([]) : toset([
    "roles/run.admin",                # roll out a new revision
    "roles/artifactregistry.writer",  # read the image it is about to deploy
    "roles/cloudbuild.builds.editor", # build it in the first place
    "roles/storage.admin",            # Cloud Build's staging bucket
    "roles/logging.viewer",           # read a failed build's logs
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.deploy[0].email}"
}

# Deploying a revision means assigning it an identity, which counts as using
# that identity - so the deployer must be allowed to act as the runtime
# account, and as nothing else.
resource "google_service_account_iam_member" "deploy_acts_as_run" {
  count              = local.cicd
  service_account_id = google_service_account.run.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy[0].email}"
}

# Cloud Build needs an identity of its own.
#
# `gcloud builds submit` with no `--service-account` runs the build as the
# Compute Engine default account, which carries `roles/editor`. Letting the
# deployer act as that would hand CI edit rights over the whole project
# through the back door - the opposite of the binding above, which is
# deliberately narrow. So builds get an account with the three permissions a
# build actually needs, and the deployer may act as that and nothing else.
#
# This only works because `infra/cloudbuild.yaml` already sets
# `options.logging: CLOUD_LOGGING_ONLY`: a custom service account is rejected
# while a build still expects to write its logs to a bucket.
resource "google_service_account" "build" {
  count        = local.cicd
  account_id   = "dreamwalker-build"
  display_name = "Dreamwalker Cloud Build"
}

resource "google_project_iam_member" "build" {
  for_each = local.cicd == 0 ? toset([]) : toset([
    "roles/logging.logWriter",       # the build's own logs
    "roles/artifactregistry.writer", # push the image, pull the cache layer
    # Read the source tarball the deployer uploaded. Project-scoped rather
    # than bound to `<project>_cloudbuild`, because that bucket is created by
    # the first build and so does not exist on a fresh apply.
    "roles/storage.objectViewer",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.build[0].email}"
}

resource "google_service_account_iam_member" "deploy_acts_as_build" {
  count              = local.cicd
  service_account_id = google_service_account.build[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy[0].email}"
}
