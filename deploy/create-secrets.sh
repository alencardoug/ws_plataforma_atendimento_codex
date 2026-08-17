#!/usr/bin/env bash
# One-time setup: creates the four production secrets in Secret Manager and
# grants the Cloud Run default compute service account read access to them.
# Run this once per project, before the first deploy-backend.sh run.
#
# Required environment variables before running this script (export them in
# your shell first, do not hardcode secrets into this file or commit them):
#   DATABASE_URL              - Neon connection string, sslmode=require,
#                                e.g. postgresql+psycopg://user:pass@ep-xxx.neon.tech/oncology?sslmode=require
#   OPENAI_API_KEY             - real OpenAI key (same one used locally is fine to reuse)
#   ANONYMOUS_TOKEN_PEPPER      - generate fresh, do NOT reuse the local .env value:
#                                 python3 -c "import secrets; print(secrets.token_urlsafe(32))"
#   OPERATOR_AUTH_SECRET        - generate fresh the same way, a different value
set -euo pipefail

for var in DATABASE_URL OPENAI_API_KEY ANONYMOUS_TOKEN_PEPPER OPERATOR_AUTH_SECRET; do
  if [ -z "${!var:-}" ]; then
    echo "Missing required env var: $var" >&2
    exit 1
  fi
done

gcloud services enable secretmanager.googleapis.com

create_or_update_secret() {
  local name="$1" value="$2"
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=-
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic
  fi
}

create_or_update_secret database-url "$DATABASE_URL"
create_or_update_secret openai-api-key "$OPENAI_API_KEY"
create_or_update_secret anonymous-token-pepper "$ANONYMOUS_TOKEN_PEPPER"
create_or_update_secret operator-auth-secret "$OPERATOR_AUTH_SECRET"

PROJECT_NUMBER=$(gcloud projects describe "$(gcloud config get-value project)" --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for secret in database-url openai-api-key anonymous-token-pepper operator-auth-secret; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

echo "Secrets created/updated and access granted to ${COMPUTE_SA}."
