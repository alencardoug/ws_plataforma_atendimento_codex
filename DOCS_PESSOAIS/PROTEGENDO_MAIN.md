# PROTEGENDO_MAIN.md — Fluxo seguro com `main` protegida (gestor solitário)

Passo a passo para **nunca mais commitar direto na `main` por acidente** e para
tocar todo o trabalho por **branch → Pull Request → merge**, mesmo sendo você a
única pessoa no repositório.

Cobre: (1) proteção no **VS Code** (User settings), (2) proteção no **GitHub**
via `gh` CLI, (3) o **ciclo completo** — `git add`, branch, commits, push, PR,
revisão, merge, limpeza — com o comando, o que ele faz e **por que naquele
momento**.

Repositório: `alencardoug/ws_plataforma_atendimento_codex` (público, branch
padrão `main`). `gh` 2.97 já autenticado como `alencardoug` (protocolo SSH).

Relacionados: `PROCESSO_BACKUP.md` (voltar código+banco), `PROCESSO_RAG.md`.

---

## Parte 0 — Conceito em uma frase

> **Branch** = qual snapshot está carregado nos seus arquivos. Você **nunca**
> precisa trocar de branch para editar/criar um arquivo. Trabalho novo nasce
> numa branch; a `main` só muda por **merge de PR**.

Duas camadas de proteção, complementares:

| Camada | O que impede | Onde |
|---|---|---|
| VS Code (`git.branchProtection`) | você commitar **sem querer** na `main` (avisa e oferece criar branch) | User settings, só na sua máquina |
| GitHub (branch protection) | qualquer `push` direto na `main`; força PR; bloqueia force-push e exclusão | servidor, vale para qualquer clone |

> ⚠️ **Antes de aplicar as Partes 1 e 2, leia e rode a seção 5.0** — ela
> fotografa o estado atual (VS Code, Git e GitHub) em `backups/`, para você ter
> de onde restaurar. A reversão de cada mudança está na **Parte 5**.

---

## Parte 1 — VS Code

### 1.0 Global vs. somente este projeto

O VS Code lê configuração em camadas; a mais específica vence:

| Camada | Arquivo | Vale para | Versionável? | Abrir com (Ctrl+Shift+P) |
|---|---|---|---|---|
| **User (global)** | `~/.config/Code/User/settings.json` (Linux; Insiders/VSCodium/Cursor têm caminho próprio) | **toda** pasta que você abrir | **não** — fica só na sua máquina | "Preferences: Open User Settings (JSON)" |
| **Workspace (só o projeto)** | `.vscode/settings.json` na raiz deste repositório | só quando **esta** pasta está aberta | **sim**, se você commitar — todo clone herda a regra | "Preferences: Open Workspace Settings (JSON)" |

Precedência: **Workspace > User**. Se as duas definirem `git.branchProtection`,
a do workspace vence **neste** projeto.

**Você configura UM lugar** (não os dois). A seção 1.2 é o bloco completo; ele
vai inteiro no arquivo que você escolher:

- **Global (recomendado — faça só isto)** — "não commitar direto na `main`" é um
  hábito seu, não uma regra do projeto. Todas as chaves da 1.2 são preferência
  pessoal de fluxo; nenhuma é específica deste repositório. Coloque o bloco
  inteiro na User settings (1.1) e pare aqui.
- **Só o projeto** — use **em vez** do global se quiser que a regra **viaje
  junto com o repositório** (outra máquina sua, um colaborador futuro). Aí o
  bloco inteiro vai no `.vscode/settings.json` e ele entra no git. Neste repo o
  `.vscode/` ainda não é rastreado; se você criar e commitar, ele cai na branch
  atual e vai para a `main` no próximo merge — sem efeito colateral.
- **As duas ao mesmo tempo (opcional, sem ganho real aqui):** bloco inteiro no
  global **+** um `.vscode/settings.json` contendo **apenas** a(s) chave(s) que
  você quer que sejam herdadas por quem clonar — na prática só
  `"git.branchProtection": ["main"]`. Não repita as outras no workspace. Se uma
  chave estiver nos dois, a do workspace vence neste projeto (mesmo valor →
  inofensivo, só redundante).
- [x] Ler adiante e entender que em User Settings vai o código inteiro, enquanto em Workspace settings vai só uma linha.

### 1.1 Opção global — User settings (recomendado)

