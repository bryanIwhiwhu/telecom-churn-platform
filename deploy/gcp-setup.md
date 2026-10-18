# One-time Google Cloud setup

About 20 minutes. Run these in **Cloud Shell** (the terminal icon in the Google Cloud console),
which already has `gcloud` installed and signed in.

Replace the three values in the first block, then paste the rest block by block.

## 0. Protect yourself from surprise bills first

In the console: **Billing → Budgets & alerts → Create budget**, set **$5**, alerts at 50% and 100%.
The deploy workflow caps the service at one instance and scales to zero when idle,
so normal demo traffic stays inside the free tier. Artifact Registry storage beyond
0.5 GB costs a few cents a month; delete old images when you're done.

## 1. Variables

```bash
export PROJECT_ID="bryan-churn-demo"        # must be globally unique
export GITHUB_REPO="YOUR_GITHUB_USERNAME/bell-churn-platform"
export REGION="northamerica-northeast2"     # Toronto

gcloud projects create "$PROJECT_ID"
gcloud config set project "$PROJECT_ID"
# Link billing in the console (Billing → Link a billing account), then continue.
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
```

## 2. Enable services and create the image repository

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    iamcredentials.googleapis.com sts.googleapis.com

gcloud artifacts repositories create churn \
    --repository-format=docker --location="$REGION"
```

## 3. A deploy-only service account (least privilege)

```bash
gcloud iam service-accounts create github-deployer --display-name="GitHub deployer"
SA="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role="$ROLE"
done
```

## 4. Keyless auth from GitHub (Workload Identity Federation)

No JSON key is ever created or stored. GitHub proves its identity with a short-lived token,
and only your repository is allowed to use the service account.

```bash
gcloud iam workload-identity-pools create github --location=global --display-name="GitHub"

gcloud iam workload-identity-pools providers create-oidc github-repo \
    --location=global --workload-identity-pool=github \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'"

gcloud iam service-accounts add-iam-policy-binding "$SA" \
    --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository/${GITHUB_REPO}"

echo "GCP_PROJECT_ID   = $PROJECT_ID"
echo "GCP_SA_EMAIL     = $SA"
echo "GCP_WIF_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/providers/github-repo"
```

## 5. Tell GitHub

In your repo: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**.
Add the three values printed above (they are identifiers, not secrets).

Then **Actions → Deploy to Google Cloud Run → Run workflow**. The job summary prints your live URL.

## Optional: turn on the analytics agent in the cloud

```bash
gcloud services enable secretmanager.googleapis.com
printf '%s' "YOUR_ANTHROPIC_KEY" | gcloud secrets create anthropic-key --data-file=-
gcloud secrets add-iam-policy-binding anthropic-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
```

Then add `--set-secrets ANTHROPIC_API_KEY=anthropic-key:latest` to the `gcloud run deploy`
command in `.github/workflows/deploy-gcp.yml`. If the service is public, anyone can spend
your API credits, so either keep `--max-instances 1` and a low provider spending limit,
or remove `--allow-unauthenticated` while the agent is on.

## Known limitation (good interview talking point)

Cloud Run containers are stateless: the bundled SQLite warehouse and the prediction log reset
whenever an instance restarts. The production fix is to point `DATABASE_URL` at Cloud SQL for
PostgreSQL (the code already supports Postgres, and CI tests it), or to land the warehouse in BigQuery.
