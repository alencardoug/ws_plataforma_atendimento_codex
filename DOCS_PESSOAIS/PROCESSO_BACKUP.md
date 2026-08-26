# PROCESSO_BACKUP.md — Como voltar integralmente a esta versão (código + Postgres local)

Objetivo: **refinar o produto localmente sem medo**. Antes de qualquer refino,
fixar uma âncora do **código** (Git) e um snapshot do **banco** (PostgreSQL
local, que já inclui o "banco vetorial"). Se o refino não agradar, voltar
tudo. Só promover para produção depois de aprovado.

Conferido contra o repositório em 2026-08-26.
Scripts de apoio: `scripts/db_backup.sh`, `scripts/db_restore.sh`.

---

## 1. Resposta curta

**Sim, é totalmente recuperável — código e banco.**

- **Código, prompts, migrações, conteúdo-fonte:** o Git cobre 100%. Esta versão
  já está no GitHub (`origin/main`, commit `a786467`).
- **Postgres local:** não existe "banco vetorial" separado. Os embeddings são
  colunas `vector(1536)` dentro do **mesmo PostgreSQL**. Um único `pg_dump`
  captura tudo junto: dados estruturados **+** vetores **+** índices HNSW **+**
  o tipo enum `scheduling.slot_status` **+** a função
  `scheduling.next_business_day()` **+** o trigger *append-only* de auditoria
  **+** a tabela `alembic_version`.

O que o Git **não** cobre e por isso tem backup próprio: o **estado do banco**
(dados) e o arquivo **`.env`** (que é gitignorado).

---

## 2. Fluxo recomendado (tudo local)

### 2.1 Antes de começar o refino — criar as âncoras

```bash
# (a) CÓDIGO: fecha o baseline e marca um ponto de retorno imutável
git add -A
git commit -m "docs: baseline antes do refino do processo"
git tag baseline-pre-refino
git checkout -b refino-rag          # o refino acontece aqui; 'main' nunca é tocada

# (b) BANCO: snapshot completo do Postgres local
docker compose up -d db
./scripts/db_backup.sh pre-refino    # gera backups/pre-refino.dump (+ backups/pre-refino.env)
```

> Não precisa `git push` — o trabalho é local. `main` continua igual a
> `origin/main`, então o GitHub também é um ponto de retorno válido.

### 2.2 Durante o refino

Trabalhe à vontade na branch `refino-rag`: mudar código, prompts, migrações
Alembic, conteúdo em `documents/`, reingerir embeddings, etc.

Se for fazer uma mudança grande no meio do caminho, tire um snapshot
intermediário: `./scripts/db_backup.sh etapa-2` (cada rótulo vira um arquivo
próprio em `backups/`).

### 2.3 Se o refino NÃO agradar — voltar tudo

```bash
# CÓDIGO
git checkout main
git branch -D refino-rag             # descarta o experimento
#   (se algo já tiver ido para 'main' por engano:)
#   git reset --hard baseline-pre-refino

# BANCO
./scripts/db_restore.sh pre-refino   # recria a base e restaura (pede confirmação: digite "restaurar")
docker compose restart backend       # se o backend roda em container
```

Resultado: working tree, histórico efetivo e banco **idênticos** a esta versão.

### 2.4 Se o refino AGRADAR — promover

1. `git checkout main && git merge refino-rag` (ou abrir PR).
2. **Backup do banco de produção (Neon) antes de migrar** — Neon tem
   *branching* / *point-in-time restore*; use isso como o equivalente do
   `db_backup.sh`.
3. Aplicar em produção na ordem segura de `PROCESSO_RAG.md` §3.5
   (`alembic upgrade head` no Neon → `ingest` → redeploy se houve código/prompt
   → validar com uma geração real).

---

## 3. Os scripts

### `scripts/db_backup.sh [rótulo]`

- Roda `pg_dump --format=custom --no-owner --no-privileges` dentro do container
  `db`, gravando `backups/<rótulo>.dump`.
- Sem rótulo, usa timestamp (`backups/AAAAMMDD-HHMMSS.dump`).
- Copia também o `.env` atual para `backups/<rótulo>.env` (fora do Git).
- Lê credenciais do `.env` (ou dos defaults do `docker-compose.yml`:
  `oncology`/`oncology`).
- Falha com mensagem clara se o serviço `db` não estiver rodando.

