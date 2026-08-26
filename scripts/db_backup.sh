#!/usr/bin/env bash
# Backup COMPLETO do PostgreSQL local (Docker Compose) — schemas content,
# customer_service e scheduling, incluindo as colunas vector(1536) do
# pgvector, o tipo enum scheduling.slot_status, a função next_business_day(),
# o trigger append-only de auditoria e a tabela alembic_version.
#
# Um único arquivo .dump (formato custom do pg_dump) cobre "banco vetorial" e
# "banco estruturado" — no pgvector eles são a mesma base.
#
# Uso:
#   ./scripts/db_backup.sh [rotulo]
# Exemplos:
#   ./scripts/db_backup.sh pre-refino
#   ./scripts/db_backup.sh            # usa timestamp
#
# Gera:  backups/<rotulo>.dump  (+ backups/<rotulo>.env se houver .env)
set -euo pipefail

cd "$(dirname "$0")/.."

LABEL="${1:-$(date +%Y%m%d-%H%M%S)}"
OUT_DIR="backups"
OUT="${OUT_DIR}/${LABEL}.dump"
mkdir -p "$OUT_DIR"

# Credenciais: do .env se existir, senão os defaults do docker-compose.yml
PGDB="oncology"; PGUSER="oncology"; PGPASS="oncology_demo_change_me"
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
  PGDB="${POSTGRES_DB:-$PGDB}"
  PGUSER="${POSTGRES_USER:-$PGUSER}"
  PGPASS="${POSTGRES_PASSWORD:-$PGPASS}"
fi

if ! docker compose ps --status running db | grep -q db; then
  echo "ERRO: o serviço 'db' não está rodando. Rode 'docker compose up -d db' primeiro." >&2
  exit 1
fi

echo "→ pg_dump de '${PGDB}' para ${OUT} ..."
docker compose exec -T -e PGPASSWORD="$PGPASS" db \
  pg_dump -U "$PGUSER" -d "$PGDB" --format=custom --no-owner --no-privileges \
  > "$OUT"

# Guarda também o .env ao lado (fora do git) — útil se você mexer nele durante o refino
if [ -f .env ]; then cp .env "${OUT_DIR}/${LABEL}.env"; fi

SIZE=$(du -h "$OUT" | cut -f1)
echo "✓ Backup concluído: ${OUT} (${SIZE})"
echo "  Restaurar depois com:  ./scripts/db_restore.sh ${LABEL}"
