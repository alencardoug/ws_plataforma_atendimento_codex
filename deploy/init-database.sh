#!/usr/bin/env bash
# One-time (idempotent-safe to re-run) production database setup against
# Neon: applies migrations and ingests the synthetic knowledge corpus. Runs
# locally against the Neon connection string — this does NOT run inside
# Cloud Run, and does not touch your local docker-compose database (it only
# touches whatever DATABASE_URL points at).
#
# Required env vars: DATABASE_URL (Neon, sslmode=require), OPENAI_API_KEY
# (real embeddings are used for ingestion).
set -euo pipefail

for var in DATABASE_URL OPENAI_API_KEY ANONYMOUS_TOKEN_PEPPER OPERATOR_AUTH_SECRET; do
  if [ -z "${!var:-}" ]; then
    echo "Missing required env var: $var" >&2
    exit 1
  fi
done

cd "$(dirname "$0")/../app"
# shellcheck disable=SC1091
source .venv312/bin/activate 2>/dev/null || { echo "Create app/.venv312 first (see DEVELOPMENT.md), then rerun."; exit 1; }

alembic upgrade head
python -m customer_care.knowledge.ingest

echo
echo "Migrations applied and corpus ingested against the target in DATABASE_URL."
echo "Next: seed a production operator account explicitly (not automatic, per OPERATIONS.md):"
echo "  python -m customer_care.auth.seed_operator --email you@example.com --password 'choose-a-strong-password'"
