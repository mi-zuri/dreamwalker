output "url" {
  description = "The public URL of the game."
  value       = google_cloud_run_v2_service.app.uri
}

output "image_repository" {
  description = "Where deploy.sh pushes images."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}

output "run_service_account" {
  description = "The identity the app runs as."
  value       = google_service_account.run.email
}

output "github_workload_identity_provider" {
  description = "Value for the GitHub Actions `workload_identity_provider` input."
  value       = local.cicd == 0 ? "" : google_iam_workload_identity_pool_provider.github[0].name
}

output "github_service_account" {
  description = "Value for the GitHub Actions `service_account` input."
  value       = local.cicd == 0 ? "" : google_service_account.deploy[0].email
}
