#!/usr/bin/env bash
# Restaura o PostgreSQL local para um backup feito por db_backup.sh.
# DESTRUTIVO: recria a base do zero e substitui TODO o conteúdo atual
# (conversas, gerações, auditoria, conhecimento, agenda, embeddings).
#
# Uso:
#   ./scripts/db_restore.sh <rotulo | caminho/para/arquivo.dump>
# Exemplos:
#   ./scripts/db_restore.sh pre-refino
#   ./scripts/db_restore.sh backups/20260826-011500.dump
set -euo pipefail

cd "$(dirname "$0")/.."

ARG="${1:?informe o rótulo ou o caminho do .dump}"
if [ -f "$ARG" ]; then DUMP="$ARG"; else DUMP="backups/${ARG}.dump"; fi
[ -f "$DUMP" ] || { echo "ERRO: arquivo não encontrado: $DUMP" >&2; exit 1; }

PGDB="oncology"; PGUSER="oncology"; PGPASS="oncology_demo_change_me"
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
  PGDB="${POSTGRES_DB:-$PGDB}"
  PGUSER="${POSTGRES_USER:-$PGUSER}"
  PGPASS="${POSTGRES_PASSWORD:-$PGPASS}"
fi

docker compose ps --status running db | grep -q db || {
  echo "ERRO: o serviço 'db' não está rodando. Rode 'docker compose up -d db'." >&2; exit 1; }

echo "ATENÇÃO: isto vai APAGAR e recriar a base '${PGDB}' a partir de:"
echo "         ${DUMP}"
read -r -p "Digite 'restaurar' para confirmar: " CONFIRM
[ "$CONFIRM" = "restaurar" ] || { echo "Cancelado."; exit 1; }

RUN() { docker compose exec -T -e PGPASSWORD="$PGPASS" db "$@"; }

echo "→ derrubando conexões e recriando '${PGDB}' ..."
RUN psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 -c \
  "DROP DATABASE IF EXISTS \"${PGDB}\" WITH (FORCE);"
RUN psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 -c \
  "CREATE DATABASE \"${PGDB}\" OWNER \"${PGUSER}\";"

echo "→ pg_restore ..."
RUN pg_restore -U "$PGUSER" -d "$PGDB" --no-owner --no-privileges --exit-on-error < "$DUMP"

echo "✓ Restaurado. Confira a revisão do Alembic:"
RUN psql -U "$PGUSER" -d "$PGDB" -tAc "SELECT version_num FROM alembic_version;"
echo "  (Se você usa o backend em container, reinicie: docker compose restart backend)"
