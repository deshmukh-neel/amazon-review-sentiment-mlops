# Cost model

ReviewSignal targets **less than $5/month** for normal portfolio traffic in `us-central1`. This is an estimate, not a billing guarantee; pricing and account-level free-tier consumption can change.

## Assumed monthly use

- Fewer than 10,000 demo/API requests, usually completing in under one second.
- Cloud Run service configured for request-based billing, 1 vCPU, 1 GiB RAM, zero minimum instances, two maximum instances, and concurrency 40.
- One candidate-training job using 4 vCPU and 16 GiB RAM, with a two-hour hard timeout; a typical run is expected to finish far sooner.
- Roughly 3.5 GiB of retained data/model objects after lifecycle policies.
- Up to five recent container images; current local image size is about 592 MB before registry compression and cleanup.
- One Cloud Scheduler job and modest North American network egress.

## Estimated steady-state range

| Component | Expected monthly range | Cost control |
| --- | ---: | --- |
| Cloud Run service | $0.00–$1.00 | Scale to zero, request billing, max 2 |
| Monthly Cloud Run Job | $0.00–$2.00 | One task/month, hard timeout, candidate only |
| Cloud Storage | $0.00–$0.50 | 5 GB-month free allowance where eligible; lifecycle rules |
| Artifact Registry | $0.00–$0.50 | 0.5 GiB free allowance; keep-five/untagged cleanup |
| Cloud Scheduler | $0.00–$0.10 | One job; first three jobs/account are currently free |
| Logging/Monitoring/network | $0.00–$0.90 | Privacy-safe compact logs, low traffic, regional resources |
| **Expected total** | **$0.00–$5.00** | Terraform budget alert: $46 |

Current Google Cloud pricing pages document Cloud Run pay-per-use/free-tier behavior, 5 GB-months of eligible regional Standard Cloud Storage, 0.5 GiB of Artifact Registry storage, and three Scheduler jobs per billing account before charges. See the official [Cloud Run](https://cloud.google.com/run/pricing), [Cloud Storage](https://cloud.google.com/storage/pricing), [Artifact Registry](https://cloud.google.com/artifact-registry/pricing), and [Cloud Scheduler](https://cloud.google.com/scheduler/pricing) pricing pages.

## Guardrails

- A Terraform-managed $46 budget can notify configured channels; this is a broad safety alert, not the expected monthly spend or an automatic cap.
- Buckets are private and versioned. Candidate objects expire after 90 days and versioned data after 365 days.
- Artifact Registry deletes untagged images after 30 days and any images after 90 days while preserving at least five recent versions.
- The service has zero minimum instances and no GPU.
- The monthly job creates a candidate but cannot promote it or create always-on infrastructure.
- Billing must be enabled explicitly before Terraform is applied.

Unexpected traffic, repeated manual training, cross-region transfer, free-tier consumption by other projects, retained object versions, or pricing changes can raise the actual bill. Review Billing reports and alerts after the first deployment.
