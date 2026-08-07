resource "google_service_account" "runtime" {
  account_id   = "reviewsignal-runtime"
  display_name = "ReviewSignal Cloud Run runtime"
}

resource "google_service_account" "trainer" {
  account_id   = "reviewsignal-trainer"
  display_name = "ReviewSignal candidate training job"
}

resource "google_service_account" "scheduler" {
  account_id   = "reviewsignal-scheduler"
  display_name = "ReviewSignal monthly job scheduler"
}

resource "google_service_account" "github_deployer" {
  account_id   = "reviewsignal-github"
  display_name = "ReviewSignal GitHub Actions deployer"
}

resource "google_service_account" "github_plan" {
  account_id   = "reviewsignal-github-plan"
  display_name = "ReviewSignal GitHub Terraform plan"
}

resource "google_storage_bucket_iam_member" "runtime_model_reader" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "trainer_data_writer" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.trainer.email}"

  condition {
    title       = "create_versioned_splits_only"
    description = "The candidate job can create immutable versioned data but cannot replace or delete it."
    expression  = "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/versions/')"
  }
}

resource "google_storage_bucket_iam_member" "trainer_model_writer" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.trainer.email}"

  condition {
    title       = "create_candidates_only"
    description = "The training job can create immutable candidates but cannot modify production objects."
    expression  = "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.models.name}/objects/candidates/')"
  }
}

resource "google_storage_bucket_iam_member" "deployer_model_writer" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_project_iam_member" "github_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/run.developer",
    "roles/serviceusage.serviceUsageConsumer",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_project_iam_member" "github_plan_viewer" {
  project = var.project_id
  role    = "roles/viewer"
  member  = "serviceAccount:${google_service_account.github_plan.email}"
}

resource "google_service_account_iam_member" "github_uses_runtime_identity" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_service_account_iam_member" "github_uses_trainer_identity" {
  service_account_id = google_service_account.trainer.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "reviewsignal-github"
  display_name              = "ReviewSignal GitHub Actions"
  description               = "Short-lived credentials for the exact public repository"
  disabled                  = false

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"
  disabled                           = false

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
    "attribute.workflow"   = "assertion.workflow_ref"
  }
  attribute_condition = "assertion.repository == '${local.repository_full_name}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_deployer_wif" {
  for_each = local.production_workflow_refs

  service_account_id = google_service_account.github_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.workflow/${each.value}"
}

resource "google_service_account_iam_member" "github_plan_wif" {
  service_account_id = google_service_account.github_plan.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${local.repository_full_name}"
}
