#!/usr/bin/env bash
# Deploy the Doctus ADK agent to Vertex AI Agent Engine (P4).
# Usage: GOOGLE_CLOUD_PROJECT=my-proj deploy/deploy.sh
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
STAGING_BUCKET="${STAGING_BUCKET:-gs://${GOOGLE_CLOUD_PROJECT}-doctus-staging}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)/adk_app"

echo "project : $GOOGLE_CLOUD_PROJECT"
echo "region  : $GOOGLE_CLOUD_LOCATION"
echo "bucket  : $STAGING_BUCKET"

# Fail fast if credentials are missing instead of a half-deployed LRO.
gcloud auth application-default print-access-token >/dev/null

adk deploy agent_engine \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_LOCATION" \
  --staging_bucket="$STAGING_BUCKET" \
  --requirements_file="$(dirname "$0")/requirements.txt" \
  "$APP_DIR"
