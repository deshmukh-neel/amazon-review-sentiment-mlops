# Deployment, promotion, and rollback

The Terraform and GitHub workflows are ready, but no cloud resources are created by a validation or plan. Enabling billing and applying Terraform are explicit operator actions.

## 1. Bootstrap remote state

Authenticate with Google Cloud, select the intended project, and confirm its billing account before continuing.

```bash
terraform -chdir=infra/terraform/bootstrap init
terraform -chdir=infra/terraform/bootstrap apply \
  -var='project_id=YOUR_PROJECT_ID'
```

Then initialize the root module with the bucket Terraform reports:

```bash
terraform -chdir=infra/terraform init \
  -backend-config='bucket=YOUR_PROJECT_ID-reviewsignal-tfstate' \
  -migrate-state
```

## 2. Plan and apply infrastructure

Copy `infra/terraform/example.auto.tfvars` to a local, ignored `.auto.tfvars` file and set the project, immutable image, Git SHA, exact GitHub owner/repository, production manifest URI, and optional billing/notification values.

```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
```

Terraform provisions the private buckets, Artifact Registry, service/job, Scheduler trigger, service accounts/IAM, GitHub Workload Identity Federation, alert policies, and optional budget. Code deploy, model promotion, and Terraform plan have separate identities bound to their exact workflow paths. The plan identity has service-specific read roles; the promoter alone can create immutable production versions and compare-and-swap the pointer. No long-lived service-account key is created.

## 3. Configure GitHub

Create a protected `production` environment and set repository/environment variables from Terraform outputs:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`
- `GCP_PLAN_SERVICE_ACCOUNT`
- `GCP_PROMOTER_SERVICE_ACCOUNT`
- `GCP_ARTIFACT_REPOSITORY`
- `CLOUD_RUN_SERVICE`
- `GCP_RUNTIME_SERVICE_ACCOUNT`
- `PRODUCTION_MODEL_MANIFEST_URI`

Pull requests run lint, tests/coverage, synthetic training, a production-container smoke test, and Terraform validation. Same-repository pull requests can also receive a read-only Terraform plan through OIDC. Forked pull requests never receive cloud credentials.

## 4. Deploy application code

After CI succeeds on `main`, the deploy workflow builds and pushes an image tagged with the immutable full Git SHA. It resolves the production pointer to a versioned manifest, deploys with no traffic, probes the tagged revision, shifts traffic, and repeats readiness, model-identity, and positive/negative checks. A failed post-shift check restores the exact previous traffic allocation.

The first code deployment intentionally waits for an initial model promotion because there is no production pointer to resolve yet. Create a candidate by running the monthly job manually (or publishing from the CLI), then run the promotion workflow with the explicit initial-promotion confirmation.

## 5. Promote a candidate

Run the protected **Promote model** workflow with an immutable `gs://.../candidates/<version>/model-manifest.json` input. The workflow:

1. Requires the manifest to be under this project's exact immutable candidate prefix and pins its object generations.
2. Verifies Git/model/dataset lineage and the artifact SHA-256 inside a read-only, credential-free, network-disabled container.
3. Applies the initial/baseline/current-production metric gates and fails closed when the current pointer is unavailable.
4. Creates or verifies an immutable `production/versions/<model-version>/` artifact/manifest pair with create-only preconditions.
5. Deploys a tagged Cloud Run revision pinned to that immutable manifest with no traffic, then probes readiness, OpenAPI, model identity, and positive/negative requests.
6. Moves traffic to the candidate and repeats model-identity and prediction probes.
7. Updates the production pointer with a generation compare-and-swap only after public checks pass.

A rejected candidate cannot update the production pointer or receive production traffic. Initial promotion requires an explicit protected-workflow confirmation and is refused if a different production version already exists. If a transient failure leaves matching immutable objects behind, a retry generation-pins and verifies their checksum and canonical manifest before reusing them.

## Rollback

If a final post-shift check or pointer compare-and-swap fails, the workflow restores the exact prior revision allocation captured from Cloud Run traffic state. Every revision keeps an immutable manifest URI, so rollback cannot cold-start against a newer model. For an operator-initiated rollback:

```bash
gcloud run revisions list \
  --service reviewsignal \
  --region us-central1

gcloud run services update-traffic reviewsignal \
  --region us-central1 \
  --to-revisions PREVIOUS_REVISION=100
```

Because buckets are versioned, restore the prior production manifest generation before the next code deployment if the model pointer also needs to be rolled back. Confirm `/readyz`, `/api/v1/model`, and two prediction probes after any rollback.

## Post-deployment acceptance

- Public page, `/docs`, `/healthz`, `/readyz`, and `/api/v1/model` respond successfully.
- Positive and negative prediction probes return valid contracts and request IDs.
- The model version matches the promoted manifest.
- A deliberately bad candidate fails before the production pointer or traffic changes.
- Failed scheduled jobs, sustained 5xx rates, and abnormal latency trigger the configured alerts.
- Billing reports and the $5 budget notification are visible.
