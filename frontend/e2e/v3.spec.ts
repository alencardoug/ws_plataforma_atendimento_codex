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
  execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-U", "oncology", "-d", "oncology", "-v", "ON_ERROR_STOP=1", "-c", sql], { cwd: repoRoot, stdio: "inherit" });
}

// Same rationale as v2.spec.ts: each scenario claims an operator
// conversation slot (cap 4) and does not release it mid-scenario.
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

test.describe("V3 acceptance (tasks.md T132)", () => {
  // Unlike v2.spec.ts (4 scenarios, each claiming exactly one of the 4
  // available slots), this file has 5 scenarios that each claim a slot and
  // don't release it — resetting between every test (not just once for the
  // whole file) keeps every scenario within the OPERATOR_MAX_ACTIVE_
  // CONVERSATIONS cap regardless of run order.
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test("quick-approve, mark-incorrect, escalate, transformar-em-Q&A, and regenerate-with-instruction (V3-1, V3-2)", async ({ browser }) => {
    // Two real LLM draft generations happen in this scenario against the
    // configured real OpenAI provider — generously timed (found while
    // adding this suite: response time grows noticeably when this test
    // runs late in a full `playwright test` pass, after several other
    // files' real generations have already run against the same backend).
    test.setTimeout(120_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Vocês atendem aos sábados? (v3 T132)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      // Quick-approve: byte-for-byte send, no edit of the draft box. Falls
      // back to a manual send when the draft abstains (Aprovar is only
      // offered for ANSWER) so the rest of this scenario (which needs a
      // source_generation_id-linked message) has deterministic state
      // either way.
      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 45_000 });
      const approveButton = operator.getByRole("button", { name: "Aprovar" });
      if (await approveButton.isVisible().catch(() => false)) {
        const draftText = await operator.locator(".draft-panel .message-body").textContent();
        await approveButton.click();
        // A poll already in flight can be completing a real automatic draft
        // while quick-approve refreshes the conversation. Wait through that
        // bounded provider call instead of relying on Playwright's 5s default.
        await expect(operator.locator(".message.operator").last()).toBeVisible({ timeout: 20_000 });
        const sentText = await operator.locator(".message.operator .message-body").last().textContent();
        expect(sentText).toBe(draftText);
      } else {
        await operator.locator("#operator-reply").fill("Resposta manual de fallback (T132).");
        await operator.getByRole("button", { name: "Enviar", exact: true }).click();
        await expect(operator.locator(".message.operator").last()).toBeVisible({ timeout: 20_000 });
      }

      // mark-incorrect / escalate: reachable on the just-sent message,
      // idempotent-looking toggle to a "done" label, no navigation away.
      const lastOperatorMessage = operator.locator(".message.operator").last();
      const markButton = lastOperatorMessage.getByRole("button", { name: "Marcar como incorreto" });
      await markButton.click();
      await expect(lastOperatorMessage.getByRole("button", { name: "✓ Marcado como incorreto" })).toBeVisible();
      const escalateButton = lastOperatorMessage.getByRole("button", { name: "Sinalizar lacuna de conteúdo" });
      await escalateButton.click();
      await expect(lastOperatorMessage.getByRole("button", { name: "✓ Sinalizado (lacuna de conteúdo)" })).toBeVisible();

      // regenerate-with-instruction: instruction text box combines with
      // (does not replace) the existing message-selection input.
      // The trailing-customer-run default selection (V2-4) is now empty —
      // the last message is the operator reply we just sent — so "Gerar
      // rascunho" needs a message re-checked (or manual-search text) to be
      // enabled at all; this is expected, not a bug in the checkbox default.
      await operator.getByRole("checkbox").first().check();
      await operator.getByLabel("Instrução para regenerar (opcional)").fill("Seja mais breve.");
      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 45_000 });

      // transformar-em-Q&A: only offered on an edited (not quick-approved)
      // message — send this regenerated draft with a manual edit.
      const editedBody = "Resposta editada manualmente pelo operador (T132).";
      await operator.locator("#operator-reply").fill(editedBody);
      await operator.getByRole("button", { name: "Enviar", exact: true }).click();
      await expect(operator.getByText(editedBody)).toBeVisible();
      const editedMessage = operator.locator(".message.operator").filter({ hasText: editedBody });
      const transformButton = editedMessage.getByRole("button", { name: "Transformar em Q&A" });
      await expect(transformButton).toBeVisible();
      await transformButton.click();
      await expect(operator).toHaveURL(/\/operator\/knowledge$/);
      // Playwright's accessible-name computation for an implicit
      // <label>Resposta<textarea>…</textarea></label> concatenates the
      // label text with the textarea's own rendered value once it is
      // non-empty (the same quirk v2.spec.ts's "Tabela" select hit) — a
      // direct id locator sidesteps it reliably.
      await expect(operator.locator("#qa-answer")).toHaveValue(editedBody);
      const questionValue = await operator.getByLabel("Pergunta").inputValue();
      expect(questionValue.length).toBeGreaterThan(0);
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("Limpar (V3-7) resets the draft/search panel without touching message selection", async ({ browser }) => {
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Pergunta para checar o Limpar (T132 V3-7)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      const checkbox = operator.getByRole("checkbox").first();
      await expect(checkbox).toBeChecked();

      await operator.getByLabel("Busca manual").fill("horário de atendimento");
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      await expect(operator.locator(".evidence-item").first()).toBeVisible({ timeout: 15_000 });

      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 20_000 });

      await operator.getByRole("button", { name: "Limpar" }).click();
      await expect(operator.locator(".draft-panel")).toHaveCount(0);
      await expect(operator.locator(".evidence-item")).toHaveCount(0);
      // Message selection must be unaffected by Limpar (independent of V2-4).
      await expect(checkbox).toBeChecked();
      // No navigation away from the conversation.
      await expect(operator.getByRole("heading", { name: /Conversa/ })).toBeVisible();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("automatic-draft countdown reflects server state and never goes negative (V3-9)", async ({ browser }) => {
    test.setTimeout(30_000);
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Mensagem para checar countdown (T132 V3-9)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      const countdown = operator.locator(".typing-indicator", { hasText: /Rascunho automático em|Gerando rascunho automaticamente/ });
      await expect(countdown).toBeVisible({ timeout: 10_000 });
      await expect(countdown).not.toContainText("-");

      const firstText = await countdown.textContent();
      await operator.waitForTimeout(2_000);
      const secondText = await countdown.textContent();
      // The countdown must move (decrease or transition to the firing
      // message) — it is not a static label — and must never show a
      // negative value at any point observed.
      expect(secondText).not.toBe(firstText);
      expect(secondText).not.toContain("-");

      // New customer activity (another message) must extend/reset the
      // window — matching V2-7's existing reset behavior, not a
      // separate/divergent clock.
      await customer.getByLabel("Mensagem").fill("Segunda mensagem estende o countdown (T132 V3-9)");
      await customer.getByRole("button", { name: "Enviar" }).click();
      await expect(operator.getByText("Segunda mensagem estende o countdown (T132 V3-9)")).toBeVisible({ timeout: 5_000 });
      await expect(countdown).toBeVisible();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("selecting evidence scrolls to top and is not disturbed by the periodic poll (V3-10)", async ({ browser }) => {
    const customerContext = await browser.newContext();
    // A short viewport guarantees the page is scrollable regardless of how
    // much content the workspace layout happens to have.
    const operatorContext = await browser.newContext({ viewport: { width: 1000, height: 400 } });
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Pergunta para checar scroll-to-top (T132 V3-10)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      await operator.evaluate(() => window.scrollTo(0, 400));
      const scrolledBefore = await operator.evaluate(() => window.scrollY);
      expect(scrolledBefore).toBeGreaterThan(0);

      await operator.getByLabel("Busca manual").fill("horário de atendimento");
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      await expect(operator.locator(".evidence-item").first()).toBeVisible({ timeout: 15_000 });
      await operator.locator(".evidence-item").first().getByRole("button", { name: "Selecionar" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });
      await expect.poll(() => operator.evaluate(() => window.scrollY)).toBeLessThan(50);

      // Scroll back down manually; the 2-second poll refreshing unrelated
      // state must not yank the position back to top on its own.
      await operator.evaluate(() => window.scrollTo(0, 400));
      await operator.waitForTimeout(3_000);
      const scrolledAfterPoll = await operator.evaluate(() => window.scrollY);
      expect(scrolledAfterPoll).toBeGreaterThan(0);
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("confirm-before-close actually closes on both surfaces when confirmed (V3-11)", async ({ browser }) => {
    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Pergunta antes de encerrar (T132 V3-11 operator)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      await operator.getByRole("button", { name: "Encerrar conversa", exact: true }).click();
      await expect(operator.getByRole("alertdialog", { name: "Confirmar encerramento" })).toBeVisible();
      await operator.getByRole("button", { name: "Encerrar conversa", exact: true }).click();
      // closeConversation() clears the operator's selection back to the
      // queue-empty state on success (main.tsx) — it does not stay on this
      // conversation showing an inline "closed" message (that copy only
      // ever appears if a still-selected conversation's status is not
      // ACTIVE, which reopening a closed conversation would show, not the
      // close action itself).
      await expect(operator.getByText("Selecione uma conversa na fila para começar.")).toBeVisible();

      // Customer surface: independent confirm step, own conversation.
      const secondCustomer = await customerContext.newPage();
      await startCustomerConversation(secondCustomer, "Pergunta antes de encerrar (T132 V3-11 customer)");
      await secondCustomer.getByRole("button", { name: "Encerrar conversa", exact: true }).click();
      await expect(secondCustomer.getByRole("alertdialog", { name: "Confirmar encerramento" })).toBeVisible();
      await secondCustomer.getByRole("button", { name: "Encerrar conversa", exact: true }).click();
      await expect(secondCustomer.getByText("Como você avalia este atendimento?")).toBeVisible();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });
});
