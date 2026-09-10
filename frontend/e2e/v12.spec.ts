import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// 012-appointment-availability-continuity-and-booking-action (D-044): the
// Operator Booking-Offer action (OB) — a "Gerar oferta de agendamento"
// button, between "Enviar" and "Encerrar conversa" in the operator
// conversation panel, that runs the appointment_availability resolver
// directly into an ordinary N2 draft. Never an autonomous send. Naming
// follows the vN.spec.ts package-number convention.

function requiredEnvironment(name: "E2E_OPERATOR_EMAIL" | "E2E_OPERATOR_PASSWORD"): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser acceptance`);
  return value;
}

const operatorEmail = requiredEnvironment("E2E_OPERATOR_EMAIL");
const operatorPassword = requiredEnvironment("E2E_OPERATOR_PASSWORD");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function psql(sql: string): void {
  try {
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  } catch {
    execFileSync("sleep", ["2"]);
    execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
  }
}

const conversationTables =
  "customer_service.audit_events, customer_service.message_selections, customer_service.message_citations, customer_service.ai_generation_sources, customer_service.ai_generations, customer_service.retrieval_hits, customer_service.retrieval_runs, customer_service.messages, customer_service.conversation_assignments, customer_service.conversations, customer_service.appointment_offer_presentations";

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/operator");
  await page.getByLabel("E-mail").fill(operatorEmail);
  await page.getByLabel("Senha").fill(operatorPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Fila" })).toBeVisible();
}

test.describe("012 acceptance — operator booking-offer action (OB)", () => {
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    // N5/governed autonomy fully off, so nothing here can be autonomously
    // sent — OB must produce a draft only.
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 0, autonomy_kill_switch_enabled = false, n5_kill_switch_enabled = false, automatic_trigger_idle_seconds = 8 WHERE id = true;");
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
    psql("UPDATE customer_service.system_settings SET autonomy_window_seconds = 30, n5_kill_switch_enabled = false WHERE id = true;");
  });

  test("operator generates an availability offer as a draft between Enviar and Encerrar, then sends it explicitly", async ({ browser }) => {
    test.setTimeout(60_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const operator = await operatorContext.newPage();
      await login(operator);
      // Make sure the simulated agenda has data (AC also keeps it topped
      // up, but this test must not depend on a prior poll having run).
      await operator.getByRole("button", { name: "Garantir disponibilidade (D+1/D+7)" }).click();

      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill("Quero agendar uma consulta");
      await customer.getByRole("button", { name: "Enviar" }).click();
      await expect(customer.getByText("Quero agendar uma consulta")).toBeVisible();

      await operator.getByRole("button", { name: /^Aguardando/ }).click();
      await expect(operator.getByText("Quero agendar uma consulta")).toBeVisible();

      const offerButton = operator.getByRole("button", { name: "Gerar oferta de agendamento" });
      await expect(offerButton).toBeEnabled();
      await offerButton.click();

      // The draft panel (IA / Evidências) shows an ANSWER draft with the
      // rendered offer block — no customer-visible message yet.
      await expect(operator.getByText("ANSWER")).toBeVisible({ timeout: 30_000 });
      await expect(operator.getByText(/simulação/)).toBeVisible();
      await expect(customer.getByText(/simulação/)).toHaveCount(0);

      // Operator explicitly sends the draft.
      await operator.getByRole("button", { name: "Usar sugestão" }).click();
      await operator.getByRole("button", { name: "Enviar" }).click();
      await expect(customer.getByText(/simulação/)).toBeVisible({ timeout: 15_000 });
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });
});
