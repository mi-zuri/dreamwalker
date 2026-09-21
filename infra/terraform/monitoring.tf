# No uptime check on purpose. Polling a scale-to-zero service keeps an
# instance alive around the clock, which would cost more than the game does.
# What is left is the two things that can actually go wrong unattended: the
# app starts logging errors, or it starts spending money.

resource "google_monitoring_notification_channel" "email" {
  display_name = "Dreamwalker alerts"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.required]
}

resource "google_logging_metric" "errors" {
  name   = "dreamwalker/errors"
  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${google_cloud_run_v2_service.app.name}"
    severity>=ERROR
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "errors" {
  display_name = "Dreamwalker is logging errors"
  combiner     = "OR"

  conditions {
    display_name = "More than five errors in ten minutes"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.errors.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      # Non-zero on purpose: Cloud Monitoring refuses to accept an explicit
      # missing-data policy without one, and a five-minute floor also keeps a
      # single bad minute from paging anybody.
      duration = "300s"

      aggregations {
        alignment_period   = "600s"
        per_series_aligner = "ALIGN_SUM"
      }

      # A scale-to-zero service reports nothing most of the time. Without
      # this, every quiet night would open an incident.
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    auto_close = "3600s"
  }
}

# The app stops itself at `monthly_budget_usd` before it generates anything,
# so this is the backstop for the costs it does not control: storage, egress,
# and anything a mistake in that check lets through.
#
# Denominated in PLN, because a budget must use the billing account's own
# currency - USD here is rejected as an invalid argument, with no hint as to
# which argument. This adopts the 30 PLN budget created during setup and
# brings it down to 10.
resource "google_billing_budget" "monthly" {
  count    = var.billing_account == "" ? 0 : 1
  provider = google.billing

  billing_account = var.billing_account
  display_name    = "Dreamwalker monthly"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = var.billing_budget.currency
      units         = tostring(var.billing_budget.amount)
    }
  }

  # Half, spent, and over. The first is the one worth reading.
  dynamic "threshold_rules" {
    for_each = [0.5, 1.0, 1.5]
    content {
      threshold_percent = threshold_rules.value
    }
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }
}

data "google_project" "this" {
  project_id = var.project_id
}
