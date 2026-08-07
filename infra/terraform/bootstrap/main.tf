variable "project_id" {
  type        = string
  description = "Google Cloud project that owns Terraform state."
}

variable "region" {
  type        = string
  description = "State bucket location."
  default     = "us-central1"
}

resource "google_storage_bucket" "terraform_state" {
  name                        = "${var.project_id}-reviewsignal-tfstate"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 10
      with_state         = "ARCHIVED"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "bucket_name" {
  value = google_storage_bucket.terraform_state.name
}
