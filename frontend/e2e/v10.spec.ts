import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// 010-governed-autonomous-response (D-041, Constitution Amendment 1.2.0):
// the first-ever mechanism in this project where an LLM-generated draft
// can reach the customer without a per-message operator click, strictly
// bounded by a per-category policy, a global kill switch, and a veto
// window (which may be 0 = immediate send). Continues the package-
// number-not-product-version naming convention `v7`/`v8`/`v9.spec.ts`
// already set for packages 007/008/009.

function requiredEnvironment(name: "E2E_OPERATOR_EMAIL" | "E2E_OPERATOR_PASSWORD"): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser acceptance`);
  return value;
}

const operatorEmail = requiredEnvironment("E2E_OPERATOR_EMAIL");
const operatorPassword = requiredEnvironment("E2E_OPERATOR_PASSWORD");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function psql(sql: string): void {
  // Same deadlock-retry rationale as v7/v8/v9.spec.ts's own psql() — a
  // previous test's real, slow LLM call can still be running server-side
  // after Playwright considers that test "done".
  try {
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  } catch {
    execFileSync("sleep", ["2"]);
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  }
}

const conversationTables = "customer_service.audit_events, customer_service.message_selections, customer_service.message_citations, customer_service.ai_generation_sources, customer_service.ai_generations, customer_service.retrieval_hits, customer_service.retrieval_runs, customer_service.messages, customer_service.conversation_assignments, customer_service.conversations";

// 'preparo' (not 'agenda'): found live in smoke_v10_governed_autonomy.py
// that "agenda"'s real content is tied to appointment-availability offer
// presentation, sweeping the *next* customer message into guided-
// booking's own slot-choice interpretation instead of a normal
// category-gated generation. 'preparo' has plain informational
// (dynamic_data_required=false) content, avoiding that cross-package
// interaction entirely for this test's own purpose.
const QUESTION = "Preciso estar em jejum para a consulta?";

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/operator");
  await page.getByLabel("E-mail").fill(operatorEmail);
  await page.getByLabel("Senha").fill(operatorPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Fila" })).toBeVisible();
}

test.describe("010 acceptance — governed autonomous response", () => {
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    // Deliberately reset to the known baseline this whole file assumes —
    // any earlier test/session's own leftover settings must never leak in.
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 0, autonomy_kill_switch_enabled = false WHERE id = true;");
    psql("UPDATE content.categories SET autonomy_enabled = false WHERE slug = 'preparo';");
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 30, autonomy_kill_switch_enabled = false WHERE id = true;");
    psql("UPDATE content.categories SET autonomy_enabled = false WHERE slug = 'preparo';");
  });

  test("window_seconds=0: an eligible message sends autonomously with no operator click, and the badge reflects it (Constitution Amendment 1.2.0 (d))", async ({ browser }) => {
    test.setTimeout(60_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("link", { name: "Registros" }).click();
      const preparoRow = operator.locator("li").filter({ hasText: "preparo" });
      const preparoCheckbox = preparoRow.getByRole("checkbox");
      // Not .check(): the checkbox is React-controlled and its onChange
      // handler awaits a real API round-trip before the state (and so the
      // checked prop) updates — a native click briefly toggles the DOM
      // then React's own reconciliation reverts it in the same tick since
      // nothing has changed yet, which .check()'s own near-synchronous
      // post-click verification reads as "did not change state" (found
      // live). Click, then wait for the real, eventually-consistent result.
      await preparoCheckbox.click();
      await expect(preparoCheckbox).toBeChecked({ timeout: 10_000 });
      // Kill switch on, window already 0 from beforeEach's own reset —
      // consolidated on this same Registros page alongside category
      // management (found live that placing it on the Operador page
      // instead collided with that page's own pre-existing
      // `getByRole("checkbox").first()` test assumptions).
      // Same async-controlled-checkbox reasoning as preparoCheckbox above.
      const killSwitch = operator.getByLabel("Envio autônomo ativado (interruptor geral)");
      await killSwitch.click();
      await expect(killSwitch).toBeChecked({ timeout: 10_000 });
      await operator.getByRole("link", { name: "Operador" }).click();
      await expect(operator.getByRole("heading", { name: "Fila" })).toBeVisible();

      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill(QUESTION);
      await customer.getByRole("button", { name: "Enviar" }).click();
      await expect(customer.getByText(QUESTION)).toBeVisible();

      // Claim it — evaluate_automatic_trigger() only runs for an assigned
      // conversation (unlike GA-6's own unclaimed path, exercised by the
      // smoke test instead, since it needs no operator UI at all).
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // V2-7's 8s idle debounce, plus real generation latency, plus
      // window_seconds=0's own immediate resolution — a generous
      // real-clock budget for the operator's own 2s poll to observe it.
      await expect(operator.getByText("automático")).toBeVisible({ timeout: 40_000 });
      await expect(customer.getByText(QUESTION)).toBeVisible();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("PAUSE cancels one autonomous send without disabling the category (Constitution Amendment 1.2.0 (d))", async ({ browser }) => {
    test.setTimeout(60_000);
    psql("UPDATE content.categories SET autonomy_enabled = true WHERE slug = 'preparo';");
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 10, autonomy_kill_switch_enabled = true WHERE id = true;");
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const operator = await operatorContext.newPage();
      await login(operator);

      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill(QUESTION);
      await customer.getByRole("button", { name: "Enviar" }).click();
      await expect(customer.getByText(QUESTION)).toBeVisible();

      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // The quick "Pausar" button lives directly on the queue row (plan.md
      // §4 — must work even without opening/claiming further), not inside
      // the opened conversation for this check.
      // The button's accessible name is its visible text ("Pausar") — the
      // longer "Pausar envio autônomo" is only its title tooltip, found
      // live to not participate in the accessible name since the button
      // already has real text content.
      const pauseButton = operator.getByRole("button", { name: "Pausar" });
      await expect(pauseButton).toBeVisible({ timeout: 40_000 });
      await pauseButton.click();
      await expect(pauseButton).toHaveCount(0);

      // Must NOT send even after the 10s window would have elapsed.
      await operator.waitForTimeout(12_000);
      await expect(operator.getByText("automático")).toHaveCount(0);

      const categoryStillOn = await operator.request.get("/api/v1/operator/knowledge/categories", { headers: { Authorization: `Bearer ${await operator.evaluate(() => sessionStorage.getItem("operator_token"))}` } });
      const categories = await categoryStillOn.json() as { slug: string; autonomy_enabled: boolean }[];
      expect(categories.find((c) => c.slug === "preparo")?.autonomy_enabled).toBe(true);
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });
});
