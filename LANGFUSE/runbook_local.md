# Validação local da integração 013

O SDK envia apenas observações prospectivas da aplicação local ao Langfuse
Cloud. Não é instalado um servidor Langfuse local. A flag versionada fica
`false`; nenhuma alteração permanente no `.env` é feita pelo executor.

## Pré-requisitos

Python 3.12 com `app/requirements-dev.txt`, dependências do frontend
instaladas pelo lockfile, Docker Compose com suporte a `!override`,
Chromium do Playwright e credenciais locais válidas para os smokes reais.
`LANGFUSE_BASE_URL` ou `LANGFUSE_HOST` precisa nomear a mesma região Cloud;
chaves só ficam no `.env` não versionado. Para o atendimento local, passar
as variáveis explicitamente ao processo; o Compose cotidiano não foi editado.

## Executar os gates

Na raiz, sem outro executor de testes concorrente:

```bash
.venv/bin/python scripts/run_langfuse_gates.py --stage all
```

O padrão executa flag `false` e depois `true`, serialmente. Para uma
verificação focada, usar `--stage backend|frontend|smoke|e2e` e opcionalmente
`--flag false|true`. A suíte completa continua necessária para AC-07.
`LANGFUSE/validation-report.json` guarda o último resultado, tempos,
projeto temporário e evidência Cloud selecionada; nunca credenciais ou
corpos de conversas. Falha em qualquer gate encerra a rodada como falha.

O executor:

1. Registra o estado dos serviços cotidianos e lê os switches de autonomia.
2. Copia somente os dados sintéticos de `content` por `pg_dump` read-only;
   não copia conversas, tokens nem usuários do banco cotidiano.
3. Devolve o PostgreSQL cotidiano ao estado inicial e usa um projeto
   exclusivo `customer-care-lf-validation-<PID>`, com volume próprio e
   banco `oncology_langfuse_test`. API/UI cotidianos não são substituídos.
4. Aplica as migrations existentes, restaura conteúdo vetorizado e cria
   operador de teste. As portas preferidas são 18000/15173; se ocupadas,
   escolhe portas livres locais e as propaga ao Playwright.
5. Valida o banco real e host antes de resets. Restaura fixtures entre
   smokes; nos módulos pytest de 012, prepara agenda após o cleanup de
   AA-9. Não altera os assertions nem as regras do agendamento.
6. Executa os gates. Pytest usa `deterministic-test` (telemetria 0%); os
   testes do contrato usam doubles ou SDK com exporter em memória. Os
   smokes/Playwright usam OpenAI real e telemetria conforme a flag.
7. Após o smoke N5 com flag ligada, lê os traces pela API autenticada e
   compara sessão, geração, query/evidências, mensagem e custo. Isso é
   prova técnica, não a avaliação de qualidade LF-6.
8. Remove contêineres e volume **criados por esta rodada**, inclusive em
   erro/SIGINT/SIGTERM tratável. Os dados descartáveis de teste não são
   recuperáveis; o banco cotidiano e seu volume não são removidos.

Helpers SQL do Playwright recusam execução sem
`E2E_DATABASE_NAME=oncology_langfuse_test`. Não chamar os smokes diretamente
contra o banco cotidiano — especialmente `smoke_ingestion_changed.py`.

## Interrupção abrupta

SIGKILL ou queda do host pode impedir o `finally`. Leia no relatório
`validation_project` e `initial_running_services`, confirme os alvos com
`docker compose -p <projeto-exato-do-relatório> ps -a` e encerre **somente**
esse projeto com:

```bash
docker compose -p <projeto-exato-do-relatório> -f docker-compose.yml down --volumes
```

O nome deve começar com `customer-care-lf-validation-`; nunca usar esse
comando com o projeto cotidiano. Caso o host tenha parado durante o
snapshot e `db` não estivesse inicialmente ativo, `docker compose stop db`
restaura seu estado. API/UI cotidianos não precisam de restauração porque
o executor não os recria. A pasta `.lf-validation-*` em `app/` contém só
artefatos temporários sintéticos; é excluída do contexto da imagem e deve
ser inspecionada antes de remover eventual resíduo de uma queda.

## Limites e leitura dos resultados

Observações são best-effort: batches 64/1 s, timeout HTTP 3 s, espera de
shutdown no máximo 5 s. Perda de telemetria não repete geração nem envio.
Ausência de evento terminal significa desfecho não observado. PostgreSQL
e auditoria continuam sendo a fonte de verdade do atendimento.

O próximo checkpoint é LF-5. A sessão LF-6 (20–30 conversas, humano +
Claude Code) e qualquer mudança de produto permanecem separadas.
