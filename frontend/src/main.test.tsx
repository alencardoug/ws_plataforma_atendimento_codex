import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App, CustomerPage, KnowledgeAdminPage, ManualEvidence, MessageBody, OperatorPage } from "./main";

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("V1 routes", () => {
  it("renders the anonymous customer surface", () => {
    render(<MemoryRouter initialEntries={["/customer"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Canal de agendamento e informações" })).toBeInTheDocument();
  });

  it("renders the operator surface", () => {
    render(<MemoryRouter initialEntries={["/operator"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Espaço do operador" })).toBeInTheDocument();
  });

  it("renders untrusted route content as text, never markup", () => {
    render(<MemoryRouter initialEntries={["/<img src=x onerror=alert(1)>"]}><App /></MemoryRouter>);
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByRole("heading", { name: "Canal de agendamento e informações" })).toBeInTheDocument();
  });

  it("preserves line breaks in plain-text messages", () => {
    render(<MessageBody body={"Primeira linha\nSegunda linha"} />);
    const message = screen.getByText(/Primeira linha/);

    expect(message.textContent).toBe("Primeira linha\nSegunda linha");
    expect(message).toHaveClass("message-body");
  });

  it("displays the full manual-search evidence without turning it into a draft", () => {
    render(<ManualEvidence evidence={{ retrieval_hit_id: "evidence-1", knowledge_type: "CLINICAL", rank: 1, title: "Documento-pai", section: "Cuidados", content: "Conteúdo completo do documento-pai.", matched_child_excerpt: "Trecho que corresponde à busca." }} />);

    expect(screen.getByText("Documento-pai")).toBeInTheDocument();
    expect(screen.getByText("Conteúdo completo do documento-pai.")).toBeInTheDocument();
    expect(screen.getByText("Trecho que corresponde à busca.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Usar/ })).toBeNull();
  });

  it("offers a single select action per evidence item when onSelect is provided (V2-3)", () => {
    const onSelect = vi.fn();
    render(<ManualEvidence evidence={{ retrieval_hit_id: "evidence-1", knowledge_type: "ADMIN_QA", rank: 1, title: "Pergunta administrativa", content: "Resposta aprovada." }} onSelect={onSelect} />);

    const button = screen.getByRole("button", { name: "Selecionar" });
    fireEvent.click(button);

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("displays the conversation token continuously and copies it on request (V2-2)", async () => {
    sessionStorage.setItem("conversation_id", "conv-1");
    sessionStorage.setItem("conversation_token", "SUB3B4GC");
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "conv-1", status: "WAITING", messages: [] }),
      }),
    );

    render(<MemoryRouter initialEntries={["/customer"]}><CustomerPage /></MemoryRouter>);

    expect(await screen.findByText("SUB3B4GC")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /mostrar|revelar/i })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Copiar" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("SUB3B4GC"));
    expect(await screen.findByRole("button", { name: "Copiado!" })).toBeInTheDocument();
  });

  it("defaults message selection to the trailing customer run and lets the operator clear it (V2-4)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    const conversationDetail = {
      id: "conv-1",
      status: "ACTIVE",
      effective_mode: "N2",
      messages: [
        { id: "op-1", author_type: "OPERATOR", body: "Olá, como posso ajudar?" },
        { id: "cust-1", author_type: "CUSTOMER", body: "Tenho uma dúvida" },
        { id: "cust-2", author_type: "CUSTOMER", body: "sobre horários" },
        { id: "cust-3", author_type: "CUSTOMER", body: "de sábado" },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) {
          return { ok: true, json: async () => [{ id: "conv-1", status: "ACTIVE", effective_mode: "N2" }] };
        }
        if (url.endsWith("/operator/runtime-config")) {
          return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        }
        if (url.endsWith("/operator/conversations/conv-1")) {
          return { ok: true, json: async () => conversationDetail };
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);

    fireEvent.click(await screen.findByRole("button", { name: /Em atendimento/ }));

    const checkboxes = await screen.findAllByRole("checkbox") as HTMLInputElement[];
    expect(checkboxes).toHaveLength(4);
    expect(checkboxes.map((box) => box.checked)).toEqual([false, true, true, true]);

    fireEvent.click(screen.getByRole("button", { name: "Desmarcar conversas" }));
    await waitFor(() => expect(checkboxes.every((box) => !box.checked)).toBe(true));
    expect(screen.getByRole("button", { name: "Gerar rascunho" })).toBeDisabled();

    fireEvent.click(checkboxes[1]);
    expect(screen.getByRole("button", { name: "Gerar rascunho" })).not.toBeDisabled();
    expect(screen.queryByRole("button", { name: "Regenerar" })).toBeNull();
  });

  it("shows a live typing indicator and surfaces an automatically-generated draft (V2-7)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    const conversationDetail = {
      id: "conv-1",
      status: "ACTIVE",
      effective_mode: "N2",
      is_customer_typing: true,
      messages: [{ id: "cust-1", author_type: "CUSTOMER", body: "Olá" }],
      latest_generation: { id: "gen-1", status: "ANSWER", draft_text: "Resposta automática sintética.", evidence: [], trigger: "AUTOMATIC" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) {
          return { ok: true, json: async () => [{ id: "conv-1", status: "ACTIVE", effective_mode: "N2" }] };
        }
        if (url.endsWith("/operator/runtime-config")) {
          return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        }
        if (url.endsWith("/operator/conversations/conv-1")) {
          return { ok: true, json: async () => conversationDetail };
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Em atendimento/ }));

    expect(await screen.findByText("Cliente está digitando…")).toBeInTheDocument();
    expect(await screen.findByText("Resposta automática sintética.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Usar sugestão" })).toBeInTheDocument();
  });

  it("lists knowledge records and creates a new Q&A entry (V2-8)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    let qaItems = [{ qa_id: "qa-1", category: "geral", question: "Pergunta existente", answer_markdown: "Resposta existente.", is_active: true, dynamic_binding: null }];
    const createdQa = { qa_id: "qa-2", category: "geral", question: "Nova pergunta", answer_markdown: "Nova resposta.", is_active: true, dynamic_binding: null };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/operator/knowledge/qa") && (!init || init.method === undefined)) {
          return { ok: true, json: async () => qaItems };
        }
        if (url.endsWith("/operator/knowledge/qa") && init?.method === "POST") {
          qaItems = [...qaItems, createdQa];
          return { ok: true, json: async () => createdQa };
        }
        if (url.endsWith("/operator/knowledge/clinical-documents") && (!init || init.method === undefined)) {
          return { ok: true, json: async () => [] };
        }
        if (url.endsWith("/operator/knowledge/categories") && (!init || init.method === undefined)) {
          return { ok: true, json: async () => [{ slug: "geral", label: "Geral", is_active: true }] };
        }
        if (url.endsWith("/operator/knowledge/dynamic-tables") && (!init || init.method === undefined)) {
          return { ok: true, json: async () => [] };
        }
        throw new Error(`Unexpected fetch: ${url} ${init?.method ?? "GET"}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator/knowledge"]}><KnowledgeAdminPage /></MemoryRouter>);

    expect(await screen.findByText("Pergunta existente")).toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText("Categoria"), { target: { value: "geral" } });
    fireEvent.change(screen.getByLabelText("Pergunta"), { target: { value: "Nova pergunta" } });
    fireEvent.change(screen.getByLabelText("Resposta"), { target: { value: "Nova resposta." } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar pergunta e resposta" }));

    expect(await screen.findByText("Nova pergunta")).toBeInTheDocument();
  });

  it("shows empty states instead of a bare blank panel (V2-1)", async () => {
    const conversation = { id: "conv-1", status: "ACTIVE", messages: [] };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/public/conversations") && init?.method === "POST") {
          return { ok: true, json: async () => ({ conversation, access_token: "SUB3B4GC" }) };
        }
        if (url.endsWith("/public/conversations/conv-1")) {
          return { ok: true, json: async () => conversation };
        }
        throw new Error(`Unexpected fetch: ${url} ${init?.method ?? "GET"}`);
      }),
    );
    render(<MemoryRouter initialEntries={["/customer"]}><CustomerPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Iniciar conversa" }));

    expect(await screen.findByText("Nenhuma mensagem ainda. Escreva abaixo para começar.")).toBeInTheDocument();
  });

  it("shows an empty queue state when there are no conversations (V2-1)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) return { ok: true, json: async () => [] };
        if (url.endsWith("/operator/runtime-config")) return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);

    expect(await screen.findByText("Nenhuma conversa no momento.")).toBeInTheDocument();
  });

  it("never offers a control the backend would reject for a closed or N1 conversation (V2-1/T104)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    const closedConversation = {
      id: "conv-closed",
      status: "CLOSED",
      effective_mode: "N2",
      messages: [{ id: "cust-1", author_type: "CUSTOMER", body: "Olá" }],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) {
          return { ok: true, json: async () => [{ id: "conv-closed", status: "CLOSED", effective_mode: "N2" }] };
        }
        if (url.endsWith("/operator/runtime-config")) {
          return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        }
        if (url.endsWith("/operator/conversations/conv-closed")) {
          return { ok: true, json: async () => closedConversation };
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Encerrada/ }));

    expect(await screen.findByText("Esta conversa está encerrada.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enviar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Gerar rascunho" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Assumir controle" })).toBeNull();
  });

  it("omits the evidence-selection action in N1-assistive search, since the backend requires N2 (V2-1/T104)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    const n1Conversation = {
      id: "conv-n1",
      status: "ACTIVE",
      effective_mode: "N1",
      messages: [{ id: "cust-1", author_type: "CUSTOMER", body: "Olá" }],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) {
          return { ok: true, json: async () => [{ id: "conv-n1", status: "ACTIVE", effective_mode: "N1" }] };
        }
        if (url.endsWith("/operator/runtime-config")) {
          return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        }
        if (url.endsWith("/operator/conversations/conv-n1")) {
          return { ok: true, json: async () => n1Conversation };
        }
        if (url.endsWith("/operator/knowledge/search") && init?.method === "POST") {
          return { ok: true, json: async () => ({ evidence: [{ retrieval_hit_id: "hit-1", knowledge_type: "ADMIN_QA", rank: 1, title: "Pergunta administrativa", content: "Resposta aprovada." }] }) };
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Em atendimento/ }));

    fireEvent.change(await screen.findByLabelText("Busca manual"), { target: { value: "horário" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar evidências" }));

    expect(await screen.findByText("Pergunta administrativa")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Selecionar" })).toBeNull();
  });

  it("requires confirmation before closing the customer's own conversation, and cancelling sends no request (V3-11)", async () => {
    sessionStorage.setItem("conversation_id", "conv-1");
    sessionStorage.setItem("conversation_token", "SUB3B4GC");
    const closeCalls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/public/conversations/conv-1") && (!init || init.method === undefined)) {
          return { ok: true, json: async () => ({ id: "conv-1", status: "ACTIVE", messages: [] }) };
        }
        if (url.endsWith("/public/conversations/conv-1") && init?.method === "POST") {
          closeCalls.push(url);
          return { ok: true, json: async () => ({ id: "conv-1", status: "CLOSED", messages: [] }) };
        }
        throw new Error(`Unexpected fetch: ${url} ${init?.method ?? "GET"}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/customer"]}><CustomerPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Encerrar conversa" }));

    expect(await screen.findByText("Deseja encerrar a conversa?")).toBeInTheDocument();
    expect(closeCalls).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Retornar e continuar conversa" }));
    expect(closeCalls).toHaveLength(0);
    expect(await screen.findByRole("button", { name: "Encerrar conversa" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Encerrar conversa" }));
    fireEvent.click(await screen.findByRole("button", { name: "Encerrar conversa" }));
    await waitFor(() => expect(closeCalls).toHaveLength(1));
  });

  it("requires confirmation before closing on the operator surface too (V3-11)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    const conversationDetail = { id: "conv-1", status: "ACTIVE", effective_mode: "N2", messages: [] };
    const closeCalls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) {
          return { ok: true, json: async () => [{ id: "conv-1", status: "ACTIVE", effective_mode: "N2" }] };
        }
        if (url.endsWith("/operator/runtime-config")) {
          return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        }
        if (url.endsWith("/operator/conversations/conv-1")) {
          return { ok: true, json: async () => conversationDetail };
        }
        if (url.endsWith("/operator/conversations/conv-1/close") && init?.method === "POST") {
          closeCalls.push(url);
          return { ok: true, json: async () => ({ id: "conv-1", status: "CLOSED" }) };
        }
        throw new Error(`Unexpected fetch: ${url} ${init?.method ?? "GET"}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Em atendimento/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Encerrar conversa" }));

    expect(await screen.findByText("Deseja encerrar a conversa?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retornar e continuar conversa" }));
    expect(closeCalls).toHaveLength(0);
    expect(await screen.findByRole("button", { name: "Encerrar conversa" })).toBeInTheDocument();
  });

  it("ensures appointment availability from the queue sidebar with no conversation selected (AA-9, T061)", async () => {
    sessionStorage.setItem("operator_token", "operator-token");
    let ensureCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/operator/conversations?scope=all")) return { ok: true, json: async () => [] };
        if (url.endsWith("/operator/runtime-config")) return { ok: true, json: async () => ({ n1_assistive_search_enabled: true }) };
        if (url.endsWith("/operator/scheduling/ensure-availability") && init?.method === "POST") {
          ensureCalls += 1;
          return {
            ok: true,
            json: async () =>
              ensureCalls === 1
                ? { created_d1: 1, created_d7: 3, already_sufficient: false, message: "Criadas 4 vaga(s): 1 em D+1, 3 em D+7." }
                : { created_d1: 0, created_d7: 0, already_sufficient: true, message: "Já tem 4 vagas disponíveis." },
          };
        }
        throw new Error(`Unexpected fetch: ${url} ${init?.method ?? "GET"}`);
      }),
    );

    render(<MemoryRouter initialEntries={["/operator"]}><OperatorPage /></MemoryRouter>);

    const button = await screen.findByRole("button", { name: "Garantir disponibilidade (D+1/D+7)" });
    fireEvent.click(button);
    expect(await screen.findByText("Criadas 4 vaga(s): 1 em D+1, 3 em D+7.")).toBeInTheDocument();

    fireEvent.click(button);
    expect(await screen.findByText("Já tem 4 vagas disponíveis.")).toBeInTheDocument();
    expect(ensureCalls).toBe(2);
  });
});
