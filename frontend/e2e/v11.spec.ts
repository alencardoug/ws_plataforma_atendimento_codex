import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// 011-ungoverned-fictional-demo-autonomy-n5 (D-042, Constitution Amendment
// 1.3.0): a second, independent autonomy exception — no evidence/category
// requirement, justified solely by this project's fictional-demo nature
// (Amendment 1.3.0 clause (e), the customer/operator-login disclaimer
// banners). Continues the package-number naming convention `v10.spec.ts`
// set for package 010.

function requiredEnvironment(name: "E2E_OPERATOR_EMAIL" | "E2E_OPERATOR_PASSWORD"): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser acceptance`);
  return value;
}

const operatorEmail = requiredEnvironment("E2E_OPERATOR_EMAIL");
const operatorPassword = requiredEnvironment("E2E_OPERATOR_PASSWORD");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function psql(sql: string): void {
  // Same deadlock-retry rationale as v7-v10.spec.ts's own psql().
  try {
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  } catch {
    execFileSync("sleep", ["2"]);
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  }
}

const conversationTables = "customer_service.audit_events, customer_service.message_selections, customer_service.message_citations, customer_service.ai_generation_sources, customer_service.ai_generations, customer_service.retrieval_hits, customer_service.retrieval_runs, customer_service.messages, customer_service.conversation_assignments, customer_service.conversations";

// Deliberately outside the knowledge base entirely — unlike v10.spec.ts's
// 'preparo' question, this must retrieve no category-relevant evidence at
// all, so the governed (010) path never fires and only N5 can answer it.
const UNCOVERED_QUESTION = "Qual a previsão do tempo para amanhã em Marte? (e2e v11)";

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/operator");
  await page.getByLabel("E-mail").fill(operatorEmail);
  await page.getByLabel("Senha").fill(operatorPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Fila" })).toBeVisible();
}

test.describe("011 acceptance — ungoverned fictional-demo autonomy (N5)", () => {
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    // Deliberately reset to the known baseline this whole file assumes —
    // any earlier test/session's own leftover settings must never leak in.
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 0, autonomy_kill_switch_enabled = false, n5_kill_switch_enabled = false, automatic_trigger_idle_seconds = 8 WHERE id = true;");
    psql("UPDATE content.categories SET autonomy_enabled = false WHERE slug = 'preparo';");
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 30, autonomy_kill_switch_enabled = false, n5_kill_switch_enabled = false, automatic_trigger_idle_seconds = 8 WHERE id = true;");
    psql("UPDATE content.categories SET autonomy_enabled = false WHERE slug = 'preparo';");
  });

  test("N5 switch is independent of the governed kill switch, and an uncovered question still sends autonomously with the distinct N5 badge", async ({ browser }) => {
    test.setTimeout(60_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("link", { name: "Registros" }).click();

      // Governed kill switch stays untouched (off, from beforeEach) — only
      // N5's own switch is turned on, proving the two are independent.
      const n5Switch = operator.getByLabel(/Autonomia sem filtro de evidência/);
      await n5Switch.click();
      await expect(n5Switch).toBeChecked({ timeout: 10_000 });
      const governedSwitch = operator.getByLabel("Envio autônomo ativado (interruptor geral)");
      await expect(governedSwitch).not.toBeChecked();

      await operator.getByRole("link", { name: "Operador" }).click();
      await expect(operator.getByRole("heading", { name: "Fila" })).toBeVisible();

      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill(UNCOVERED_QUESTION);
      await customer.getByRole("button", { name: "Enviar" }).click();
      await expect(customer.getByText(UNCOVERED_QUESTION)).toBeVisible();

      // Claim it — the claimed-conversation trigger path exercises the
      // same maybe_open_autonomous_window() both mechanisms share.
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // 8s idle debounce (beforeEach's own reset), plus real generation
      // latency, plus window_seconds=0's own immediate resolution.
      const badge = operator.getByTitle("Enviada automaticamente sem evidência — modo N5, demonstração");
      await expect(badge).toBeVisible({ timeout: 40_000 });
      await expect(customer.getByText(UNCOVERED_QUESTION)).toBeVisible();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });
});