`Ctrl+Shift+P` → **"Preferences: Open User Settings (JSON)"** → abre
`~/.config/Code/User/settings.json`. Fora do repositório, não depende de branch,
não entra em commit, vale para todos os projetos. Adicione as chaves da 1.2.

### 1.1b Opção só este projeto — Workspace settings

`Ctrl+Shift+P` → **"Preferences: Open Workspace Settings (JSON)"** → cria/abre
`.vscode/settings.json` na raiz do repo.

- **Se você escolheu "só o projeto"** (não fez o global): cole o bloco **inteiro**
  da 1.2 aqui.
- **Se você está fazendo "as duas"** (já tem o global): coloque aqui **só**
  `"git.branchProtection": ["main"]` — o resto já está no global.

Para a regra viajar com o repo: `git add .vscode/settings.json && git commit -m
"chore: protege a main no VS Code (workspace)"` — na branch de trabalho, entra
na `main` pelo PR.

### 1.2 As chaves (iguais nas duas opções)

Mescle dentro do objeto `{ ... }` já existente (não duplique as chaves):

```jsonc
{
  // avisa e oferece criar uma branch nova se você tentar commitar na main
  "git.branchProtection": ["main"],
  "git.branchProtectionPrompt": "alwaysPrompt",

  // higiene do dia a dia
  "git.autofetch": true,          // mostra quando a main remota andou
  "git.pruneOnFetch": true,       // limpa refs de branches remotas já apagadas
  "git.confirmSync": true,        // confirma antes de push+pull juntos
  "git.postCommitCommand": "none" // não faz push automático — você decide quando
}
```

- `"git.branchProtectionPrompt"`: `"alwaysPrompt"` pergunta o que fazer;
  `"alwaysCommitToNewBranch"` já cria a branch sozinho. Escolha o seu gosto.
- Salve (`Ctrl+S`). Vale na hora, sem reiniciar.
- [x] Colar bloco de código inteiro em User settings, sem duplicar (ter dois blocos) de { … }.
- [x] Colar a linha a seguir em Workspace settings:
      `"git.branchProtection": ["main"],

### 1.3 (opcional) Config do Git — reduz atrito

Também aqui há **global** e **só este projeto**:

| Flag | Arquivo | Vale para |
|---|---|---|
| `git config --global …` | `~/.gitconfig` | todos os repositórios da sua conta |
| `git config --local …` (o padrão dentro de um repo) | `.git/config` deste repo | **só** este clone; não é versionado |

**Global (recomendado — é preferência de fluxo, não do projeto):**

```bash
git config --global push.autoSetupRemote true   # 'git push' numa branch nova já cria o upstream sozinho
git config --global pull.ff only                 # 'git pull' nunca cria merge-commit surpresa; falha se precisar rebase
git config --global fetch.prune true             # 'git fetch' remove refs de branches remotas apagadas
git config --global rebase.autoStash true        # 'git rebase' guarda/repõe mudanças não commitadas sozinho
```
- [ ] Execução dos códigos

**Só este projeto** — troque `--global` por `--local` rodando **dentro da pasta
do repo**:

```bash
git config --local push.autoSetupRemote true
git config --local pull.ff only
```

**Por quê:** com `push.autoSetupRemote` você nunca mais precisa de ```git push -u
origin <branch>``` na primeira vez; com `pull.ff only` a `main` local só avança em
linha reta (sem merge-commit acidental). Conferir de onde veio um valor:
`git config --show-origin --get pull.ff`.

---

## Parte 2 — GitHub (proteção da branch `main`)

### 2.0 Global vs. só este projeto, no GitHub

No GitHub a proteção de branch é **sempre por repositório** — não existe um
ajuste "global" para uma conta pessoal. O equivalente a "global" só existe
quando os repositórios estão dentro de uma **organização**: aí um
**organization ruleset** (`gh api orgs/<org>/rulesets`) aplica a mesma regra a
todos os repos da org de uma vez. Como
`alencardoug/ws_plataforma_atendimento_codex` é um repo de conta pessoal, a
única opção é a **por projeto**, descrita abaixo. (Se um dia mover o repo para
uma org, dá para promover esta regra a ruleset da org.)

### 2.1 A limitação do gestor solitário (leia antes)

O GitHub **não deixa você aprovar (`Approve`) a sua própria Pull Request** — o
botão fica desabilitado. Portanto a proteção **não pode exigir 1 aprovação**
(você se trancaria para fora). A configuração abaixo usa
**`required_approving_review_count: 0`**: a PR continua **obrigatória** (nada
entra na `main` sem PR), mas você mesmo pode mergear depois de revisar o diff e
o CI. Sua "aprovação" é o ato de revisar + mergear.

### 2.2 Opção A — Branch protection clássica (1 comando)

```bash
gh api -X PUT repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true
}
JSON
```

O que cada campo faz e por que está assim:

| Campo | Valor | Efeito / motivo |
|---|---|---|
| `required_pull_request_reviews` | presente | **força PR** — `git push origin main` direto passa a ser rejeitado. |
| `required_approving_review_count` | `0` | você não consegue aprovar a própria PR; 0 evita o auto-lock. |
| `dismiss_stale_reviews` | `true` | se você revisou e depois mandou mais commits, a revisão antiga é descartada. |
| `enforce_admins` | `false` | **escape hatch**: como admin, você ainda consegue destravar a `main` numa emergência (CI quebrado, etc.). Coloque `true` se quiser disciplina total. |
| `required_linear_history` | `true` | proíbe merge-commit na `main` — histórico reto (usar *squash* ou *rebase merge*). |
| `allow_force_pushes` | `false` | ninguém reescreve a história da `main`. |
| `allow_deletions` | `false` | a branch `main` não pode ser apagada. |
| `required_conversation_resolution` | `true` | toda thread de comentário na PR precisa estar resolvida antes do merge. |
| `required_status_checks` | `null` | não há CI neste repo ainda; quando houver, troque por `{"strict": true, "contexts": ["<nome do check>"]}`. |

### 2.3 Opção B — Ruleset (modelo mais novo do GitHub)

Equivalente, com a API de *rulesets* (dá para empilhar várias regras e ligar/
desligar sem apagar):

```bash
gh api -X POST repos/alencardoug/ws_plataforma_atendimento_codex/rulesets \
  --input - <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
    }},
    { "type": "non_fast_forward" },
    { "type": "deletion" },
    { "type": "required_linear_history" }
  ]
}
JSON
```

Use **A ou B**, não as duas. A é mais simples de entender; B é o caminho que o
GitHub está priorizando.
- [ ] Configurar github na opção B.

### 2.4 Ajustar as opções de merge do repositório

```bash
gh api -X PATCH repos/alencardoug/ws_plataforma_atendimento_codex \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=true \
  -F delete_branch_on_merge=true
