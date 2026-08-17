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

Cloud Run (customer-care-backend, region us-east1, min-instances=0)
  --DATABASE_URL (public internet, sslmode=require)--> Neon serverless Postgres (us-east-1, N. Virginia)
  --OPENAI_API_KEY--> OpenAI API (unchanged from local dev)
```

**Region choice (2026-08-17):** Cloud Run's Always Free tier is restricted to
exactly three regions — `us-central1`, `us-east1`, `us-west1` (deploying
elsewhere works but is billed from the first request, not covered by the
free allotment). Target audience is majority Brazil, so `us-east1` (South
Carolina) was chosen over `us-central1`/`us-west1` as the free-tier-eligible
region geographically closest to it. Neon's project region was set to N.
Virginia (`us-east-1`) — the closest of Neon's three offered US regions
(N. Virginia/Ohio/Oregon) to both Brazil and to `us-east1`, keeping the
Cloud Run↔Neon hop short too.

Neon is an independent company, not a GCP product — the connection crosses
the public internet (TLS-encrypted), not a GCP private VPC. `database.py`'s
existing `pool_pre_ping=True` already handles Neon's compute
autosuspend/resume transparently — no code change was needed for that.

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
2. `gcloud auth login`; create a dedicated GCP project (`gcloud projects
   create <PROJECT_ID>`) rather than reusing the account's auto-created
   default project; `gcloud config set project <PROJECT_ID>`; link a billing
   account (`gcloud billing projects link <PROJECT_ID>
   --billing-account=<ACCOUNT_ID>`, required even to stay within the free
   tier — see `gcloud billing accounts list`).
3. `gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   secretmanager.googleapis.com firebase.googleapis.com
   cloudresourcemanager.googleapis.com`. All five were needed in practice,
   not just the three Cloud Run/Build/Secret Manager APIs — Firebase
   provisioning (step 6) failed with an opaque `403 PERMISSION_DENIED` until
   the last two were also enabled.
4. Set a budget alert (GCP Console → Billing → Budgets & alerts) — e.g. warn
   at US$1 — as a safety net, not because charges are expected. If the
   console asks you to scope the alert to specific services, don't narrow it
   to just Cloud Run — leave it unscoped (whole project) or select all
   listed services, so it also catches Cloud Build/Secret Manager spend.
5. Create a Neon project (neon.tech). Match Postgres major version to what's
   used locally (17, not whatever default Neon offers) to remove a variable
   from the first production deploy. **Turn Neon Auth OFF** — the app has its
   own operator/customer auth, Neon's built-in auth would be unused surface
   area. Pick the Neon region closest to your actual users (not necessarily
   closest to the Cloud Run region — see the region-choice note above for
   why Cloud Run region wins that tradeoff). Then, in Neon's SQL Editor:
   `CREATE EXTENSION IF NOT EXISTS vector;`. Copy the connection string from
   "Connection Details" and add `?sslmode=require` if not already present.
6. Add Firebase to the **same** GCP project — `firebase login`, then
   `firebase projects:addfirebase <PROJECT_ID>`. **In practice this CLI
   command kept failing with `403 PERMISSION_DENIED` even as project Owner,
   with all of step 3's APIs enabled, and after a full `firebase logout` +
   `firebase login --reauth`** — cause not identified. The reliable
   workaround: go to console.firebase.google.com → "Add project" → select
   the existing GCP project from the list (do not create a new one) → finish
   the wizard (Analytics is optional, fine to skip). Once the Firebase
   project exists (`firebase projects:list` shows it), `firebase use --add`
   from the repo root works normally and generates the local (gitignored)
   `.firebaserc`.
7. Generate **fresh** production secrets — do not reuse local `.env` values:
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` (run
   twice, once for `ANONYMOUS_TOKEN_PEPPER`, once for `OPERATOR_AUTH_SECRET`;
   same command, a third time, for the operator account's password in step 2
   of Deploy below — don't reuse a memorable/guessable password since this
   account is reachable from a real public URL).
8. Export `DATABASE_URL` (with `+psycopg` after `postgresql`, matching
   SQLAlchemy's driver syntax — Neon's own connection string doesn't include
   it), `OPENAI_API_KEY`, `ANONYMOUS_TOKEN_PEPPER`, `OPERATOR_AUTH_SECRET` in
   your shell, then run `deploy/create-secrets.sh` (creates the four Secret
   Manager secrets and grants Cloud Run access).

### Deploy

1. `deploy/init-database.sh` (same four env vars exported as above) — applies
   migrations and ingests the synthetic corpus into Neon. Safe to rerun
   (idempotent, same content-hash re-embed guarantee as local ingestion).
   Note its `--corpus-root` default (`/workspace/documents`) only applies
   inside the Docker image; running this locally against a remote database
   needs `--corpus-root ../documents` (relative to `app/`) instead.
2. Seed one production operator account explicitly:
   `python -m customer_care.auth.seed_operator --email ... --password ...`
   (use one of step 7's generated secrets as the password, not something
   memorable — this account is reachable from the public URL).
3. `deploy/deploy-backend.sh` — builds `app/Dockerfile` via Cloud Build and
   deploys to Cloud Run (`--source`, no local Docker build needed). Verify
   with `curl <service-url>/health` and `curl <service-url>/ready` (the
   latter also confirms Neon connectivity) before moving on.
4. `deploy/deploy-frontend.sh` — builds the SPA and deploys to Firebase
   Hosting. Verify the `/api/**` rewrite actually reaches Cloud Run (not
   just that the static SPA loads) with e.g. `curl -X POST
   https://<project>.web.app/api/v1/public/conversations`.
5. Reset any conversations created during steps 3-4's `curl` validation
   (`TRUNCATE customer_service.audit_events, message_selections,
   message_citations, ai_generation_sources, ai_generations, retrieval_hits,
   retrieval_runs, messages, conversation_assignments, conversations
   CASCADE;` against Neon) so the operator's queue starts empty for real use.

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
