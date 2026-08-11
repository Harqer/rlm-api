#!/usr/bin/env bash
# Deploy to Cloud Run, pulling secrets from GCP Secret Manager instead of
# baking them into the image or env — same zero-trust pattern already used
# for the Spresso/QBitcoin backend.
#
# Prereqs (one-time):
#   gcloud secrets create supabase-service-role-key --data-file=-   <<< "$SUPABASE_SERVICE_ROLE_KEY"
#   gcloud secrets create rlm-managed-anthropic-key  --data-file=-   <<< "$MANAGED_ANTHROPIC_API_KEY"   # optional, only for managed tier
#
# Usage:
#   PROJECT_ID=your-gcp-project REGION=us-west1 SUPABASE_URL=https://xxx.supabase.co ./deploy/cloudrun.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-west1}"
SUPABASE_URL="${SUPABASE_URL:?Set SUPABASE_URL}"
SERVICE_NAME="${SERVICE_NAME:-harqer-rlm-api}"

gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}" .

gcloud run deploy "${SERVICE_NAME}" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=${SUPABASE_URL}" \
  --set-secrets "SUPABASE_SERVICE_ROLE_KEY=supabase-service-role-key:latest" \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 300 \
  --memory 1Gi \
  --cpu 1

echo "Deployed. Fetch the URL with:"
echo "  gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format='value(status.url)'"