```

**Por quê:** `allow_merge_commit=false` casa com `required_linear_history`;
`delete_branch_on_merge=true` apaga a branch automaticamente após o merge (menos
lixo).
- [ ] Ajustar repositório atual.

### 2.5 Conferir

```bash
gh api repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection --jq '{pr_required: (.required_pull_request_reviews!=null), approvals: .required_pull_request_reviews.required_approving_review_count, linear: .required_linear_history.enabled, force: .allow_force_pushes.enabled}'
# teste prático: tente empurrar direto (deve FALHAR):
#   git switch main && git commit --allow-empty -m "teste" && git push origin main   → "protected branch"
#   git reset --hard origin/main   (desfaz o commit de teste local)
```
- [ ] Testar repositório atual

### 2.6 Como afrouxar temporariamente (emergência)

```bash
# desligar a proteção (raro; só se você travar com a proteção ligada)
gh api -X DELETE repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection
# ...fazer o conserto direto na main...
# religar: rodar de novo o comando da seção 2.2
```

Com `enforce_admins: false` você raramente precisa disso — como admin, um
`gh pr merge --admin` já ignora checks pendentes.

---

## Parte 3 — O ciclo completo de um trabalho

Convenção de nome de branch: `tipo/tema-curto` — `feat/…`, `fix/…`,
`refino/…`, `docs/…`, `chore/…`.
Convenção de mensagem de commit: `tipo: resumo no imperativo` (ex.:
`refino: recalibra threshold de slot-choice`).

### Fase 1 — Começar (nasce a branch)

```bash
git switch main                 # ir para a main...
git pull --ff-only              # ...e atualizá-la (traz o que foi mergeado no GitHub)
git switch -c refino/rag-crud   # cria a branch de trabalho a partir da main atual
```
- [ ] Nascer a branch ou usar a existente (abaixo)

**Por quê agora:** a branch tem que nascer da `main` mais recente, senão você
trabalha sobre um estado velho e o merge vira conflito.

> Verificar branches. Se você já tem a branch **`refino-rag`** criada. Para seguir nela:
```bash
git branch -a # Para verificar branches existentes locais e remotas
git switch refino-rag # Para ativar uma branch
```

Para renomear, seguindo um padrão:
```bash
git branch -m refino-rag refino/rag-crud # Para renomear, no padrão
```

### Fase 2 — Trabalhar (ciclo de commits, repita à vontade)

```bash
git status                      # o que mudou / o que está preparado
git add -p                      # revisar e preparar pedaço a pedaço (ou 'git add -A' para tudo)
git commit -m "refino: <o que este commit faz>"
git push                        # envia a branch para o GitHub (backup + base da PR)
```
- [ ] status, add, commit, push

- `git add -p`: mostra cada bloco de mudança e pergunta se entra no commit —
  você revê o que está commitando.
- `git push` na primeira vez já cria o upstream (por causa do
  `push.autoSetupRemote` da Parte 1.3); sem ele seria `git push -u origin
  refino/rag-crud`.
- **Por quê comitar em pedaços pequenos:** cada commit é um ponto de retorno
  (`git revert`, `git reset`), e a PR fica legível.

**Manter a branch em dia com a `main`** (se o trabalho durar dias / a `main`
andar):

```bash
git fetch origin                                    # baixa o estado novo do remoto (não mexe nos seus arquivos)
git rebase origin/main                              # reaplica seus commits por cima da main nova → história reta
# resolva conflitos se houver: edite, 'git add <arquivo>', 'git rebase --continue'
git push --force-with-lease --force-if-includes     # a branch foi reescrita pelo rebase; publica por cima
```
- [ ] fetch, rebase, push force with lease

- `--force-with-lease` (e **não** `--force`): só sobrescreve se ninguém empurrou
  algo que você ainda não viu — protege contra apagar trabalho.
- `--force-if-includes`: fecha um furo do `--force-with-lease` quando o
  `git.autofetch` está ligado (ver abaixo).
- Rebase mantém o histórico linear que a proteção exige.

#### Entendendo — quando o `git push` é recusado

`git push` (sem forçar) é recusado com `! [rejected] … (non-fast-forward)`
quando a branch **no remoto tem commit(s) que a sua local não tem**. A recusa é
uma **pergunta**, não um "force aqui". Duas causas, respostas opostas:

| Causa | O que aconteceu | Ação correta |
|---|---|---|
| **A — você reescreveu seu histórico** | rebase / `commit --amend` / squash: mesmo trabalho, SHA novo; a versão antiga no remoto ficou obsoleta | `git push --force-with-lease --force-if-includes` — você *quer* substituir |
| **B — o remoto ganhou commit real** | você empurrou de outra máquina, web-edit no GitHub, alguém colaborou | `git pull --rebase` para integrar → `git push` normal. **Nunca force** — apagaria esse commit |

Como descobrir qual é:

```bash
git fetch
git log --oneline --left-right HEAD...@{u}
#   linhas com '<'  = commits só seus (local)
#   linhas com '>'  = commits só do remoto
```

- Os `>` são **versões antigas dos seus próprios commits** (mensagem igual, você
  acabou de rebasear)? → **Causa A** → force-with-lease.
- Os `>` são **trabalho diferente que você não tem**? → **Causa B** → integre,
  não force.

**Regra:** `git push` sempre primeiro. Recusou → não force por reflexo; olhe *o
que* o remoto tem a mais. "É minha versão antiga (rebasei)" →
`--force-with-lease --force-if-includes`. "É commit que me falta" →
`git pull --rebase` → `git push`.

**Por que `--force-if-includes` junto:** `--force-with-lease` sozinho compara "o
que vi por último no remoto" vs. "o que está lá agora". Com o `git.autofetch`
(1.2) ligado, um fetch em segundo plano pode atualizar "o que vi por último" sem
você perceber, e o `--force-with-lease` deixa passar — apagando commits reais.
`--force-if-includes` (Git ≥ 2.30) exige que os commits sobrescritos estejam no
seu histórico local. Ligue por config para não depender de lembrar:

```bash
git config --global push.useForceIfIncludes true    # todo --force-with-lease já vem com a checagem extra
```

Opcional — um atalho só para o caso "reescrevi de propósito":

```bash
git config --global alias.pushf 'push --force-with-lease --force-if-includes'
#   reescreveu histórico (rebase/amend/squash) → git pushf
#   só acrescentou commits                     → git push  (não precisa de força)
```
- [ ] (opcional) push.useForceIfIncludes / alias pushf

### Fase 3 — Abrir a Pull Request

```bash
git push                                        # garantia: manda o que faltar. No-op ("Everything up-to-date") se você já empurrou tudo na Fase 2
gh pr create --base main --fill                 # cria a PR; --fill usa os commits como título/descrição
# alternativas:
#   gh pr create --base main --title "Refino do CRUD do RAG" --body "Contexto: ..."
#   gh pr create --base main --fill --web        # abre a PR no navegador em seguida
```
- [ ] Abrir a PR

**Por quê:** a PR é o "portão" da `main`. Ela junta o diff, roda CI (quando
houver) e dá a tela de revisão.

### Fase 4 — Revisar (você, gestor solitário)

```bash
gh pr view                    # resumo: título, commits, estado, checks
gh pr diff                    # diff completo no terminal
gh pr checks                  # status do CI (aguardar verde, se houver)
gh pr view --web              # abre a aba "Files changed" no navegador para revisão visual
```
- [ ]  Revisar

- Revise a aba **"Files changed"** com calma. Marque comentários se quiser;
  resolva-os antes do merge (a proteção exige threads resolvidas).
- ⚠️ `gh pr review --approve` **vai falhar** na sua própria PR
  (*"Can not approve your own pull request"*). É esperado. Sua aprovação é:
  diff revisado + checks verdes + decisão de mergear. Se quiser deixar registro
  formal, use `gh pr comment --body "Revisado: OK para merge"`.

### Fase 5-alt — Reutilizar a mesma branch entre merges (trabalho contínuo)

Se você quer **manter uma branch de vida longa** (ex.: `refino-rag`) em vez de
criar uma nova a cada bloco: na Fase 5 use `gh pr merge --squash` **sem**
`--delete-branch`, **pule a Fase 6 abaixo** e rode este re-sync no lugar.

**Por que é obrigatório:** `--squash` cria **um commit novo** na `main`, sem
lineage com os commits da branch. A branch fica com histórico **divergente** da
`main`; se você seguir commitando nela e abrir a próxima PR, os commits antigos
reaparecem como mudança / geram conflito. O re-sync alinha a branch de novo.

```bash
gh pr merge --squash            # Fase 5, sem --delete-branch

