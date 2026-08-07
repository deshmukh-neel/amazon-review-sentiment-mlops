# Architecture

ReviewSignal separates reproducible model creation from public inference. A scheduled Cloud Run Job reads a pinned dataset revision, validates deterministic splits, trains a candidate, and writes immutable artifacts to private Cloud Storage. Candidate models do not receive production traffic automatically.

```mermaid
flowchart LR
    Source["Pinned dataset revision"] --> Job["Cloud Run pipeline job"]
    Job --> Data["Versioned GCS data"]
    Data --> Candidate["Candidate model + metrics"]
    Candidate --> Gate{"Promotion gates pass?"}
    Gate -- no --> Reject["Retain candidate for inspection"]
    Gate -- yes --> Preview["No-traffic Cloud Run revision"]
    Preview --> Smoke{"Smoke tests pass?"}
    Smoke -- no --> Rollback["Keep current production revision"]
    Smoke -- yes --> Service["Public FastAPI service"]
    GitHub["GitHub Actions + OIDC"] --> Job
    GitHub --> Preview
```

## Runtime boundaries

- The training job can read and write data and candidate-model objects.
- The public service can only read the exact production-model bucket.
- GitHub Actions receives short-lived GCP credentials through Workload Identity Federation.
- The service loads a model pinned by `MODEL_VERSION` and verifies its SHA-256 before deserialization.
- Submitted review text exists only for the lifetime of one HTTP request and is excluded from logs.

## Cost controls

The service uses zero minimum instances and two maximum instances. The training job runs monthly and exits. Storage and container-image lifecycle policies remove old non-production artifacts while retaining active production and rollback versions.

