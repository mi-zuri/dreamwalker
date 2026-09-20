terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # State lives in the assets bucket, under its own prefix. One bucket is
  # enough for a project this size, and it means `tofu init` needs nothing
  # that does not already exist.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# The Billing Budgets API bills its quota to a project you name, and local
# ADC does not name one - so a plain provider gets a 403 pointing at Google's
# own shared client project. Only the budget needs this, so only the budget
# gets it: a blanket `user_project_override` would put the header on every
# call this configuration makes.
provider "google" {
  alias                 = "billing"
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}