git switch main
git pull --ff-only              # main local recebe o commit squashado
git switch refino-rag
git reset --hard origin/main    # descarta o histórico antigo da branch — já está tudo na main via squash
git push --force-with-lease     # publica a branch realinhada sobre a main nova
```
- [ ] Merge e limpeza de branch longa/duradoura

- `git reset --hard origin/main` é o passo que a Fase 6 normal não tem: zera a
  divergência criada pelo squash. Sem ele, a PR seguinte nasce quebrada.
- `--force-with-lease` na branch é seguro — a proteção é só da `main`; e o
  `-with-lease` recusa se o remoto tiver algo que você ainda não viu.
- `git branch -d refino-rag` **falharia** aqui ("not fully merged") — por isso a
  Fase 6 normal não se aplica; este bloco a substitui.

> Recomendação: para trilha única e contínua isto funciona bem, mas **branch
> curta por tarefa** (nova branch → PR → `--squash --delete-branch` → Fase 6) dá
> menos manutenção. Escolha um dos dois e seja consistente.

### Fase 5 — Merge

```bash
gh pr merge --squash --delete-branch
# se quiser sem prompt interativo: acrescente --yes
# se precisar ignorar checks pendentes (privilégio de admin, use consciente): --admin
```

- `--squash`: junta todos os commits da branch em **um** commit limpo na `main`
  — histórico do produto enxuto, e some o ruído dos commits-rascunho.
  Alternativa: `--rebase` (mantém os commits individuais, ainda linear).
  `--merge` está **bloqueado** pela `required_linear_history`.
- `--delete-branch`: apaga a branch remota (e a local, se possível).

### Fase 6 — Limpar e voltar ao ponto de partida

```bash
git switch main
git pull --ff-only              # traz o commit do merge para a main local
git branch -d refino/rag-crud   # apaga a branch local (só apaga se já mergeada; -D força)
git fetch --prune               # remove refs de branches remotas já apagadas
```

Agora `main` local == `origin/main` == produto com o refino aplicado. Pronto
para a próxima Fase 1.

### Fase 7 — Se precisar desfazer **depois** do merge

```bash
gh pr revert <número-da-PR>     # cria uma PR nova que desfaz exatamente aquela — passa pelo mesmo fluxo
# ou, localmente:
git revert -m 1 <sha-do-merge-commit>   # gera um commit que anula o merge; depois abra PR normal
```

Para voltar **tudo** (código + banco) a um marco, veja `PROCESSO_BACKUP.md`
(tag `baseline-pre-refino` + `scripts/db_restore.sh`).

---

## Parte 4 — Cola rápida

```bash
# --- setup, uma vez ---
#   VS Code: Ctrl+Shift+P → "Open User Settings (JSON)" → add "git.branchProtection": ["main"]
gh api -X PUT repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection --input - <<'JSON'
{ "required_status_checks": null, "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0, "dismiss_stale_reviews": true, "require_code_owner_reviews": false },
  "restrictions": null, "required_linear_history": true, "allow_force_pushes": false, "allow_deletions": false,
  "block_creations": false, "required_conversation_resolution": true }
