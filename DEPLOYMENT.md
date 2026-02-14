# GCP Deployment Guide

This guide covers deploying the Shell Chat backend to Google Cloud Platform.

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated
- A GCP project with billing enabled
- Firebase project (same as frontend)

---

## GitHub Actions: Auto-deploy on push

**Every push to `main` triggers a redeploy.** The workflow in `.github/workflows/deploy-cloud-run.yml` builds the Docker image, pushes to Artifact Registry, and deploys to Cloud Run.

### Setup

1. **Enable GCP APIs** (if not already):
   ```bash
   gcloud services enable run.googleapis.com artifactregistry.googleapis.com
   ```

2. **Create Artifact Registry repo** (first time only):
   ```bash
   gcloud artifacts repositories create shell-chat \
     --repository-format=docker \
     --location=us-central1 \
     --description="Shell Chat images"
   ```

3. **Create service account and key:**

   - Create a service account with: `roles/run.admin`, `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser`, `roles/iam.serviceAccountTokenCreator` (on itself)
   - Download JSON key, add as GitHub **secret**: `GCP_SA_KEY`

4. **Add GitHub secrets:** `GCP_SA_KEY`, `TOGETHER_API_KEY`

5. **Add GitHub vars (optional):** `GCP_REGION` (default: us-central1), `FIREBASE_PROJECT_ID` (default: shell-chat-3b8d2)

6. **Allow public access** (one-time, if not in workflow):
   ```bash
   gcloud run services add-iam-policy-binding shell-chat-backend \
     --region=us-central1 \
     --member="allUsers" \
     --role="roles/run.invoker"
   ```

### Production environment

The workflow sets these env vars on Cloud Run:

| Variable | Source | Purpose |
|----------|--------|---------|
| `FIREBASE_PROJECT_ID` | GitHub var or default | Firebase Admin SDK project for token verification |
| `TOGETHER_API_KEY` | GitHub secret | Together AI inference |

**Firebase credentials:** For token verification, you also need the Firebase service account JSON. Mount it via Secret Manager and set `GOOGLE_APPLICATION_CREDENTIALS` to the mount path. Do this manually in the Cloud Run console or via a one-time `gcloud run deploy` with `--set-secrets`.

### Cost

- **GitHub Actions:** Free for public repos (unlimited minutes). Private repos: 2,000 min/month free (Free plan), then ~$0.008/min. A typical deploy uses ~2–4 minutes.
- **Cloud Run:** Free tier includes 2M requests/month and 360K vCPU-seconds. Beyond that, pay per use.
- **Artifact Registry:** 0.5 GB free; storage beyond that is billed.

For low-traffic apps, total cost is often $0 or a few dollars per month.

---

## Option 1: Cloud Run (Recommended)

Cloud Run is serverless, auto-scales to zero, and is the simplest way to run containers on GCP.

### 1. Build and push the image

```bash
# Set your GCP project and region
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1

# Build and push to Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:latest
```

### 2. Create Artifact Registry repo (first time only)

```bash
gcloud artifacts repositories create shell-chat \
  --repository-format=docker \
  --location=${REGION} \
  --description="Shell Chat images"
```

### 3. Store secrets in Secret Manager

```bash
# Firebase service account JSON (for auth)
gcloud secrets create firebase-credentials --data-file=firebase-service-account.json

# Together AI API key (create secret, then add version with your key)
echo -n "your-together-api-key" | gcloud secrets create together-api-key --data-file=-
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy shell-chat-backend \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "FIREBASE_PROJECT_ID=${PROJECT_ID},PORT=8000,GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase.json" \
  --set-secrets "/secrets/firebase.json=firebase-credentials:latest,TOGETHER_API_KEY=together-api-key:latest" \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 10
```

**Secrets:** `--set-secrets` accepts `KEY=VALUE` pairs. For file mounts, use `MOUNT_PATH=SECRET_NAME:VERSION`. For env vars, use `ENV_VAR=SECRET_NAME:VERSION`. The Cloud Run service account needs `roles/secretmanager.secretAccessor`.

### 5. Update frontend

Point `VITE_API_URL` to your Cloud Run URL (e.g. `https://shell-chat-backend-xxxxx-uc.a.run.app`). See the frontend repo's `DEPLOYMENT.md` for deploying the frontend.

---

## Database: SQLite vs Cloud SQL

**SQLite (default):** The app uses SQLite with `DATABASE_PATH` (default `./navigator.db`). On Cloud Run:

- **Ephemeral storage:** Data is lost when the instance scales to zero. Fine for dev/demo.
- **Persistent volume:** Cloud Run 2nd gen supports volume mounts. Use a Cloud Storage bucket or Filestore for persistence. **Caveat:** SQLite does not support concurrent writes from multiple instances—use `--min-instances=1 --max-instances=1` if you mount a volume.

**Cloud SQL (production):** For multi-instance scaling, migrate to PostgreSQL and use Cloud SQL. Update `database.py` to use a PostgreSQL connection string and install `psycopg2` or `asyncpg`.

---

## Option 2: Cloud Run + Cloud Build (CI/CD)

Use Cloud Build to build and deploy on push:

```yaml
# cloudbuild.yaml (in backend root)
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:$SHORT_SHA', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:$SHORT_SHA']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - run
      - deploy
      - shell-chat-backend
      - --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/shell-chat/shell-chat-backend:$SHORT_SHA
      - --region=${REGION}
```

Trigger from a repo: `gcloud builds submit --config=cloudbuild.yaml`

---

## Option 3: GKE (Kubernetes)

For more control, multi-service setups, or custom networking:

1. Create a GKE cluster.
2. Build and push the image to Artifact Registry (same as Cloud Run).
3. Deploy with a Deployment + Service. Use a PersistentVolumeClaim for SQLite, or Cloud SQL Proxy sidecar for PostgreSQL.
4. Expose via LoadBalancer or Ingress.

---

## Local Docker run

```bash
docker build -t shell-backend .
docker run -p 8000:8000 \
  -e FIREBASE_PROJECT_ID=your-project \
  -e TOGETHER_API_KEY=your-key \
  -v $(pwd)/firebase-service-account.json:/secrets/firebase.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase.json \
  shell-backend
```
