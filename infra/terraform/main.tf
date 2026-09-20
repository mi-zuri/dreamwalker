# Everything the deployed game needs, in one project.
#
# What is deliberately absent: a load balancer (Cloud Run's own domain
# mapping is free and this app does not need the features), Cloud SQL (the
# data is single-owner documents; see docs/decisions.md), Cloud Scheduler
# (news ingest is lazy - a scheduled job would cost more idle than the game
# costs playing), and an uptime check (polling a scale-to-zero service keeps
# it awake, which would turn a free idle month into a paid one).

locals {
  # Run as a dedicated identity rather than the default compute account, so
  # the grants below are the complete list of what the app can reach.
  sa_email = google_service_account.run.email
}

resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "firestore.googleapis.com",
    "firebaserules.googleapis.com",
    "identitytoolkit.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "iamcredentials.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# ── Image registry ──────────────────────────────────────────────────────

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = "dreamwalker"
  format        = "DOCKER"
  description   = "Dreamwalker service images"

  # Old revisions are only useful for a rollback, and three is as far back as
  # anyone would ever roll. Keeping more is pure storage cost.
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  depends_on = [google_project_service.required]
}

# ── Identity ────────────────────────────────────────────────────────────

resource "google_service_account" "run" {
  account_id   = "dreamwalker-run"
  display_name = "Dreamwalker Cloud Run service"
}

resource "google_project_iam_member" "run" {
  for_each = toset([
    "roles/aiplatform.user",   # text, image and embedding generation
    "roles/datastore.user",    # Firestore documents
    "roles/logging.logWriter", # structured logs
    "roles/monitoring.metricWriter",
    "roles/firebaseauth.viewer", # verifying ID tokens
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${local.sa_email}"
}

resource "google_storage_bucket_iam_member" "assets_writer" {
  bucket = var.assets_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.sa_email}"
}

# Generated images are served to the browser straight from Cloud Storage
# rather than proxied through the app, so the objects have to be readable.
# They are content-addressed hashes of a prompt: unguessable, and nothing in
# them is private.
resource "google_storage_bucket_iam_member" "assets_public" {
  bucket = var.assets_bucket
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# ── The one secret ──────────────────────────────────────────────────────

# Lyria RealTime is Gemini-API-only, so music is the only thing that needs a
# key; text and images authenticate as the service account above.
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "gemini_api_key" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.sa_email}"
}

# ── The service ─────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "app" {
  name     = "dreamwalker"
  location = var.region

  template {
    service_account                  = local.sa_email
    max_instance_request_concurrency = 80

    # Long enough for a 12-minute music session plus the handshake. Cloud Run
    # bills a WebSocket for its whole life, which is why the session cap
    # exists in the first place.
    timeout = "900s"

    # The service holds a generation job in memory between the POST that
    # starts it and the SSE stream that watches it, so a request has to reach
    # the instance that owns it. One instance guarantees that, and doubles as
    # the ceiling on what a bad day can cost. Zero minimum is what makes an
    # idle month free.
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }

        # Images and later scenes generate behind the player, after the
        # response that triggered them has already been sent. Throttled CPU
        # would stall exactly that work, so it stays allocated for the life
        # of the instance - which, at min_instance_count 0, is only while
        # someone is playing.
        cpu_idle          = false
        startup_cpu_boost = true
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = "global"
      }
      env {
        name  = "LLM_MODE"
        value = "live"
      }
      env {
        name  = "MUSIC_MODE"
        value = "realtime"
      }
      env {
        name  = "AUTH_MODE"
        value = "firebase"
      }
      env {
        name  = "INVITE_ONLY"
        value = "true"
      }
      env {
        name  = "ALLOWED_EMAILS"
        value = jsonencode(var.allowed_emails)
      }
      env {
        name  = "STORAGE_MODE"
        value = "firestore"
      }
      env {
        name  = "ASSETS_MODE"
        value = "gcs"
      }
      env {
        name  = "ASSETS_BUCKET"
        value = var.assets_bucket
      }
      # Same-origin: the container serves the frontend, so nothing is allowed
      # to call this API from anywhere else.
      env {
        name  = "CORS_ORIGINS"
        value = "[]"
      }
      env {
        name  = "MONTHLY_BUDGET_USD"
        value = tostring(var.monthly_budget_usd)
      }
      env {
        name  = "FIREBASE_API_KEY"
        value = var.firebase_web.api_key
      }
      env {
        name  = "FIREBASE_AUTH_DOMAIN"
        value = var.firebase_web.auth_domain
      }
      env {
        name  = "FIREBASE_APP_ID"
        value = var.firebase_web.app_id
      }
      env {
        name  = "FIREBASE_MESSAGING_SENDER_ID"
        value = var.firebase_web.messaging_sender_id
      }
      env {
        name  = "FIREBASE_STORAGE_BUCKET"
        value = var.firebase_web.storage_bucket
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 3
        period_seconds        = 3
        failure_threshold     = 10
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.gemini_api_key,
  ]
}

# Public, because the invite list is enforced one layer in: an uninvited
# visitor gets the login screen and nothing else. Keeping the service itself
# private would mean signed requests, which a browser cannot make.
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
