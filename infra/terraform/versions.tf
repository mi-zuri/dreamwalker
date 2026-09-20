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
