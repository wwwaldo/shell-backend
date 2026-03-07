# GCP Deployment Guide

Infrastructure is managed with **Terraform** (`infra/`). Code deployments are handled by **GitHub Actions** (`.github/workflows/deploy-cloud-run.yml`).

## Architecture

```
Frontend → Cloud Run → Cloud SQL (PostgreSQL)
                     ↘ Secret Manager
GitHub Actions → Artifact Registry → Cloud Run (image update)
```

- **Cloud Run** serves the API, connecting to Cloud SQL via the built-in Auth Proxy (Unix socket)
- **Cloud SQL** (PostgreSQL 15, `db-f1-micro`) provides persistent storage
- **Secret Manager** stores `TOGETHER_API_KEY` and the database password
- **Artifact Registry** hosts Docker images
- **GitHub Actions** builds and pushes images on every push to `main`

## First-Time Setup

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- A GCP project with billing enabled

### 1. Create the Terraform state bucket

```bash
gsutil mb -p shell-chat-3b8d2 gs://shell-chat-tf-state
```

### 2. Create a `terraform.tfvars` file

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and fill in your values. Set the Together API key via environment variable to avoid committing it:

```bash
export TF_VAR_together_api_key="your-together-api-key"
```

### 3. Apply Terraform

```bash
cd infra
terraform init
terraform plan    # review changes
terraform apply   # create all resources
```

This creates:
- Cloud SQL PostgreSQL instance + database + user
- Artifact Registry repository
- Cloud Run service (with Cloud SQL connection, env vars, secrets)
- Service account with appropriate IAM roles
- Secret Manager secrets

### 4. Push the first Docker image

The Cloud Run service starts with a `latest` placeholder image. Push a real image:

```bash
# From the backend root
export PROJECT_ID=shell-chat-3b8d2
export REGION=us-central1

gcloud auth configure-docker ${REGION}-docker.pkg.dev
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:latest

gcloud run services update shell-chat-backend \
  --region ${REGION} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:latest
```

### 5. Set up GitHub Actions

Add these GitHub secrets and variables:

| Type | Name | Value |
|------|------|-------|
| Secret | `GCP_SA_KEY` | Service account JSON key (needs `run.developer`, `artifactregistry.writer`) |
| Variable | `GCP_REGION` | `us-central1` (optional, this is the default) |

After this, every push to `main` auto-deploys.

### 6. Update frontend

Point `VITE_API_URL` to your Cloud Run URL (shown in `terraform output cloud_run_url`).

---

## Day-to-Day Operations

### Deploying code changes

Push to `main`. GitHub Actions builds, pushes, and updates the Cloud Run image automatically.

### Changing infrastructure

Edit files in `infra/`, then:

```bash
cd infra
terraform plan
terraform apply
```

### Viewing logs

```bash
gcloud run services logs read shell-chat-backend --region us-central1
```

### Connecting to the database

```bash
# Get connection name
terraform -chdir=infra output cloud_sql_connection_name

# Connect via Cloud SQL Auth Proxy
cloud-sql-proxy PROJECT:REGION:shell-chat-db &
psql "host=127.0.0.1 port=5432 user=navigator dbname=navigator"
```

The database password is stored in Secret Manager (`shell-chat-db-password`).

---

## Local Development

Local dev still uses SQLite -- no changes needed:

```bash
# .env (default)
DATABASE_PATH=./navigator.db
```

To test against PostgreSQL locally:

```bash
# .env
DATABASE_URL=postgresql://user:pass@localhost:5432/navigator
```

---

## Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| Cloud SQL `db-f1-micro` | ~$7-9 |
| Cloud Run (low traffic) | ~$0 (scale to zero) |
| Secret Manager | ~$0 (free tier) |
| Artifact Registry | ~$0 (negligible) |
| **Total** | **~$7-10** |
