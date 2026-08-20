import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// 007-completed-booking-visibility (D-037): once a guided-booking (GB)
// flow reaches GUIDED_BOOKING_COMPLETE, both the operator's conversation
// view and the customer's own tab show a summary of what was booked.
// Continues the package-number-not-product-version naming convention
// `smoke_v4_appointment_availability.py`/`smoke_v5_guided_booking.py`/
// `v8.spec.ts`/`v9.spec.ts` already set for packages 004/005/008/009.

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
  // Postgres deadlock (found live, v8.spec.ts). One retry after a short
  // pause is enough in practice.
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

async function sendCustomerMessage(page: import("@playwright/test").Page, body: string): Promise<void> {
  await page.getByLabel("Mensagem").fill(body);
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(body)).toBeVisible();
}

// Generates a manual draft on the operator's latest customer message and
// sends it verbatim — the shared step this whole flow repeats.
async function draftAndSend(operator: import("@playwright/test").Page, latestCustomerText: string, searchHint?: string): Promise<void> {
  // The operator's own 2s poll can lag behind a customer message that was
  // just sent — without this wait, "Desmarcar conversas" + "last checkbox"
  // can select the *previous* message again (found live: two consecutive
  // calls produced generations with the identical triggering_message_id,
  // so the GB flow's second step silently re-processed the first message
  // instead of the customer's actual slot-choice reply).
  await expect(operator.getByText(latestCustomerText)).toBeVisible({ timeout: 15_000 });
  await operator.getByRole("button", { name: "Desmarcar conversas" }).click();
  const checkboxes = operator.locator(".messages .message-select input[type=checkbox]");
  await checkboxes.last().check();
  // generate() always sends manual_search_text alongside
  // selected_message_ids — a hint left filled from a *previous* call
  // would silently poison retrieval for every later step, not just the
  // one that set it. Always set it explicitly (a real near-exact-match
  // hint, matching v9.spec.ts/smoke_v6's own established pattern for
  // pinning real-embedding retrieval against topically-similar-but-wrong
  // catalog content — see smoke_v5_guided_booking.py's own comment on
  // this exact ambiguity — or empty, to fall back to natural retrieval
  // from the selected message alone).
  await operator.getByLabel("Busca manual").fill(searchHint ?? "");
  // Wait for this click's own POST /drafts response, not just for
  // ANSWER/ABSTAIN text to be *somewhere* on screen — that text can
  // already be present from a prior step's draft (or a concurrent
  // automatic-trigger draft), satisfying a plain visibility wait before
  // this click's own fresh draft actually lands (found live: a step
  // silently reused the previous step's stale draft instead of waiting
  // for its own).
  const [draftResponse] = await Promise.all([
    operator.waitForResponse((response) => response.url().includes("/drafts") && response.request().method() === "POST", { timeout: 30_000 }),
    operator.getByRole("button", { name: "Gerar rascunho" }).click(),
  ]);
  if (!draftResponse.ok()) throw new Error(`POST /drafts failed: ${draftResponse.status()} ${await draftResponse.text()}`);
  await expect(operator.getByText(/^ANSWER|^ABSTAIN/)).toBeVisible({ timeout: 15_000 });
  // Copies draft.draft_text into the reply textarea — without this, the
  // textarea stays empty and the subsequent "Enviar" click silently no-ops
  // against the <textarea required> field, so the flow never actually
  // advances (found live: all 4 GB steps generated but none were ever
  // really sent, so GB's own latest_sent_generation_trigger() check never
  // saw a prior sent step and the state machine never progressed).
  await operator.getByRole("button", { name: /Usar sugestão|Usar documento completo/ }).click();
  await operator.getByRole("button", { name: "Enviar" }).click();
}

