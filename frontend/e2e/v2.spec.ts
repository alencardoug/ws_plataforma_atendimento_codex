import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

function requiredEnvironment(name: "E2E_OPERATOR_EMAIL" | "E2E_OPERATOR_PASSWORD"): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser acceptance`);
  return value;
}

const operatorEmail = requiredEnvironment("E2E_OPERATOR_EMAIL");
const operatorPassword = requiredEnvironment("E2E_OPERATOR_PASSWORD");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function psql(sql: string): void {
  // A previous test's automatic-draft trigger (a real, slow LLM call) can
  // still be running server-side after Playwright considers that test
  // "done" — closing browser contexts does not cancel an already-in-flight
  // backend request — occasionally racing this TRUNCATE into a genuine
  // Postgres deadlock (found live, v8.spec.ts; recurs here once v1.spec.ts
  // reliably completes its own real "Gerar rascunho" call instead of
  // failing early). One retry after a short pause is enough in practice.
  try {
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  } catch {
    execFileSync("sleep", ["2"]);
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  }
}

function restartBackend(): void {
  execFileSync("docker", ["compose", "restart", "backend"], { cwd: repoRoot, stdio: "inherit" });
  execFileSync("bash", ["-c", "until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 1; done"], { cwd: repoRoot, stdio: "inherit", timeout: 30_000 });
}

// Each of T124/T125/T126/T127 claims an operator conversation slot (cap is
// OPERATOR_MAX_ACTIVE_CONVERSATIONS, 4 by default) and does not release it —
// closing mid-scenario would interfere with what each scenario is proving.
// Reset conversation state before this file's tests run so capacity is never
// exhausted by another spec file's (e.g. v1.spec.ts's) leftover claims, or by
// a prior run of this same file.
const conversationTables = "customer_service.audit_events, customer_service.message_selections, customer_service.message_citations, customer_service.ai_generation_sources, customer_service.ai_generations, customer_service.retrieval_hits, customer_service.retrieval_runs, customer_service.messages, customer_service.conversation_assignments, customer_service.conversations";

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/operator");
  await page.getByLabel("E-mail").fill(operatorEmail);
  await page.getByLabel("Senha").fill(operatorPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Fila" })).toBeVisible();
}

test.describe("V2 acceptance (tasks.md T124-T128)", () => {
  test.beforeAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    // T128 deliberately trips the anonymous-token rate limiter's lockout.
    // That state lives in the backend process's memory, keyed by client IP
    // (customer_care/shared/http.py client_ip()) — every request through
    // this same docker-compose nginx proxy resolves to the same real
    // source IP (this test runner's own machine), so the lockout it
    // engaged would otherwise still be active for whichever e2e/*.spec.ts
    // file runs next (e.g. v3.spec.ts) in the same `playwright test` pass.
    // Restarting clears it, matching what T128 always needed done before
    // running other token-validation-dependent scenarios from this host.
    restartBackend();
  });

  test("typing-debounced automatic trigger batches correctly across multiple bursts (T124, V2-7 automatic)", async ({ browser }) => {
    // Each automatic draft includes the deliberate 8s debounce plus a real
    // provider call. Two bursts therefore need more than the old 60s test
    // budget when provider latency is above a few seconds.
    test.setTimeout(150_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill("Mensagem automática 1 (T124)");
      await customer.getByRole("button", { name: "Enviar" }).click();
      await expect(customer.getByText("Mensagem automática 1 (T124)")).toBeVisible();

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // Resume typing within the 8s window: this must NOT produce a draft yet.
      await customer.getByLabel("Mensagem").fill("ainda digitando");
      await customer.waitForTimeout(4_000);
      await customer.getByLabel("Mensagem").fill("");
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toHaveCount(0);

      // Now stay idle for the full 8s debounce; exactly one automatic draft must appear.
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 45_000 });
      const firstDraft = await operator.locator(".draft-panel .badge").textContent();
      expect(firstDraft).toMatch(/ANSWER|ABSTAIN/);

      // Second burst: two more customer messages, then idle again.
      await customer.getByLabel("Mensagem").fill("Mensagem automática 2 (T124)");
      await customer.getByRole("button", { name: "Enviar" }).click();
      await customer.getByLabel("Mensagem").fill("Mensagem automática 3 (T124)");
      await customer.getByRole("button", { name: "Enviar" }).click();
      await operator.waitForTimeout(9_000);
      await operator.reload();
      await operator.getByRole("button", { name: /^Em atendimento/ }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 45_000 });
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("\"Buscar evidências\" and \"Gerar rascunho\" are independent (T125, V2-3/V2-4)", async ({ browser }) => {
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill("Pergunta para checar independência T125");
      await customer.getByRole("button", { name: "Enviar" }).click();

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      const checkbox = operator.getByRole("checkbox").first();
      await expect(checkbox).toBeChecked();

      await operator.getByLabel("Busca manual").fill("horário de atendimento");
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      await expect(operator.locator(".evidence-item").first()).toBeVisible();

      // Selecting search evidence must not touch the message-selection checkboxes.
      await operator.locator(".evidence-item").first().getByRole("button", { name: "Selecionar" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });
      await expect(checkbox).toBeChecked();

      // "Gerar rascunho" from the (still default-checked) message selection must not
      // be affected by the evidence-selection generation that just happened.
      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("dynamic-pattern happy path and fallback (T126, V2-6)", async ({ browser }) => {
    test.setTimeout(120_000);
    const category = `e2e-t126-${Date.now()}`;
    psql(`INSERT INTO content.knowledge_dynamic_fixture (category, status, label, ordinal) VALUES ('${category}', 'ok', 'Segunda 09h (T126)', 1), ('${category}', 'ok', 'Terca 10h (T126)', 2);`);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill("Pergunta de teste dinamico T126");
      await customer.getByRole("button", { name: "Enviar" }).click();

      const operator = await operatorContext.newPage();
      await login(operator);

      // Happy path: a binding whose filter matches rows. V3-8 replaced the
      // free-text "Categoria"/"Tabela"/"Filtro (JSON)"/"Colunas de saída
      // (JSON)" inputs with guided selectors backed by the live category
      // registry and real `information_schema` column introspection —
      // updated here to match (found and fixed while implementing V3-8,
      // T132: this suite had not been rerun against V3's UI until now).
      await operator.goto("/operator/knowledge");
      await operator.getByRole("button", { name: "Criar nova categoria" }).click();
      await operator.getByLabel("Identificador").fill(category);
      await operator.getByLabel("Rótulo").fill(`Categoria fixture ${category}`);
      await operator.getByRole("button", { name: "Criar categoria" }).click();
      await expect(operator.getByLabel("Categoria")).toHaveValue(category);
      await operator.getByLabel("Pergunta").fill(`Quais horarios fixture ${category} estao disponiveis?`);
      await operator.getByLabel("Resposta", { exact: true }).fill("Horario fixture: {{slot}}.");
      await operator.getByLabel("Tabela").selectOption("knowledge_dynamic_fixture");
      await operator.getByLabel("Coluna do filtro").selectOption("category");
      await operator.getByLabel("Valor do filtro").fill(category);
      await operator.getByRole("button", { name: "Adicionar filtro" }).click();
      await operator.getByLabel("Coluna de saída").selectOption("label");
      await operator.getByLabel("Nome da variável").fill("slot");
      await operator.getByRole("button", { name: "Adicionar coluna" }).click();
      await operator.getByRole("button", { name: "Adicionar pergunta e resposta" }).click();
      await expect(operator.getByText(`Quais horarios fixture ${category} estao disponiveis?`)).toBeVisible();

      // Fallback path: same table/columns, filter matches zero rows.
      await operator.getByLabel("Categoria").selectOption(category);
      await operator.getByLabel("Pergunta").fill(`Quais horarios fixture ${category} inexistente estao disponiveis?`);
      await operator.getByLabel("Resposta", { exact: true }).fill("Horario fixture: {{slot}}.");
      await operator.getByLabel("Tabela").selectOption("knowledge_dynamic_fixture");
      await operator.getByLabel("Coluna do filtro").selectOption("category");
      await operator.getByLabel("Valor do filtro").fill(`${category}-no-match`);
      await operator.getByRole("button", { name: "Adicionar filtro" }).click();
      await operator.getByLabel("Coluna de saída").selectOption("label");
      await operator.getByLabel("Nome da variável").fill("slot");
      await operator.getByRole("button", { name: "Adicionar coluna" }).click();
      await operator.getByRole("button", { name: "Adicionar pergunta e resposta" }).click();
      await expect(operator.getByText(`Quais horarios fixture ${category} inexistente estao disponiveis?`)).toBeVisible();

      await operator.goto("/operator");
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      await operator.getByLabel("Busca manual").fill(`horarios fixture ${category} estao disponiveis`);
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      const happyPathItem = operator.locator(".evidence-item").filter({ hasText: `Quais horarios fixture ${category} estao disponiveis?` });
      await expect(happyPathItem).toBeVisible({ timeout: 15_000 });
      await happyPathItem.getByRole("button", { name: "Selecionar" }).click();
      await expect(operator.locator(".draft-panel")).toContainText("Segunda 09h (T126)");
      await expect(operator.locator(".draft-panel")).toContainText("Terca 10h (T126)");

      await operator.getByLabel("Busca manual").fill(`horarios fixture ${category} inexistente estao disponiveis`);
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      const fallbackItem = operator.locator(".evidence-item").filter({ hasText: `Quais horarios fixture ${category} inexistente estao disponiveis?` });
      await expect(fallbackItem).toBeVisible({ timeout: 15_000 });
      await fallbackItem.getByRole("button", { name: "Selecionar" }).click();
      await expect(operator.locator(".draft-panel .badge")).toHaveText("ABSTAIN");
      await expect(operator.locator(".draft-panel")).not.toContainText("no row matched filter");
      await expect(operator.locator(".draft-panel")).not.toContainText("allowlist");
    } finally {
      await customerContext.close();
      await operatorContext.close();
      psql(`DELETE FROM content.knowledge_dynamic_fixture WHERE category = '${category}';`);
    }
  });

  test("knowledge CRUD round trip: create -> retrievable -> used in a generation -> deactivate -> no longer retrievable (T127, V2-8)", async ({ browser }) => {
    test.setTimeout(90_000);
    const category = `e2e-t127-${Date.now()}`;
    const question = `Pergunta unica de round-trip ${category}?`;
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill("Pergunta de teste round-trip T127");
      await customer.getByRole("button", { name: "Enviar" }).click();

      const operator = await operatorContext.newPage();
      await login(operator);

      await operator.goto("/operator/knowledge");
      await operator.getByRole("button", { name: "Criar nova categoria" }).click();
      await operator.getByLabel("Identificador").fill(category);
      await operator.getByLabel("Rótulo").fill(`Categoria fixture ${category}`);
      await operator.getByRole("button", { name: "Criar categoria" }).click();
      await expect(operator.getByLabel("Categoria")).toHaveValue(category);
      await operator.getByLabel("Pergunta").fill(question);
      await operator.getByLabel("Resposta", { exact: true }).fill("Resposta aprovada de round-trip T127.");
      await operator.getByRole("button", { name: "Adicionar pergunta e resposta" }).click();
      await expect(operator.getByText(question)).toBeVisible();

      await operator.goto("/operator");
      await operator.getByRole("button", { name: /^Aguardando/ }).click();
      await operator.getByLabel("Busca manual").fill(question);
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      const item = operator.locator(".evidence-item").filter({ hasText: question });
      await expect(item).toBeVisible({ timeout: 15_000 });
      await item.getByRole("button", { name: "Selecionar" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });

      await operator.goto("/operator/knowledge");
      await operator.locator("li").filter({ hasText: question }).getByRole("button", { name: "Desativar" }).click();
      await expect(operator.getByText(question)).toHaveCount(0);

      await operator.goto("/operator");
      await operator.getByRole("button", { name: /^Em atendimento|^Aguardando/ }).first().click().catch(() => undefined);
      await operator.getByLabel("Busca manual").fill(question);
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      await expect(operator.locator(".evidence-item").filter({ hasText: question })).toHaveCount(0);
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("token validation lockout engages and blocks further attempts (T128, V2-2)", async ({ request }) => {
    const created = await request.post("/api/v1/public/conversations");
    expect(created.ok()).toBeTruthy();
    const { conversation } = await created.json();

    let lockedOut = false;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      const response = await request.get(`/api/v1/public/conversations/${conversation.id}`, { headers: { Authorization: "Bearer WRONGTOK" } });
      if (response.status() === 429) {
        const body = await response.json();
        expect(body.code).toBe("RATE_LIMITED");
        lockedOut = true;
        break;
      }
      expect(response.status()).toBe(403);
    }
    expect(lockedOut).toBe(true);
  });
});
