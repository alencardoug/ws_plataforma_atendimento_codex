FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Cloud Run injects PORT (defaults to 8080 there); local docker-compose sets
# it explicitly to 8000 to match the existing published port mapping. Shell
# form is required for $PORT expansion (exec-form CMD arrays don't expand).
ENV PORT=8000
RUN useradd --create-home --uid 1000 appuser
USER appuser
CMD uvicorn main:app --host 0.0.0.0 --port "$PORT"
