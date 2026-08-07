# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected credential exposure or exploitable vulnerability. Use GitHub's private vulnerability-reporting feature for this repository when it is available.

Include the affected component, reproduction steps, impact, and any suggested mitigation. Do not include real review text, credentials, access tokens, or private cloud identifiers.

## Supported version

Until the first tagged production release, only the latest commit on `main` is supported.

## Security posture

- GitHub Actions uses repository-scoped Workload Identity Federation, not long-lived GCP keys.
- Model artifacts are pinned by SHA-256 and verified before deserialization.
- GCS data/model buckets prevent public access and use separate least-privilege identities.
- Submitted prediction text is neither persisted nor logged.
- CI runs dependency updates, CodeQL, and secret scanning.
