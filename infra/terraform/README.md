# GCP infrastructure

Terraform manages private versioned data/model buckets, Artifact Registry, a scale-to-zero Cloud Run service, a monthly candidate-only Cloud Run Job and Scheduler trigger, least-privilege identities, repository-scoped GitHub OIDC, monitoring, and a `$5` monthly budget.

## State bootstrap

Create the small state bucket once, then migrate the root configuration:

```bash
terraform -chdir=bootstrap init
terraform -chdir=bootstrap apply -var='project_id=YOUR_PROJECT_ID'
terraform init -backend-config='bucket=YOUR_PROJECT_ID-reviewsignal-tfstate' -migrate-state
```

## Validate and plan

```bash
cp example.auto.tfvars local.auto.tfvars
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform plan -out=reviewsignal.tfplan
```

`container_image` must use an immutable Git SHA tag. The service reads `production/model-manifest.json`; the monthly job writes versioned data and candidates but cannot promote them. A separate manual workflow evaluates, smoke-tests with zero traffic, migrates traffic, and preserves the prior revision for rollback.