JSON
gh api -X PATCH repos/alencardoug/ws_plataforma_atendimento_codex -F allow_merge_commit=false -F delete_branch_on_merge=true

# --- por trabalho (branch curta por tarefa — recomendado) ---
git switch main && git pull --ff-only
git switch -c refino/tema
# ...editar...
git add -p && git commit -m "refino: ..." && git push
gh pr create --base main --fill
gh pr diff            # revisar
gh pr merge --squash --delete-branch
git switch main && git pull --ff-only && git branch -d refino/tema && git fetch --prune

# --- por trabalho (branch de vida longa, ex.: refino-rag — ver Fase 6-alt) ---
git switch refino-rag
# ...editar...
git add -p && git commit -m "refino: ..." && git push
gh pr create --base main --fill && gh pr diff
gh pr merge --squash          # SEM --delete-branch
git switch main && git pull --ff-only
git switch refino-rag && git reset --hard origin/main && git push --force-with-lease
```

---

## Parte 5 — Retornando para as configurações anteriores

Como **desfazer cada alteração** deste documento, uma a uma. São ajustes de
**configuração** (VS Code / Git / GitHub) — não são versionados pela tag
`baseline-pre-refino`; por isso têm reversão própria, independente do
`PROCESSO_BACKUP.md`.

### 5.0 (recomendado) Fotografar o estado ANTES de mudar

Rode isto **antes** de aplicar qualquer coisa das Partes 1–2, para ter de onde
restaurar:

```bash
mkdir -p backups
cp ~/.config/Code/User/settings.json           backups/vscode-user-settings.antes.json 2>/dev/null || true
git config --global --list                    > backups/gitconfig-global.antes.txt
git config --local  --list                    > backups/gitconfig-local.antes.txt
gh api repos/alencardoug/ws_plataforma_atendimento_codex \
  --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge}' \
  > backups/repo-merge-settings.antes.json
