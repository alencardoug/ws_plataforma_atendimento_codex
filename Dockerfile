# Cloud Run production build ONLY (deploy/deploy-backend.sh uses
# `gcloud run deploy --source .`, which requires a file literally named
# `Dockerfile` at the source root -- gcloud has no flag to point at a
# different path/name). Local docker-compose does NOT use this file; it
# builds app/Dockerfile directly with context ./app (see docker-compose.yml)
# and gets prompts/ via a live read-only bind mount instead of a build-time
# copy, so local prompt edits take effect without a rebuild.
#
# Cloud Run has no equivalent bind-mount mechanism for our own repo files,
# so prompts/ must be baked into the image at build time here. Keep this
# file's Python/dependency/user setup in sync with app/Dockerfile by hand --
# Docker's build-context scoping means one Dockerfile can't serve both
# call sites (app/-scoped context for local, repo-root-scoped context here
# so prompts/ is reachable) without duplication.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .
COPY prompts/ /workspace/prompts/

ENV PORT=8000
RUN useradd --create-home --uid 1000 appuser
USER appuser
CMD uvicorn main:app --host 0.0.0.0 --port "$PORT"
