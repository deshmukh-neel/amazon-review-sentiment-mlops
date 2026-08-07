variable "project_id" {
  description = "Google Cloud project that hosts ReviewSignal."
  type        = string
}

variable "region" {
  description = "Regional location for serverless and storage resources."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment label used on managed resources."
  type        = string
  default     = "prod"
}

variable "container_image" {
  description = "Immutable Artifact Registry image URI, including a Git SHA tag."
  type        = string

  validation {
    condition     = !endswith(var.container_image, ":latest")
    error_message = "container_image must be immutable and may not use the latest tag."
  }
}

variable "deployment_git_sha" {
  description = "Full Git SHA represented by the deployed training image."
  type        = string

  validation {
    condition     = length(var.deployment_git_sha) >= 7
    error_message = "deployment_git_sha must contain at least seven characters."
  }
}

variable "production_model_manifest_uri" {
  description = "Optional pinned production model manifest. Defaults to the model bucket production pointer."
  type        = string
  default     = null
  nullable    = true
}

variable "github_owner" {
  description = "Exact GitHub repository owner allowed by Workload Identity Federation."
  type        = string
  default     = "deshmukh-neel"
}

variable "github_repository" {
  description = "Exact GitHub repository name allowed by Workload Identity Federation."
  type        = string
  default     = "amazon-review-sentiment-mlops"
}

variable "billing_account_id" {
  description = "Billing account ID for the monthly budget; null skips budget creation during bootstrap."
  type        = string
  default     = null
  nullable    = true
}

variable "monthly_budget_usd" {
  description = "Portfolio cost guardrail in US dollars."
  type        = number
  default     = 46
}

variable "notification_channel_names" {
  description = "Existing Cloud Monitoring notification channel resource names."
  type        = list(string)
  default     = []
}

variable "monthly_training_schedule" {
  description = "UTC cron schedule for candidate-only ingestion and training."
  type        = string
  default     = "0 10 1 * *"
}
