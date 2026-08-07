data "google_project" "current" {
  project_id = var.project_id
}

locals {
  name_prefix = "reviewsignal"
  labels = {
    application = "reviewsignal"
    environment = var.environment
    managed_by  = "terraform"
  }
  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "sts.googleapis.com",
  ])
  production_model_manifest_uri = coalesce(
    var.production_model_manifest_uri,
    "gs://${google_storage_bucket.models.name}/production/model-manifest.json"
  )
  repository_full_name = "${var.github_owner}/${var.github_repository}"
  production_workflow_refs = toset([
    "${var.github_owner}/${var.github_repository}/.github/workflows/deploy.yml@refs/heads/main",
    "${var.github_owner}/${var.github_repository}/.github/workflows/promote-model.yml@refs/heads/main",
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "data" {
  name                        = "${var.project_id}-${local.name_prefix}-data"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 365
      matches_prefix = ["versions/"]
      with_state     = "ANY"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "models" {
  name                        = "${var.project_id}-${local.name_prefix}-models"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 90
      matches_prefix = ["candidates/"]
      with_state     = "ANY"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = local.name_prefix
  description   = "Immutable ReviewSignal service and training images"
  format        = "DOCKER"
  labels        = local.labels

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-untagged-after-30-days"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "2592000s"
    }
  }

  cleanup_policies {
    id     = "delete-images-after-90-days"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "7776000s"
    }
  }

  cleanup_policies {
    id     = "keep-five-recent-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }

  depends_on = [google_project_service.required]
}