```bash
./scripts/db_backup.sh pre-refino
./scripts/db_backup.sh                 # timestamp automático
```

### `scripts/db_restore.sh <rótulo | caminho/arquivo.dump>`

- **Destrutivo e com confirmação** (é preciso digitar `restaurar`).
- Derruba conexões (`DROP DATABASE ... WITH (FORCE)`), recria a base vazia e
  roda `pg_restore --no-owner --no-privileges --exit-on-error`.
- Ao final, imprime a revisão do Alembic restaurada
  (`SELECT version_num FROM alembic_version`).

```bash
./scripts/db_restore.sh pre-refino
./scripts/db_restore.sh backups/20260826-011500.dump
```

`backups/` está no `.gitignore` — os dumps nunca vão para o GitHub.

---

## 4. Dois níveis de backup do banco

Use o **A** (os scripts). O **B** é reforço opcional para quem quer restauração
byte-a-byte.

| | **A — `pg_dump` (recomendado)** | **B — snapshot do volume Docker** |
|---|---|---|
| O que salva | dump lógico `.dump` (formato custom), portátil | cópia byte-a-byte do diretório de dados |
| Cobre vetores + HNSW? | sim (índice é **recriado** no restore — segundos, neste corpus) | sim (índice já vem **pronto**) |
| Precisa DB parado? | **não** | **sim** (consistência) |
| Restore | `./scripts/db_restore.sh` | substituir o conteúdo do volume |
| Independe de `downgrade()` de migração? | **sim** — recria a base do zero a partir do arquivo | sim |

**Comandos do método B:**

```bash
# backup
docker compose down
docker run --rm \
  -v ws_plataforma_atendimento_codex_postgres17_data:/v \
  -v "$PWD/backups":/b \
  alpine tar czf /b/pgdata-pre-refino.tgz -C /v .
docker compose up -d

# restore
docker compose down
docker run --rm \
  -v ws_plataforma_atendimento_codex_postgres17_data:/v \
  -v "$PWD/backups":/b \
  alpine sh -c "rm -rf /v/* /v/..?* /v/.[!.]* ; tar xzf /b/pgdata-pre-refino.tgz -C /v"
docker compose up -d
```

(O nome do volume — `ws_plataforma_atendimento_codex_postgres17_data` — é o
`basename` da pasta do projeto + `_` + o nome do volume no `docker-compose.yml`.
Confirme com `docker volume ls | grep postgres17`.)

---

## 5. Por que o `pg_dump` basta (e por que não dá para "só reverter o Git")

- O dump em formato custom já emite `CREATE EXTENSION IF NOT EXISTS vector` e o
  DDL de **todos** os índices (inclusive os HNSW); o `pg_restore` reconstrói a
  base inteira a partir do arquivo.
- **As migrações Alembic deste projeto são *forward-only*** — `downgrade()`
  levanta `RuntimeError` de propósito. Então "voltar o código" **não desfaz**
  colunas/tabelas que uma migração nova criou. O `db_restore.sh` contorna isso
  porque **dropa e recria** a base a partir do snapshot — não depende de
  `downgrade()`.
- Recriar do zero (`alembic upgrade head` + `ingest` + `seed_operator`)
  reconstrói conhecimento e agenda, mas **perde** conversas, gerações e
  auditoria, e **gasta chamadas de embedding de novo**. Por isso o `pg_dump` é o
  caminho de "voltar"; o rebuild é só um último recurso.

---

## 6. Checklist rápido

**Antes do refino**
- [ ] `git commit` do baseline + `git tag baseline-pre-refino`
- [ ] `git checkout -b refino-rag`
- [ ] `docker compose up -d db`
- [ ] `./scripts/db_backup.sh pre-refino`
- [ ] (opcional) método B: `pgdata-pre-refino.tgz`

**Se reverter**
- [ ] `git checkout main` (+ `git branch -D refino-rag`)
- [ ] `./scripts/db_restore.sh pre-refino`
- [ ] `docker compose restart backend`
- [ ] conferir: app sobe, "Buscar evidências" retorna resultados reais
      (`embedding_model = text-embedding-3-small`, não `sha256-test-v1`)

**Se promover**
- [ ] merge `refino-rag` → `main`
- [ ] backup/branch do Neon **antes** de migrar produção
- [ ] seguir `PROCESSO_RAG.md` §3.5
