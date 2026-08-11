import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App, ManualEvidence, MessageBody } from "./main";

describe("V1 routes", () => {
  it("renders the anonymous customer surface", () => {
    render(<MemoryRouter initialEntries={["/customer"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Atendimento" })).toBeInTheDocument();
  });

  it("renders the operator surface", () => {
    render(<MemoryRouter initialEntries={["/operator"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Espaço do operador" })).toBeInTheDocument();
  });

  it("renders untrusted route content as text, never markup", () => {
    render(<MemoryRouter initialEntries={["/<img src=x onerror=alert(1)>"]}><App /></MemoryRouter>);
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByRole("heading", { name: "Atendimento" })).toBeInTheDocument();
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
});
