resource "google_monitoring_alert_policy" "failed_training_job" {
  display_name          = "ReviewSignal scheduled training failure"
  combiner              = "OR"
  notification_channels = var.notification_channel_names

  documentation {
    content   = "The monthly candidate job reported a failed execution. Inspect Cloud Run Job logs before retrying."
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "Failed Cloud Run Job execution"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_job\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.label.result=\"failed\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  user_labels = local.labels
  depends_on  = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "sustained_5xx" {
  display_name          = "ReviewSignal sustained 5xx responses"
  combiner              = "OR"
  notification_channels = var.notification_channel_names

  documentation {
    content   = "ReviewSignal returned more than one 5xx response per minute for five minutes. Consider rolling back the active Cloud Run revision."
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "5xx response rate"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${local.name_prefix}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.label.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  user_labels = local.labels
  depends_on  = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "latency" {
  display_name          = "ReviewSignal abnormal p95 latency"
  combiner              = "OR"
  notification_channels = var.notification_channel_names

  documentation {
    content   = "ReviewSignal p95 request latency exceeded two seconds for five minutes."
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "p95 request latency"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${local.name_prefix}\" AND metric.type=\"run.googleapis.com/request_latencies\""
      comparison      = "COMPARISON_GT"
      threshold_value = 2000
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }

  user_labels = local.labels
  depends_on  = [google_project_service.required]
}

resource "google_billing_budget" "portfolio" {
  count = var.billing_account_id == null ? 0 : 1

  billing_account = var.billing_account_id
  display_name    = "ReviewSignal monthly portfolio budget"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  depends_on = [google_project_service.required]
}
