import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// 008-customer-facing-draft-status (D-038): a generic, no-numbers
// "Preparando resposta…" cue on the customer's own tab while the existing
// automatic-draft debounce window is open — reusing automatic_draft_status()
// verbatim. Continues the package-number-not-product-version naming
// convention `smoke_v4_appointment_availability.py`/`smoke_v5_guided_
// booking.py`/`v9.spec.ts` already set for packages 004/005/009.

function requiredEnvironment(name: "E2E_OPERATOR_EMAIL" | "E2E_OPERATOR_PASSWORD"): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser acceptance`);
  return value;
}

const operatorEmail = requiredEnvironment("E2E_OPERATOR_EMAIL");
const operatorPassword = requiredEnvironment("E2E_OPERATOR_PASSWORD");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function psql(sql: string): void {
  // This file's own previous test can leave the automatic-draft trigger
  // (a real, slow LLM call) still running server-side after Playwright
  // considers that test "done" (closing browser contexts does not cancel
  // an already-in-flight backend request) — occasionally racing this
  // TRUNCATE into a genuine Postgres deadlock (found live). One retry
  // after a short pause is enough in practice; a second consecutive
  // deadlock would be a real problem worth surfacing, not silently
  // retried away.
  try {
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  } catch {
    execFileSync("sleep", ["2"]);
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  }
}

const conversationTables = "customer_service.audit_events, customer_service.message_selections, customer_service.message_citations, customer_service.ai_generation_sources, customer_service.ai_generations, customer_service.retrieval_hits, customer_service.retrieval_runs, customer_service.messages, customer_service.conversation_assignments, customer_service.conversations";

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/operator");
  await page.getByLabel("E-mail").fill(operatorEmail);
  await page.getByLabel("Senha").fill(operatorPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Fila" })).toBeVisible();
}

async function startCustomerConversation(page: import("@playwright/test").Page, firstMessage: string): Promise<void> {
  await page.goto("/customer");
  await page.getByRole("button", { name: "Iniciar conversa" }).click();
  await page.getByLabel("Mensagem").fill(firstMessage);
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(firstMessage)).toBeVisible();
}

test.describe("008 acceptance — customer-facing draft status", () => {
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test("customer sees a generic 'Preparando resposta…' cue while the automatic draft is pending, and it clears once the draft lands (CS-1, CS-2, CS-4)", async ({ browser }) => {
    test.setTimeout(60_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Mensagem para checar o aviso de resposta em preparo (008)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // Eligibility (and so the cue) is true as soon as an operator is
      // assigned and there is an uncovered customer message — it does not
      // wait for the full debounce window to elapse (CS-1 reuses
      // automatic_draft_status()'s existing eligibility check verbatim,
      // matching V3-9's own "Respondendo em Ns…" appearing immediately
      // after claim).
      await expect(customer.getByText("Preparando resposta…")).toBeVisible({ timeout: 10_000 });
      // CS-3: never the numeric countdown on the customer's side.
      await expect(customer.getByText(/Respondendo em \d/)).toHaveCount(0);

      // Once the automatic draft actually lands (operator's own poll
      // evaluates the trigger every ~2s; the debounce window is 8s, plus
      // real gpt-5-mini generation latency observed up to ~23s in this
      // environment — 20s total budget was found live to be too tight in
      // a slow moment), the cue must clear.
      await expect(operator.getByText(/^ANSWER|^ABSTAIN/)).toBeVisible({ timeout: 40_000 });
      await expect(customer.getByText("Preparando resposta…")).toHaveCount(0, { timeout: 5_000 });
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("a manual 'Gerar rascunho' click does not clear the customer-facing cue — only the automatic trigger path covers a message (CS-5 regression)", async ({ browser }) => {
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Mensagem para checar que rascunho manual não altera o aviso (008/CS-5)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // Eligibility is already true immediately after claim (matching the
      // primary scenario above).
      await expect(customer.getByText("Preparando resposta…")).toBeVisible({ timeout: 10_000 });

      // A manual "Gerar rascunho" click generates a draft through a wholly
      // separate code path (generate_draft() via the manual endpoint) that
      // never touches `auto_draft_covers_through_message_id` — only
      // evaluate_automatic_trigger() does. CS-5 is a deliberate scope
      // limit: this cue must reflect only the automatic path, so it must
      // stay on, not be cleared by the manual generation below. Checked
      // immediately after the click rather than after the manual
      // generation's own (real-LLM, ~15-25s) completion: waiting that long
      // risks the *automatic* trigger also completing independently in the
      // meantime (its own 8s debounce has long since elapsed by then),
      // which would legitimately clear the cue for an unrelated reason and
      // make this assertion no longer test what CS-5 actually claims.
      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(customer.getByText("Preparando resposta…")).toBeVisible({ timeout: 3_000 });
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });
});
