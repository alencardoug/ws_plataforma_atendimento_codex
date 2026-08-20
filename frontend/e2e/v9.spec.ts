import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

import { expect, test, type APIRequestContext } from "@playwright/test";

// 009-two-phase-clinical-evidence (D-039): the operator's "IA e evidências"
// sidebar must never show a clinical hit's full parent document by
// default — only its matched child excerpt, until "Trazer documento" is
// explicitly clicked — for both manual-search evidence and (new here)
// automatic-draft evidence. Continues the package-number-not-product-
// version naming convention `smoke_v4_appointment_availability.py`/
// `smoke_v5_guided_booking.py` already set for packages 004/005.

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

async function startCustomerConversation(page: import("@playwright/test").Page, firstMessage: string): Promise<void> {
  await page.goto("/customer");
  await page.getByRole("button", { name: "Iniciar conversa" }).click();
  await page.getByLabel("Mensagem").fill(firstMessage);
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(firstMessage)).toBeVisible();
}

async function apiOperatorToken(request: APIRequestContext): Promise<string> {
  const response = await request.post("/api/v1/auth/operator/login", { data: { email: operatorEmail, password: operatorPassword } });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).access_token as string;
}

// Creates a fresh clinical parent document + one child chunk whose
// `content_markdown` is a unique string this test can later search for
// with a near-exact-match embedding (same trick v2.spec.ts's Q&A
// round-trip test already relies on).
async function createClinicalFixture(request: APIRequestContext, token: string): Promise<{ documentContent: string; chunkContent: string }> {
  const suffix = randomUUID().slice(0, 8);
  const documentContent = `Conteudo completo do documento-pai de teste ${suffix}, nao deve aparecer antes do clique em Trazer documento.`;
  const chunkContent = `Trecho filho encontrado pela busca de teste ${suffix}.`;
  const headers = { Authorization: `Bearer ${token}` };
  const document = await request.post("/api/v1/operator/knowledge/clinical-documents", { headers, data: { title: `Documento fixture 009 ${suffix}`, content_markdown: documentContent } });
  expect(document.ok()).toBeTruthy();
  const documentId = (await document.json()).document_id as string;
  const chunk = await request.post(`/api/v1/operator/knowledge/clinical-documents/${documentId}/chunks`, { headers, data: { ordinal: 1, heading: "Fixture", content_markdown: chunkContent } });
  expect(chunk.ok()).toBeTruthy();
  return { documentContent, chunkContent };
}

async function createQAFixture(request: APIRequestContext, token: string): Promise<{ question: string; answer: string }> {
  const suffix = randomUUID().slice(0, 8);
  const headers = { Authorization: `Bearer ${token}` };
  const categorySlug = `fixture-009-${suffix}`;
  const category = await request.post("/api/v1/operator/knowledge/categories", { headers, data: { slug: categorySlug, label: `Fixture 009 ${suffix}` } });
  expect(category.ok()).toBeTruthy();
  const question = `Pergunta fixture 009 ${suffix}?`;
  const answer = `Resposta fixture 009 ${suffix}.`;
  const qa = await request.post("/api/v1/operator/knowledge/qa", { headers, data: { category: categorySlug, question, answer_markdown: answer } });
  expect(qa.ok()).toBeTruthy();
  return { question, answer };
}

test.describe("009 acceptance — two-phase clinical evidence selection", () => {
  test.beforeEach(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test.afterAll(() => {
    psql(`TRUNCATE ${conversationTables} CASCADE;`);
  });

  test("manual-search clinical evidence shows only the child excerpt until 'Trazer documento', then 'Selecionar' scrolls to the reply textarea (EV-1, EV-2, EV-5)", async ({ browser, request }) => {
    const token = await apiOperatorToken(request);
    const { documentContent, chunkContent } = await createClinicalFixture(request, token);

    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext({ viewport: { width: 1000, height: 500 } });
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Pergunta para checar evidência clínica em duas fases (009)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();

      await operator.getByLabel("Busca manual").fill(chunkContent);
      await operator.getByRole("button", { name: "Buscar evidências" }).click();
      const card = operator.locator(".evidence-item").filter({ hasText: chunkContent });
      await expect(card).toBeVisible({ timeout: 15_000 });

      // EV-1: only the child excerpt is present; the full parent document
      // must not be in the DOM at all, and there is no "Selecionar" yet.
      await expect(card.getByText(documentContent)).toHaveCount(0);
      await expect(card.getByRole("button", { name: "Selecionar" })).toHaveCount(0);
      await expect(card.getByRole("button", { name: "Trazer documento" })).toBeVisible();

      await operator.evaluate(() => window.scrollTo(0, 400));

      // EV-2/EV-5: revealing the parent shows it (already-fetched, no new
      // request) and scrolls to the top of the page.
      await card.getByRole("button", { name: "Trazer documento" }).click();
      await expect(card.getByText(documentContent)).toBeVisible();
      await expect.poll(() => operator.evaluate(() => window.scrollY)).toBeLessThan(50);

      await operator.evaluate(() => window.scrollTo(0, 0));
      await card.getByRole("button", { name: "Selecionar" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });
      await expect(operator.locator("#operator-reply")).toBeInViewport();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });

  test("automatic-draft evidence is selectable via the same candidate cards, without changing the draft's own suggestion button (EV-3, EV-4)", async ({ browser, request }) => {
    const token = await apiOperatorToken(request);
    const { chunkContent } = await createClinicalFixture(request, token);
    const { question } = await createQAFixture(request, token);

    const customerContext = await browser.newContext();
    const operatorContext = await browser.newContext();
    try {
      const customer = await customerContext.newPage();
      await startCustomerConversation(customer, "Pergunta para checar evidências do rascunho automático (009)");

      const operator = await operatorContext.newPage();
      await login(operator);
      await operator.getByRole("button", { name: /^Aguardando/ }).click();
      // Isolate retrieval to the manual-search text only, matching each
      // fixture's near-exact-match query (plan.md §6).
      await operator.getByRole("button", { name: "Desmarcar conversas" }).click();

      await operator.getByLabel("Busca manual").fill(chunkContent);
      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });
      const clinicalCard = operator.locator(".draft-panel .evidence-item").filter({ hasText: chunkContent });
      await expect(clinicalCard).toBeVisible();
      await expect(clinicalCard.getByRole("button", { name: "Trazer documento" })).toBeVisible();
      await expect(clinicalCard.getByRole("button", { name: "Selecionar" })).toHaveCount(0);
      // EV-4: the whole-draft suggestion action is untouched by EV-3.
      await expect(operator.locator(".draft-panel").getByRole("button", { name: /Usar sugestão|Usar documento completo/ })).toBeVisible();

      await operator.getByLabel("Busca manual").fill(question);
      await operator.getByRole("button", { name: "Gerar rascunho" }).click();
      await expect(operator.getByText(/ANSWER|ABSTAIN/)).toBeVisible({ timeout: 15_000 });
      const qaCard = operator.locator(".draft-panel .evidence-item").filter({ hasText: question });
      await expect(qaCard).toBeVisible();
      await expect(qaCard.getByRole("button", { name: "Selecionar" })).toBeVisible();
    } finally {
      await customerContext.close();
      await operatorContext.close();
    }
  });
});