gh api repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection \
  > backups/branch-protection.antes.json 2>&1   # hoje isto retorna 404 "Branch not protected"
```

> **Estado de origem já conhecido** (verificado nesta sessão, 2026-08-26):
> a branch `main` **não tinha proteção nenhuma** (HTTP 404), e o repositório
> estava com `allow_squash_merge=true`, `allow_merge_commit=true`,
> `allow_rebase_merge=true`, `delete_branch_on_merge=false`. As chaves de Git
> (`push.autoSetupRemote`, `pull.ff`, `fetch.prune`, `rebase.autoStash`)
> **não existiam** — reverter = remover (`--unset`), não redefinir.

---

### 5.1 Desfazer — VS Code User settings (global) — refere-se à seção 1.1/1.2

`Ctrl+Shift+P` → "Open User Settings (JSON)" e **apague as linhas que você
adicionou** (`git.branchProtection`, `git.branchProtectionPrompt`,
`git.autofetch`, `git.pruneOnFetch`, `git.confirmSync`, `git.postCommitCommand`).
Salvar — vale na hora.

Só desligar a proteção mantendo o resto:

```jsonc
"git.branchProtection": []   // lista vazia = nenhuma branch protegida no editor
```

Restaurar o arquivo inteiro a partir da foto da 5.0:

```bash
cp backups/vscode-user-settings.antes.json ~/.config/Code/User/settings.json
```

### 5.2 Desfazer — VS Code Workspace settings — refere-se à seção 1.1b

- **Se você não commitou** o `.vscode/settings.json`: apague o arquivo (ou só as
  chaves). `rm .vscode/settings.json`
- **Se você commitou**: faça pelo fluxo normal (branch → PR → merge):

  ```bash
  git switch -c chore/remove-vscode-settings
  git rm .vscode/settings.json        # ou edite deixando só o que quer manter
  git commit -m "chore: remove proteção da main no workspace (volta a valer a User settings)"
  git push && gh pr create --base main --fill && gh pr merge --squash --delete-branch
  ```

Removido o workspace, volta a valer a **User settings** (Parte 1.1) para estas
chaves.

### 5.3 Desfazer — config do Git — refere-se à seção 1.3

Como as chaves não existiam antes, reverter é **remover**:

```bash
# global
for k in push.autoSetupRemote pull.ff fetch.prune rebase.autoStash; do
  git config --global --unset "$k"
