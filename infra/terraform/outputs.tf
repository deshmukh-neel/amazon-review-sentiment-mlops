output "service_url" {
  description = "Public ReviewSignal Cloud Run URL."
  value       = google_cloud_run_v2_service.api.uri
}

output "data_bucket" {
  value = google_storage_bucket.data.name
}

output "model_bucket" {
  value = google_storage_bucket.models.name
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.containers.name
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "github_deployer_service_account" {
  value = google_service_account.github_deployer.email
}

output "github_plan_service_account" {
  value = google_service_account.github_plan.email
}

output "github_promoter_service_account" {
  value = google_service_account.github_promoter.email
}

output "production_model_manifest_uri" {
  value = local.production_model_manifest_uri
}
