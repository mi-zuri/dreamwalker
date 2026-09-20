variable "project_id" {
  description = "GCP project that owns everything here."
  type        = string
}

variable "region" {
  description = <<-EOT
    Cloud Run region. europe-west1 is not arbitrary: it is inside Firestore's
    eur3 multi-region, so every state read is in-region, and it is one of the
    regions where Cloud Run can map a custom domain without a load balancer.
    europe-central2 is closer to Warsaw but supports neither.
  EOT
  type        = string
  default     = "europe-west1"
}

variable "assets_bucket" {
  description = "Bucket for generated images and captured music loops."
  type        = string
}

variable "image" {
  description = "Full Artifact Registry image reference to deploy."
  type        = string
}

variable "allowed_emails" {
  description = <<-EOT
    The invite list. Anyone signing in with a Google account outside it is
    refused at the door, before any generation happens. This is the strongest
    cost control the app has, which is why it has no default.
  EOT
  type        = list(string)
}

variable "alert_email" {
  description = "Where error-rate and budget alerts go."
  type        = string
}

variable "billing_account" {
  description = "Billing account id, for the budget alert. Empty skips it."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = <<-EOT
    The hard cap the app enforces on itself before every generation, and the
    amount the billing alert watches. Roughly 10 PLN.
  EOT
  type        = number
  default     = 2.40
}

variable "github_repo" {
  description = "owner/name of the repo allowed to deploy via Workload Identity."
  type        = string
  default     = ""
}

variable "firebase_web" {
  description = <<-EOT
    The browser's Firebase config. Public values - they name the project and
    authorise nothing - served to the frontend at runtime from /api/config.
  EOT
  type = object({
    api_key             = string
    auth_domain         = string
    app_id              = string
    messaging_sender_id = string
    storage_bucket      = string
  })
}