done
git config --global --list | grep -E 'push\.|pull\.|fetch\.|rebase\.'   # conferir que sumiram

# se você aplicou como --local (dentro do repo), repita trocando o escopo:
for k in push.autoSetupRemote pull.ff; do git config --local --unset "$k"; done
```

Ou restaurar exatamente a foto da 5.0 comparando com
`backups/gitconfig-global.antes.txt`. Ver de onde um valor vem:
`git config --show-origin --get pull.ff`.

### 5.4 Desfazer — GitHub branch protection (Opção A) — refere-se à seção 2.2

Como não havia proteção antes, reverter = **apagar a proteção**:

```bash
gh api -X DELETE repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection
# conferir: deve voltar a dar 404 "Branch not protected"
gh api repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection 2>&1 | head -1
```

Afrouxar **sem** remover tudo (ex.: parar de exigir PR, mas manter bloqueio de
force-push): reexecute o `PUT` da seção 2.2 com o corpo ajustado — esse endpoint
**substitui** a configuração inteira, então basta enviar o subconjunto desejado.

### 5.5 Desfazer — GitHub ruleset (Opção B) — refere-se à seção 2.3

Só se você usou a Opção B em vez da A:

```bash
# achar o id
gh api repos/alencardoug/ws_plataforma_atendimento_codex/rulesets --jq '.[] | {id, name, enforcement}'
# apagar de vez
gh api -X DELETE repos/alencardoug/ws_plataforma_atendimento_codex/rulesets/<ID>
# ...ou só desativar, mantendo a regra salva:
gh api -X PUT repos/alencardoug/ws_plataforma_atendimento_codex/rulesets/<ID> --input - <<'JSON'
{ "name": "protect-main", "target": "branch", "enforcement": "disabled" }
JSON
```

### 5.6 Desfazer — opções de merge do repositório — refere-se à seção 2.4

Voltar aos valores de origem (5.0):

```bash
gh api -X PATCH repos/alencardoug/ws_plataforma_atendimento_codex \
  -F allow_merge_commit=true \
  -F allow_squash_merge=true \
  -F allow_rebase_merge=true \
  -F delete_branch_on_merge=false
# conferir
gh api repos/alencardoug/ws_plataforma_atendimento_codex \
  --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge}'
```

### 5.7 Reverter tudo de uma vez (ordem)

```bash
# 1. GitHub: solta a main
gh api -X DELETE repos/alencardoug/ws_plataforma_atendimento_codex/branches/main/protection || true
gh api -X PATCH  repos/alencardoug/ws_plataforma_atendimento_codex \
  -F allow_merge_commit=true -F delete_branch_on_merge=false
# 2. Git: remove as chaves adicionadas
for k in push.autoSetupRemote pull.ff fetch.prune rebase.autoStash; do git config --global --unset "$k" 2>/dev/null || true; done
# 3. VS Code: restaura a User settings da foto (ou apague as chaves à mão)
cp backups/vscode-user-settings.antes.json ~/.config/Code/User/settings.json 2>/dev/null || true
# 4. (se criou) remove o workspace settings pelo fluxo de PR — ver 5.2
```

> Isto reverte **configurações**. Código e banco continuam onde estiverem — para
> voltar esses, use `PROCESSO_BACKUP.md` (tag `baseline-pre-refino` +
> `scripts/db_restore.sh`).