test.describe("007 acceptance — completed booking visibility", () => {
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test("a completed guided-booking flow shows the full detail summary on both the operator's and the customer's tab (BS-2, BS-5, BS-6, BS-7)", async ({ browser }) => {
    test.setTimeout(60_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: "Garantir disponibilidade (D+1/D+7)" }).click();
      await expect(operator.getByRole("status")).toBeVisible();

      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      // "amanhã" (not "essa semana") deliberately: it's in DATE_KEYWORDS
      // (006/ND), resolving deterministically with no LLM call, and it's a
      // near-exact match for the catalog's own "Existe consulta disponível
      // amanhã?" entry — avoiding two independent sources of real-provider
      // non-determinism (LLM date-fallback, embedding retrieval ranking)
      // this test doesn't need, since it's testing booking-completion
      // visibility (BS-2/5/6/7), not date parsing (covered separately by
      // 006's own tests).
      await sendCustomerMessage(customer, "Existe consulta disponível amanhã?");

      await operator.getByRole("button", { name: /^Aguardando/ }).click();
      await draftAndSend(operator, "Existe consulta disponível amanhã?", "Existe consulta disponível amanhã?"); // availability offers

      await sendCustomerMessage(customer, "primeira opção");
      await draftAndSend(operator, "primeira opção"); // GUIDED_SLOT_SELECTION — offer + CPF request

      await sendCustomerMessage(customer, "tabom 123.456..789.10");
      await draftAndSend(operator, "tabom 123.456..789.10"); // GUIDED_CPF_CONFIRMED — payment question

      await sendCustomerMessage(customer, "sim, paguei");
      await draftAndSend(operator, "sim, paguei"); // GUIDED_BOOKING_COMPLETE

      execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-c", "SELECT m.body, g.status, g.trigger, g.abstention_reason, left(g.draft_text,80), g.dynamic_pattern_used, g.created_at FROM customer_service.ai_generations g JOIN customer_service.messages m ON m.id=g.triggering_message_id ORDER BY g.created_at;"], { cwd: repoRoot, stdio: "inherit" });

      // Both sides show the same full-detail line (BS-2 sourced it from
      // the specific offer GB-2 identified, not just the specialty) —
      // "(America/São_Paulo)" only appears in the full-detail template
      // (render_booking_summary_line), never the specialty-only fallback.
      const operatorSummary = operator.getByLabel("Agendamento realizado");
      await expect(operatorSummary).toBeVisible({ timeout: 10_000 });
      await expect(operatorSummary).toContainText("(America/São_Paulo)");

      const customerSummary = customer.getByLabel("Agendamento realizado");
      await expect(customerSummary).toBeVisible({ timeout: 10_000 });
      await expect(customerSummary).toContainText("(America/São_Paulo)");
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("closing the browser tab and reopening /customer fresh loses the booking summary (BS-6 outcome 5 — session-only, never persisted)", async ({ browser }) => {
    const customerContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await customer.goto("/customer");
      await customer.getByRole("button", { name: "Iniciar conversa" }).click();
      await customer.getByLabel("Mensagem").fill("Mensagem para checar persistência do resumo (007/BS-6)");
      await customer.getByRole("button", { name: "Enviar" }).click();

      const conversationId = await customer.evaluate(() => sessionStorage.getItem("conversation_id"));
      expect(conversationId).toBeTruthy();

      // Simulates closing the tab: a genuinely new Page (sessionStorage is
      // scoped per top-level browsing context/tab, so a new Page already
      // starts with none — no explicit clear needed, and clearing before
      // the page has navigated to the app's own origin throws a
      // SecurityError on a blank page, found live).
      await customerContext.clearCookies();
      const freshPage = await customerContext.newPage();
      await freshPage.goto("/customer");
      await expect(freshPage.getByRole("button", { name: "Iniciar conversa" })).toBeVisible();
      expect(await freshPage.evaluate(() => sessionStorage.getItem("conversation_id"))).toBeNull();
      await expect(freshPage.getByLabel("Agendamento realizado")).toHaveCount(0);
    } finally {
      await customerContext.close();
    }
  });
});
