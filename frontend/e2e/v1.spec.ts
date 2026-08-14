import { expect, test, type BrowserContext, type Page } from "@playwright/test";

function requiredEnvironment(name: "E2E_OPERATOR_EMAIL" | "E2E_OPERATOR_PASSWORD"): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser acceptance`);
  return value;
}

const operatorEmail = requiredEnvironment("E2E_OPERATOR_EMAIL");
const operatorPassword = requiredEnvironment("E2E_OPERATOR_PASSWORD");

test("six independent customers, capacity, hidden N2 draft, explicit send and take-over", async ({ browser }) => {
  test.skip(process.env.E2E_MATURITY_MODE === "N1", "N2 acceptance scenario");
  const contexts: BrowserContext[] = [];
  const customerPages: Page[] = [];
  const sessions: Array<{ id: string; token: string }> = [];

  try {
    for (let index = 0; index < 6; index += 1) {
      const context = await browser.newContext();
      contexts.push(context);
      const page = await context.newPage();
      customerPages.push(page);
      await page.goto("/customer");
      await page.getByRole("button", { name: "Iniciar conversa" }).click();
      await expect(page.getByText("Aguardando", { exact: true })).toBeVisible();
      const session = await page.evaluate(() => ({
        id: sessionStorage.getItem("conversation_id") || "",
        token: sessionStorage.getItem("conversation_token") || "",
      }));
      expect(session.id).not.toBe("");
      expect(session.token).not.toBe("");
      sessions.push(session);
      await page.getByLabel("Mensagem").fill(`Mensagem sintética do cliente ${index + 1}`);
      await page.getByRole("button", { name: "Enviar" }).click();
      await expect(page.getByText(`Mensagem sintética do cliente ${index + 1}`)).toBeVisible();
    }

    expect(new Set(sessions.map((item) => item.id)).size).toBe(6);
    expect(new Set(sessions.map((item) => item.token)).size).toBe(6);

    const operatorContext = await browser.newContext();
    contexts.push(operatorContext);
    const operator = await operatorContext.newPage();
    await operator.goto("/operator");
    await operator.getByLabel("E-mail").fill(operatorEmail);
    await operator.getByLabel("Senha").fill(operatorPassword);
    await operator.getByRole("button", { name: "Entrar" }).click();
    await expect(operator.getByRole("heading", { name: "Fila" })).toBeVisible();
    await expect(operator.getByRole("button", { name: /^Aguardando/ })).toHaveCount(6);

    for (let index = 0; index < 4; index += 1) {
      await operator.getByRole("button", { name: /^Aguardando/ }).first().click();
      await expect(operator.getByRole("button", { name: /^Em atendimento/ })).toHaveCount(index + 1);
    }
    await expect(operator.getByRole("button", { name: /^Aguardando/ })).toHaveCount(2);
    await operator.getByRole("button", { name: /^Aguardando/ }).first().click();
    await expect(operator.getByRole("alert")).toContainText("capacity", { ignoreCase: true });
    await expect(operator.getByRole("button", { name: /^Em atendimento/ })).toHaveCount(4);
    await expect(operator.getByRole("button", { name: /^Aguardando/ })).toHaveCount(2);

    const firstActiveButton = operator.getByRole("button", { name: /^Em atendimento/ }).first();
    const firstActiveLabel = await firstActiveButton.textContent();
    const selectedSessionIndex = sessions.findIndex((session) => firstActiveLabel?.includes(session.id.slice(0, 8)));
    expect(selectedSessionIndex).toBeGreaterThanOrEqual(0);
    await firstActiveButton.click();
    await operator.getByRole("button", { name: "Gerar rascunho" }).click();
    await expect(operator.getByText(/ANSWER|ABSTAIN/, { exact: true })).toBeVisible();
    for (const page of customerPages) await expect(page.getByText(/ANSWER|ABSTAIN/, { exact: true })).toHaveCount(0);
    await operator.getByRole("button", { name: /Usar (sugestão|documento completo)/ }).click();
    const reply = operator.locator("main.workspace > section textarea");
    const multilineReply = `${await reply.inputValue()}\n\nComplemento revisado pelo operador.`;
    await reply.fill(multilineReply);
    await operator.locator("main.workspace > section").getByRole("button", { name: "Enviar" }).click();
    await expect(operator.getByText("Complemento revisado pelo operador.")).toBeVisible();
    await expect(customerPages[selectedSessionIndex].getByText("Complemento revisado pelo operador.")).toBeVisible({ timeout: 10_000 });
    const operatorReply = operator.locator("main.workspace > section article .message-body").last();
    const customerReply = customerPages[selectedSessionIndex].locator("article.operator .message-body").last();
    await expect(operatorReply).toHaveCSS("white-space", "pre-wrap");
    await expect(customerReply).toHaveCSS("white-space", "pre-wrap");
    expect(await operatorReply.textContent()).toBe(multilineReply);
    expect(await customerReply.textContent()).toBe(multilineReply);

    await operator.getByRole("button", { name: /^Em atendimento/ }).nth(1).click();
    await operator.getByRole("button", { name: "Assumir controle" }).click();
    await expect(operator.getByRole("heading", { name: "Conversa N1" })).toBeVisible();
    await expect(operator.getByRole("button", { name: "Gerar rascunho" })).toHaveCount(0);
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});

test("N1 hides AI controls and preserves manual service when search is disabled", async ({ browser }) => {
  test.skip(process.env.E2E_MATURITY_MODE !== "N1", "Run with the N1 acceptance backend");
  const customerContext = await browser.newContext();
  const operatorContext = await browser.newContext();
  try {
    const customer = await customerContext.newPage();
    await customer.goto("/customer");
    await customer.getByRole("button", { name: "Iniciar conversa" }).click();
    await customer.getByLabel("Mensagem").fill("Mensagem manual N1 do navegador");
    await customer.getByRole("button", { name: "Enviar" }).click();

    const operator = await operatorContext.newPage();
    await operator.goto("/operator");
    await operator.getByLabel("E-mail").fill(operatorEmail);
    await operator.getByLabel("Senha").fill(operatorPassword);
    await operator.getByRole("button", { name: "Entrar" }).click();
    await operator.getByRole("button", { name: /^Aguardando N1/ }).click();
    await expect(operator.getByRole("heading", { name: "Conversa N1" })).toBeVisible();
    await expect(operator.getByRole("button", { name: "Gerar rascunho" })).toHaveCount(0);
    await expect(operator.getByText("Busca assistiva N1 desabilitada.")).toBeVisible();
    const reply = operator.locator("main.workspace > section textarea");
    await reply.fill("Resposta manual N1 pelo navegador.");
    await operator.locator("main.workspace > section").getByRole("button", { name: "Enviar" }).click();
    await expect(customer.getByText("Resposta manual N1 pelo navegador.")).toBeVisible({ timeout: 10_000 });
  } finally {
    await customerContext.close();
    await operatorContext.close();
  }
});
