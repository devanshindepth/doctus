#!/usr/bin/env bash
# Deploy Doctus Studio (FastAPI + React SPA) to Google Cloud Run.
# Usage:
#   export GOOGLE_CLOUD_PROJECT="your-project-id"
#   ./deploy/deploy_cloud_run.sh
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-doctus-studio}"
AR_REPO="${AR_REPO:-doctus}"
IMAGE_TAG="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${AR_REPO}/${SERVICE_NAME}:latest"

echo "=========================================================="
echo "  Deploying Doctus Studio to Google Cloud Run"
echo "  Project:  ${GOOGLE_CLOUD_PROJECT}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${IMAGE_TAG}"
echo "=========================================================="

# 1. Ensure required Google Cloud APIs are enabled
echo "--> Enabling Google Cloud APIs (Cloud Run, Artifact Registry, Cloud Build)..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com --project="${GOOGLE_CLOUD_PROJECT}"

# 2. Ensure Artifact Registry repository exists
echo "--> Checking Artifact Registry repository '${AR_REPO}'..."
if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" --project="${GOOGLE_CLOUD_PROJECT}" >/dev/null 2>&1; then
  echo "--> Creating Artifact Registry repository '${AR_REPO}'..."
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Docker repository for Doctus Studio" \
    --project="${GOOGLE_CLOUD_PROJECT}"
fi

# 3. Submit build to Cloud Build (builds Docker multi-stage container)
echo "--> Submitting build to Cloud Build..."
gcloud builds submit \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --substitutions="_AR_REGION=${REGION},_AR_REPO=${AR_REPO},_DEPLOY_REGION=${REGION}" \
  --config=deploy/cloudrun/cloudbuild.yaml \
  .

# 4. Fetch the deployed service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform=managed --region="${REGION}" --project="${GOOGLE_CLOUD_PROJECT}" --format='value(status.url)')

echo "=========================================================="
echo "  🎉 Doctus Studio Successfully Deployed to Google Cloud!"
echo "  URL: ${SERVICE_URL}"
echo "=========================================================="
