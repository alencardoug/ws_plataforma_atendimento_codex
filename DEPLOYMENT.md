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
