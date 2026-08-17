# Deployment

## V1 acceptance deployment

Local Docker Compose only.

Required services:

- `db`: PostgreSQL 17 + pgvector;
- `backend`: FastAPI;
- `frontend`: built/served SPA or dev server for local demo.

Optional operational command/profile:

- `ingest`: one-shot knowledge ingestion.

## Explicitly not required for V1

- GCP;
- Kubernetes;
- managed PostgreSQL;
- load balancer;
- production TLS termination;
- autoscaling;
- high availability.

The architecture should not preclude a later GCP VM/container deployment, but no cloud abstraction work should be added solely for hypothetical deployment.

## Production deployment (Cloud Run + Firebase Hosting + Neon)

Decided 2026-08-17 (see `DECISIONS.md` D-029). **Data remains synthetic/demo
only** — this is infrastructure only, not a change to Constitution Article VI
("V1 uses synthetic/demo data only"). Deploying real patient/customer data
requires a constitution amendment and the dedicated privacy/security/legal
review `SECURITY.md` already requires; that is a separate, larger decision,
not part of this runbook.

### Architecture

```
Browser --HTTPS--> Firebase Hosting (*.web.app, free managed TLS)
                      |-- static files: frontend/dist (built SPA)
                      '-- rewrite /api/** --> Cloud Run service (same-origin
                          from the browser's perspective; no CORS needed,
                          same shape as today's nginx same-origin proxy)

Cloud Run (customer-care-backend, region us-central1, min-instances=0)
  --DATABASE_URL (public internet, sslmode=require)--> Neon serverless Postgres
  --OPENAI_API_KEY--> OpenAI API (unchanged from local dev)
```

Neon is an independent company, not a GCP product — the connection crosses
the public internet (TLS-encrypted), not a GCP private VPC. Expect a small
added query latency versus same-cloud Cloud SQL; not expected to be
noticeable at demo/pilot traffic levels. `database.py`'s existing
`pool_pre_ping=True` already handles Neon's compute autosuspend/resume
transparently — no code change was needed for that.

Supabase is intentionally not used: its free tier fully pauses the project
after a period of inactivity (manual unpause required), which is incompatible
with a `min-instances=0` backend that itself scales to zero.

### Cost expectations

Expected to stay within free tiers for demo/pilot-level traffic:

- **Cloud Run**: requires a GCP billing account on file even to use its free
  tier (no way around this), but should not be charged if usage stays within
  the free monthly request/compute allotment. A budget alert is set up
  during provisioning as a safety net.
- **Neon**: free plan, no card required historically — verify current limits
  on neon.tech before relying on this, terms change.
- **Firebase Hosting (Spark/free plan)**: no card required.
- **OpenAI API**: not new — already billed today for local dev/testing;
  production traffic volume may increase this, independent of the
  infrastructure choice above.

### One-time provisioning (requires your own login/credentials — cannot be done unattended)

1. Install CLIs if not already present: `npm install -g firebase-tools`;
   GCP's standalone `gcloud` installer (no root needed) from
   `cloud.google.com/sdk/docs/install`.
2. `gcloud auth login`; create or select a GCP project; `gcloud config set
   project <PROJECT_ID>`; enable billing on it (required even for the free
   tier).
3. `gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   secretmanager.googleapis.com`.
4. Set a budget alert (GCP Console → Billing → Budgets & alerts) — e.g. warn
   at US$1 — as a safety net, not because charges are expected.
5. Create a Neon project (neon.tech), a `oncology` database, and copy its
   connection string (append `?sslmode=require` if not already present).
6. `firebase login`; `firebase use --add` from the repo root to generate a
   local (gitignored) `.firebaserc` pointing at the same GCP project (Firebase
   Hosting and Cloud Run can share one GCP project).
7. Generate **fresh** production secrets — do not reuse local `.env` values:
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` (run
   twice, once for `ANONYMOUS_TOKEN_PEPPER`, once for `OPERATOR_AUTH_SECRET`).
8. Export `DATABASE_URL`, `OPENAI_API_KEY`, `ANONYMOUS_TOKEN_PEPPER`,
   `OPERATOR_AUTH_SECRET` in your shell, then run `deploy/create-secrets.sh`
   (creates the four Secret Manager secrets and grants Cloud Run access).

### Deploy

1. `deploy/init-database.sh` (same four env vars exported as above) — applies
   migrations and ingests the synthetic corpus into Neon. Safe to rerun
   (idempotent, same content-hash re-embed guarantee as local ingestion).
2. Seed one production operator account explicitly (printed by step 1):
   `python -m customer_care.auth.seed_operator --email ... --password ...`.
3. `deploy/deploy-backend.sh` — builds `app/Dockerfile` via Cloud Build and
   deploys to Cloud Run (`--source`, no local Docker build needed).
4. `deploy/deploy-frontend.sh` — builds the SPA and deploys to Firebase
   Hosting.

`deploy/deploy-backend.sh`'s `SERVICE_NAME`/`REGION` must stay in sync with
`firebase.json`'s `hosting.rewrites[].run.serviceId`/`region` — they're
independent files today (Cloud Run has no native awareness of the Firebase
rewrite), so a rename requires updating both.

### Post-deploy validation

- Open the `*.web.app` URL; confirm HTTPS is automatic (no manual cert step).
- Run through `teste_humano.md` §2 against the production URL instead of
  localhost.
- Expect a multi-second cold start on the first request after any idle
  period (`min-instances=0`); this is an accepted tradeoff for staying in the
  free tier, not a bug.
- Confirm `sessionStorage` tokens/audit events behave identically to local —
  nothing about the anonymous-token or audit mechanism changes with the
  deployment target.

### Known limitation carried over, not fixed by this deployment

The anonymous-token rate limiter (`anonymous_access/rate_limit.py`) is an
in-memory, per-process dict. On Cloud Run this state does not survive an
instance restart/scale-to-zero cycle, and would not be shared across
concurrent instances if traffic ever required `--max-instances` above 1. At
demo/pilot traffic this is not expected to matter (Constitution Article VIII:
don't add infrastructure ahead of a measured need) — noted here so it isn't
mistaken for an oversight later if traffic grows.
