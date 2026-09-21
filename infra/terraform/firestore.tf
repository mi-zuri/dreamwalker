# Every Firestore read and write goes through the backend's Admin SDK, which
# bypasses these rules entirely. They exist to make sure nothing *else* can:
# the web SDK ships in the bundle with the project id, and without this a
# stranger could read the database straight from a browser console.
resource "google_firebaserules_ruleset" "firestore" {
  project = var.project_id

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/firestore.rules")
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_firebaserules_release" "firestore" {
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name
  project      = var.project_id

  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.firestore]
  }
}
