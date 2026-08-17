#!/usr/bin/env bash
# Deploys the backend to Cloud Run from source (Cloud Build builds the
# repo-root Dockerfile remotely -- no local docker build/push needed). Run
# from the repo root. Source is the repo root, not ./app, so the build can
# also COPY prompts/ into the image (Cloud Run has no bind-mount equivalent
# to how local docker-compose serves prompts/ to app/Dockerfile) -- see the
# comment at the top of the repo-root Dockerfile for the full reasoning.
#
# Prerequisites (one-time, see DEPLOYMENT.md "Production deployment" section):
#   - gcloud auth login && gcloud config set project <PROJECT_ID>
#   - Cloud Run + Cloud Build APIs enabled on the project
#   - Secret Manager secrets already created: database-url, openai-api-key,
#     anonymous-token-pepper, operator-auth-secret (see create-secrets.sh)
#
# Service name/region here MUST match firebase.json's hosting.rewrites run.serviceId/region.
set -euo pipefail

SERVICE_NAME="customer-care-backend"
REGION="us-east1"

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --set-secrets="DATABASE_URL=database-url:latest,OPENAI_API_KEY=openai-api-key:latest,ANONYMOUS_TOKEN_PEPPER=anonymous-token-pepper:latest,OPERATOR_AUTH_SECRET=operator-auth-secret:latest" \
  --set-env-vars="GLOBAL_MATURITY_MODE=N2,N1_ASSISTIVE_SEARCH_ENABLED=true,OPERATOR_MAX_ACTIVE_CONVERSATIONS=4,OPERATOR_AUTH_TTL_MINUTES=480,ANONYMOUS_TOKEN_RATE_LIMIT_MAX_FAILURES=30,ANONYMOUS_TOKEN_RATE_LIMIT_WINDOW_SECONDS=60,ANONYMOUS_TOKEN_RATE_LIMIT_BASE_LOCKOUT_SECONDS=60,ANONYMOUS_TOKEN_RATE_LIMIT_MAX_LOCKOUT_SECONDS=900,AI_PROVIDER=openai,AI_GENERATION_MODEL=gpt-5-mini,AI_EMBEDDING_MODEL=text-embedding-3-small,AI_EMBEDDING_DIMENSION=1536,API_ROOT_PATH=/api/v1,LOG_LEVEL=INFO"

echo
echo "Deployed. Cloud Run URL (for direct testing, bypassing Firebase Hosting):"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)"
