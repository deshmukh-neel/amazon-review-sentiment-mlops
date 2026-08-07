resource "google_cloud_run_v2_service" "api" {
  name                = local.name_prefix
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.labels

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "30s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      env {
        name  = "MODEL_MANIFEST_URI"
        value = local.production_model_manifest_uri
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 2
        timeout_seconds       = 2
        period_seconds        = 3
        failure_threshold     = 20
        http_get {
          path = "/healthz"
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 2
        period_seconds        = 10
        failure_threshold     = 3
        http_get {
          path = "/healthz"
          port = 8080
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [traffic]
  }

  depends_on = [
    google_project_service.required,
    google_storage_bucket_iam_member.runtime_model_reader,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "monthly_candidate" {
  name                = "${local.name_prefix}-monthly-candidate"
  location            = var.region
  deletion_protection = true
  labels              = local.labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.trainer.email
      max_retries     = 1
      timeout         = "7200s"

      containers {
        image   = var.container_image
        command = ["sh", "-c"]
        args = [
          "reviewsignal pipeline --data-dir /tmp/data --model-dir /tmp/models --data-publish-prefix gs://${google_storage_bucket.data.name}/versions/$(date -u +%Y%m%dT%H%M%SZ) --model-publish-prefix gs://${google_storage_bucket.models.name}/candidates --git-sha ${var.deployment_git_sha}"
        ]

        resources {
          limits = {
            cpu    = "4"
            memory = "16Gi"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_storage_bucket_iam_member.trainer_data_writer,
    google_storage_bucket_iam_member.trainer_model_writer,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_job.monthly_candidate.location
  name     = google_cloud_run_v2_job.monthly_candidate.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "monthly_candidate" {
  name             = "${local.name_prefix}-monthly-candidate"
  description      = "Creates a validated candidate only; promotion remains manual"
  schedule         = var.monthly_training_schedule
  time_zone        = "Etc/UTC"
  region           = var.region
  attempt_deadline = "180s"

  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.monthly_candidate.name}:run"
    body        = base64encode("{}")

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [
    google_project_service.required,
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
  ]
}
