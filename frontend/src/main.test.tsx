import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./main";

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
});
