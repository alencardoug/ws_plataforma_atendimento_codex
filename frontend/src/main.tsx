import React, { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import "./styles.css";

const API = "/api/v1";

type ConversationStatus = "WAITING" | "ACTIVE" | "CLOSED";
type MaturityMode = "N1" | "N2";

interface Citation {
  title: string;
  section?: string | null;
  url?: string | null;
}

interface Message {
  id: string;
  author_type: "CUSTOMER" | "OPERATOR";
  body: string;
  citations?: Citation[];
  // Operator-only (V3-1): absent on CustomerPage's shared projection —
  // an AI generation stays an internal artifact, never customer-visible.
  source_generation_id?: string | null;
  // Operator-only (V3-1×V3-8): present only when this message differs from
  // the draft that produced it (an "edit"), pre-filling the "transformar em
  // Q&A" flow.
  qa_transform?: { question: string; answer: string; category_slug: string | null } | null;
}

interface CustomerConversation {
  id: string;
  status: ConversationStatus;
  messages: Message[];
}

interface OperatorConversation extends CustomerConversation {
  effective_mode: MaturityMode;
  is_customer_typing?: boolean;
  latest_generation?: Draft | null;
}

interface ConversationSummary {
  id: string;
  status: ConversationStatus;
  effective_mode: MaturityMode;
}

export interface Evidence {
  retrieval_hit_id: string;
  knowledge_type: "ADMIN_QA" | "CLINICAL";
  rank: number;
  title: string;
  section?: string | null;
  content: string;
  matched_child_excerpt?: string | null;
}

interface RequestMessage {
  role: string;
  content: string;
}

interface Draft {
  id: string;
  status: "ANSWER" | "ABSTAIN";
  draft_text: string;
  evidence: Evidence[];
  trigger?: "AUTOMATIC" | "MANUAL_DRAFT" | "MANUAL_EVIDENCE";
  request_messages?: RequestMessage[] | null;
}

function defaultMessageSelection(messages: Message[]): Set<string> {
  const ids = new Set<string>();
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].author_type !== "CUSTOMER") break;
    ids.add(messages[i].id);
  }
  return ids;
}

interface RuntimeConfig {
  n1_assistive_search_enabled: boolean;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Erro inesperado";
}

async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  const body: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof body === "object" && body !== null && "message" in body
      ? String(body.message)
      : `Erro ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

export function MessageBody({ body }: { body: string }) {
  return <p className="message-body">{body}</p>;
}

const STATUS_LABEL: Record<ConversationStatus, string> = { WAITING: "Aguardando", ACTIVE: "Em atendimento", CLOSED: "Encerrada" };

function StatusBadge({ status }: { status: ConversationStatus }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{STATUS_LABEL[status]}</span>;
}

export function ManualEvidence({ evidence, onSelect }: { evidence: Evidence; onSelect?: () => void }) {
  return <article className="evidence-item"><strong>{evidence.title}</strong>{evidence.section && <small>Seção: {evidence.section}</small>}<MessageBody body={evidence.content} />{evidence.matched_child_excerpt && <><small>Trecho encontrado</small><MessageBody body={evidence.matched_child_excerpt} /></>}{onSelect && <button type="button" onClick={onSelect}>Selecionar</button>}</article>;
}

// Operator-only transparency pop-up: shows the exact `messages` array sent
// to the generation model for the currently displayed draft. Never shown on
// CustomerPage. Sourced from the draft response already held in local
// state — not persisted server-side, so it reflects only the draft that is
// currently on screen (plan note in ai/router.py's generation_dict).
export function RequestDebugDialog({ messages, onClose }: { messages: RequestMessage[]; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return <dialog ref={ref} className="debug-dialog" onClose={onClose} aria-label="Requisição enviada ao modelo">
    <h2>Requisição enviada ao modelo</h2>
    <p className="is-loading">Conteúdo exato transmitido à API do provedor de IA para gerar este rascunho — visível somente ao operador.</p>
    {messages.map((message, index) => <section key={index} className="debug-message">
      <strong>{message.role}</strong>
      <pre>{message.content}</pre>
    </section>)}
    <button type="button" className="btn-secondary" onClick={() => ref.current?.close()}>Fechar</button>
  </dialog>;
}

export function CustomerPage() {
  const [id, setId] = useState(() => sessionStorage.getItem("conversation_id") || "");
  const [token, setToken] = useState(() => sessionStorage.getItem("conversation_token") || "");
  const [conversation, setConversation] = useState<CustomerConversation | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [tokenCopied, setTokenCopied] = useState(false);

  const copyToken = async () => {
    try {
      await navigator.clipboard.writeText(token);
      setTokenCopied(true);
      window.setTimeout(() => setTokenCopied(false), 2000);
    } catch {
      setError("Não foi possível copiar o código automaticamente. Copie manualmente.");
    }
  };

  const refresh = useCallback(async () => {
    if (id && token) setConversation(await api<CustomerConversation>(`/public/conversations/${id}`, {}, token));
  }, [id, token]);

  // V2-7: typing-activity heartbeat, sent roughly every 2.5s while the
  // message box has non-empty content — extends the server-side 8-second
  // automatic-draft debounce window. A ref avoids a stale `text` closure
  // inside the interval without resetting the interval on every keystroke.
  const textRef = useRef(text);
  useEffect(() => {
    textRef.current = text;
  }, [text]);
  useEffect(() => {
    if (!id || !token) return;
    const heartbeat = window.setInterval(() => {
      if (textRef.current.trim().length > 0) {
        void api(`/public/conversations/${id}/typing`, { method: "POST" }, token).catch(() => undefined);
      }
    }, 2500);
    return () => window.clearInterval(heartbeat);
  }, [id, token]);

  useEffect(() => {
    const initial = window.setTimeout(() => void refresh().catch((caught) => setError(errorMessage(caught))), 0);
    const timer = window.setInterval(() => void refresh().catch(() => undefined), 2000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [refresh]);

  const start = async () => {
    const data = await api<{ conversation: CustomerConversation; access_token: string }>("/public/conversations", { method: "POST" });
    sessionStorage.setItem("conversation_id", data.conversation.id);
    sessionStorage.setItem("conversation_token", data.access_token);
    setId(data.conversation.id);
    setToken(data.access_token);
    setConversation(data.conversation);
  };

  const send = async (event: FormEvent) => {
    event.preventDefault();
    await api<Message>(`/public/conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ body: text }) }, token);
    setText("");
    await refresh();
  };

  const close = async () => {
    const closed = await api<CustomerConversation>(`/public/conversations/${id}`, { method: "POST" }, token);
    setConversation(closed);
    sessionStorage.removeItem("conversation_id");
    sessionStorage.removeItem("conversation_token");
  };

  if (!id) {
    return <main>
      <div className="card stack">
        <h1>Atendimento</h1>
        <p>Converse anonimamente com nossa equipe. Um código de acompanhamento será exibido assim que a conversa iniciar.</p>
        <button onClick={() => void start().catch((caught) => setError(errorMessage(caught)))}>Iniciar conversa</button>
        {error && <p role="alert">{error}</p>}
      </div>
    </main>;
  }

  return <main>
    <div className="card stack">
      <div className="stack" style={{ gap: "var(--space-3)" }}>
        <h1>Atendimento</h1>
        {conversation ? <StatusBadge status={conversation.status} /> : <p className="is-loading">Carregando conversa…</p>}
        <p className="conversation-token" aria-label="Código desta conversa">
          Código da conversa: <strong>{token}</strong>
          <button type="button" className="btn-secondary" onClick={() => void copyToken()}>{tokenCopied ? "Copiado!" : "Copiar"}</button>
        </p>
      </div>
      <section className="messages" aria-live="polite" aria-label="Mensagens da conversa">
        {conversation && conversation.messages.length === 0 && <p className="empty-state">Nenhuma mensagem ainda. Escreva abaixo para começar.</p>}
        {conversation?.messages.map((message) => <article key={message.id} className={`message ${message.author_type.toLowerCase()}`}>
          <span className="message-author">{message.author_type === "CUSTOMER" ? "Você" : "Atendente"}</span>
          <MessageBody body={message.body} />
          {message.citations?.map((citation) => <small key={`${citation.title}-${citation.section || ""}`} className="message-citation">Fonte: {citation.title}{citation.section ? ` — ${citation.section}` : ""}</small>)}
        </article>)}
      </section>
      <form onSubmit={(event) => void send(event).catch((caught) => setError(errorMessage(caught)))}>
        <label htmlFor="customer-message">Mensagem<textarea id="customer-message" value={text} onChange={(event) => setText(event.target.value)} required disabled={conversation?.status === "CLOSED"} /></label>
        <button disabled={conversation?.status === "CLOSED"}>Enviar</button>
      </form>
      {conversation?.status !== "CLOSED" && <button type="button" className="btn-ghost" onClick={() => void close().catch((caught) => setError(errorMessage(caught)))}>Encerrar conversa</button>}
      {error && <p role="alert">{error}</p>}
    </div>
  </main>;
}

export function OperatorPage() {
  const navigate = useNavigate();
  const [token, setToken] = useState(() => sessionStorage.getItem("operator_token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [selected, setSelected] = useState<OperatorConversation | null>(null);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [instructionText, setInstructionText] = useState("");
  const [searchEvidence, setSearchEvidence] = useState<Evidence[]>([]);
  const [selectedMessageIds, setSelectedMessageIds] = useState<Set<string>>(new Set());
  const [showRequestDebug, setShowRequestDebug] = useState(false);
  const [markedIncorrectIds, setMarkedIncorrectIds] = useState<Set<string>>(new Set());
  const [escalatedIds, setEscalatedIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setItems(await api<ConversationSummary[]>("/operator/conversations?scope=all", {}, token));
    setRuntimeConfig(await api<RuntimeConfig>("/operator/runtime-config", {}, token));
  }, [token]);

  const selectedId = selected?.id;
  // V2-7: an AUTOMATIC-trigger draft has no direct API response to this
  // browser — it only appears via polling's latest_generation field. Track
  // the last generation id we've already surfaced into `draft` (in this ref,
  // read/written directly rather than via a memoized helper, to keep
  // refreshSelected's own dependency list simple) so a still-current-but-
  // already-handled (sent/dismissed) generation doesn't silently reappear.
  const lastGenerationIdRef = useRef<string | null>(null);
  const refreshSelected = useCallback(async () => {
    if (!selectedId) return;
    const data = await api<OperatorConversation>(`/operator/conversations/${selectedId}`, {}, token);
    setSelected(data);
    if (data.latest_generation && data.latest_generation.id !== lastGenerationIdRef.current) {
      lastGenerationIdRef.current = data.latest_generation.id;
      setDraft(data.latest_generation);
    }
  }, [selectedId, token]);

  const toggleMessageSelection = (messageId: string) => {
    setSelectedMessageIds((current) => {
      const next = new Set(current);
      if (next.has(messageId)) next.delete(messageId);
      else next.add(messageId);
      return next;
    });
  };

  useEffect(() => {
    if (!token) return;
    const initial = window.setTimeout(() => void load().catch((caught) => setError(errorMessage(caught))), 0);
    const timer = window.setInterval(() => void load().catch(() => undefined), 2000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [load, token]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setInterval(() => void refreshSelected().catch((caught) => setError(errorMessage(caught))), 2000);
    return () => window.clearInterval(timer);
  }, [refreshSelected, selectedId]);

  const login = async (event: FormEvent) => {
    event.preventDefault();
    const data = await api<{ access_token: string }>("/auth/operator/login", { method: "POST", body: JSON.stringify({ email, password }) });
    sessionStorage.setItem("operator_token", data.access_token);
    setToken(data.access_token);
  };
  // Default message selection (trailing consecutive customer messages) is
  // set only when a conversation is freshly opened, not on every poll
  // refresh — otherwise polling would keep discarding the operator's own
  // edits (V2-4).
  const open = async (conversationId: string) => {
    const data = await api<OperatorConversation>(`/operator/conversations/${conversationId}`, {}, token);
    setSelected(data);
    setSelectedMessageIds(defaultMessageSelection(data.messages));
    lastGenerationIdRef.current = data.latest_generation?.id ?? null;
    setDraft(data.latest_generation ?? null);
    setShowRequestDebug(false);
    setMarkedIncorrectIds(new Set());
    setEscalatedIds(new Set());
  };
  const claim = async (conversationId: string) => {
    await api<OperatorConversation>(`/operator/conversations/${conversationId}/claim`, { method: "POST" }, token);
    await load();
    await open(conversationId);
  };
  // V3-1: reachable from any message in the rendered history, not only the
  // latest draft. Idempotent server-side; the local Set only drives this
  // session's button feedback, reset on conversation switch (open()).
  const markIncorrect = async (generationId: string) => {
    if (!selected) return;
    await api(`/operator/conversations/${selected.id}/generations/${generationId}/mark-incorrect`, { method: "POST" }, token);
    setMarkedIncorrectIds((current) => new Set(current).add(generationId));
  };
  const escalateGeneration = async (generationId: string) => {
    if (!selected) return;
    await api(`/operator/conversations/${selected.id}/generations/${generationId}/escalate`, { method: "POST" }, token);
    setEscalatedIds((current) => new Set(current).add(generationId));
  };
  // V3-1×V3-8: no new endpoint — hands the server-computed pre-fill to
  // KnowledgeAdminPage's existing create-entry form via sessionStorage, a
  // one-time handoff read (and cleared) on that page's mount.
  const transformToQA = (prefill: { question: string; answer: string; category_slug: string | null }) => {
    sessionStorage.setItem("qa_transform_prefill", JSON.stringify(prefill));
    navigate("/operator/knowledge");
  };
  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    await api<Message>(`/operator/conversations/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ body: text, source_generation_id: draft?.id || null, citation_retrieval_hit_ids: [] }) }, token);
    setText("");
    setDraft(null);
    await open(selected.id);
  };
  // V3-2: sends the current draft byte-for-byte unmodified. No dedicated
  // backend endpoint — the same send path already tags this `approve`
  // (ai.draft_accepted) since body === draft_text (plan.md §1/§5).
  const quickApprove = async () => {
    if (!selected || !draft) return;
    await api<Message>(`/operator/conversations/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ body: draft.draft_text, source_generation_id: draft.id, citation_retrieval_hit_ids: [] }) }, token);
    setText("");
    setDraft(null);
    await open(selected.id);
  };
  const canGenerate = selectedMessageIds.size > 0 || searchQuery.trim().length > 0;
  const generate = async () => {
    if (!selected || !canGenerate) return;
    setDraft(await api<Draft>(`/operator/conversations/${selected.id}/drafts`, {
      method: "POST",
      body: JSON.stringify({ selected_message_ids: [...selectedMessageIds], manual_search_text: searchQuery, instruction_text: instructionText }),
    }, token));
  };
  const clearMessageSelection = () => setSelectedMessageIds(new Set());
  const takeOver = async () => {
    if (!selected) return;
    await api<OperatorConversation>(`/operator/conversations/${selected.id}/take-over`, { method: "POST" }, token);
    await open(selected.id);
  };
  const closeConversation = async () => {
    if (!selected) return;
    await api<ConversationSummary>(`/operator/conversations/${selected.id}/close`, { method: "POST" }, token);
    setSelected(null);
    setDraft(null);
    setSearchEvidence([]);
    await load();
  };
  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    const result = await api<{ evidence: Evidence[] }>("/operator/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ query: searchQuery, conversation_id: selected.id }),
    }, token);
    setSearchEvidence(result.evidence);
  };
  const selectEvidence = async (retrievalHitId: string) => {
    if (!selected) return;
    setDraft(await api<Draft>(`/operator/knowledge/evidence/${retrievalHitId}/select`, {
      method: "POST",
      body: JSON.stringify({ conversation_id: selected.id }),
    }, token));
  };

  if (!token) {
    return <main>
      <div className="card stack">
        <h1>Espaço do operador</h1>
        <form onSubmit={(event) => void login(event).catch((caught) => setError(errorMessage(caught)))}>
          <label htmlFor="operator-email">E-mail<input id="operator-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label htmlFor="operator-password">Senha<input id="operator-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <button>Entrar</button>
        </form>
        {error && <p role="alert">{error}</p>}
      </div>
    </main>;
  }

  const aiEligible = selected?.status === "ACTIVE" && selected.effective_mode === "N2";
  const searchAvailable = selected?.effective_mode === "N2" || runtimeConfig?.n1_assistive_search_enabled;
  const useDraftLabel = draft?.evidence.find((item) => item.rank === 1)?.knowledge_type === "CLINICAL" ? "Usar documento completo" : "Usar sugestão";
  return <main className="workspace">
    <aside className="card" aria-label="Fila de conversas">
      <h2>Fila</h2>
      {items.length === 0 && <p className="empty-state">Nenhuma conversa no momento.</p>}
      {items.map((conversation) => <button
        key={conversation.id}
        type="button"
        className="queue-item"
        aria-current={conversation.id === selectedId ? "true" : undefined}
        onClick={() => void (conversation.status === "WAITING" ? claim(conversation.id) : open(conversation.id)).catch((caught) => setError(errorMessage(caught)))}
      >
        <StatusBadge status={conversation.status} />{" "}
        <span>{conversation.effective_mode} · {conversation.id.slice(0, 8)}</span>
      </button>)}
    </aside>
    <section className="card">
      {selected ? <>
        <h1>Conversa {selected.effective_mode}</h1>
        {selected.is_customer_typing && <p aria-live="polite" className="typing-indicator">Cliente está digitando…</p>}
        <button type="button" className="btn-ghost" onClick={clearMessageSelection}>Desmarcar conversas</button>
        <div className="messages">
          {selected.messages.length === 0 && <p className="empty-state">Sem mensagens nesta conversa ainda.</p>}
          {selected.messages.map((message) => <article key={message.id} className={`message ${message.author_type.toLowerCase()}`}>
            <label className="message-select">
              <input type="checkbox" checked={selectedMessageIds.has(message.id)} onChange={() => toggleMessageSelection(message.id)} aria-label={`Incluir mensagem de ${message.author_type === "CUSTOMER" ? "cliente" : "operador"} no contexto`} />
              <span className="message-author">{message.author_type === "CUSTOMER" ? "Cliente" : "Operador"}</span>
            </label>
            <MessageBody body={message.body} />
            {message.source_generation_id && <div className="message-taxonomy-actions">
              <button type="button" className="btn-ghost" disabled={markedIncorrectIds.has(message.source_generation_id)} onClick={() => void markIncorrect(message.source_generation_id as string).catch((caught) => setError(errorMessage(caught)))}>{markedIncorrectIds.has(message.source_generation_id) ? "✓ Marcado como incorreto" : "Marcar como incorreto"}</button>
              <button type="button" className="btn-ghost" disabled={escalatedIds.has(message.source_generation_id)} onClick={() => void escalateGeneration(message.source_generation_id as string).catch((caught) => setError(errorMessage(caught)))}>{escalatedIds.has(message.source_generation_id) ? "✓ Sinalizado (lacuna de conteúdo)" : "Sinalizar lacuna de conteúdo"}</button>
              {message.qa_transform && <button type="button" className="btn-ghost" onClick={() => transformToQA(message.qa_transform as NonNullable<Message["qa_transform"]>)}>Transformar em Q&amp;A</button>}
            </div>}
          </article>)}
        </div>
        {selected.status === "ACTIVE" ? <>
          <form onSubmit={(event) => void send(event).catch((caught) => setError(errorMessage(caught)))}>
            <label htmlFor="operator-reply">Resposta<textarea id="operator-reply" value={text} onChange={(event) => setText(event.target.value)} required /></label>
            <button>Enviar</button>
          </form>
          <button type="button" className="btn-ghost" onClick={() => void closeConversation().catch((caught) => setError(errorMessage(caught)))}>Encerrar conversa</button>
        </> : <p className="is-loading">Esta conversa está encerrada.</p>}
      </> : <p className="empty-state">Selecione uma conversa na fila para começar.</p>}
    </section>
    <aside className="card" aria-label="IA e evidências">
      <h2>IA / Evidências</h2>
      {aiEligible && <div className="stack" style={{ gap: "var(--space-2)" }}>
        <label htmlFor="instruction-text">Instrução para regenerar (opcional)<input id="instruction-text" value={instructionText} onChange={(event) => setInstructionText(event.target.value)} placeholder="ex.: seja mais formal" /></label>
        <button disabled={!canGenerate} onClick={() => void generate().catch((caught) => setError(errorMessage(caught)))}>Gerar rascunho</button>
        <button type="button" className="btn-secondary" onClick={() => void takeOver().catch((caught) => setError(errorMessage(caught)))}>Assumir controle</button>
      </div>}
      {selected && searchAvailable && <form onSubmit={(event) => void search(event).catch((caught) => setError(errorMessage(caught)))}>
        <label htmlFor="manual-search">Busca manual<input id="manual-search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} required /></label>
        <button type="submit" className="btn-secondary">Buscar evidências</button>
      </form>}
      {selected?.effective_mode === "N1" && !searchAvailable && <p className="is-loading">Busca assistiva N1 desabilitada.</p>}
      {draft && <div className="draft-panel">
        <span className={`badge badge-${draft.status === "ANSWER" ? "active" : "closed"}`}>{draft.status}</span>
        <MessageBody body={draft.draft_text} />
        <button onClick={() => setText(draft.draft_text)}>{useDraftLabel}</button>
        {draft.status === "ANSWER" && <button type="button" className="btn-secondary" onClick={() => void quickApprove().catch((caught) => setError(errorMessage(caught)))}>Aprovar</button>}
        {draft.request_messages && draft.request_messages.length > 0 && <button type="button" className="btn-ghost" onClick={() => setShowRequestDebug(true)}>Ver requisição enviada</button>}
        {draft.evidence.map((item) => <small key={item.retrieval_hit_id} className="message-citation">{item.title}</small>)}
      </div>}
      {showRequestDebug && draft?.request_messages && <RequestDebugDialog messages={draft.request_messages} onClose={() => setShowRequestDebug(false)} />}
      {searchEvidence.map((item) => <ManualEvidence key={item.retrieval_hit_id} evidence={item} onSelect={aiEligible ? () => void selectEvidence(item.retrieval_hit_id).catch((caught) => setError(errorMessage(caught))) : undefined} />)}
      {error && <p role="alert">{error}</p>}
    </aside>
  </main>;
}

interface QADynamicBindingData {
  source_table: string;
  filter: Record<string, string>;
  output_columns: { column: string; variable_name: string }[];
  row_limit: number;
}

interface QAItem {
  qa_id: string;
  category: string;
  question: string;
  answer_markdown: string;
  is_active: boolean;
  dynamic_binding: QADynamicBindingData | null;
}

interface Category {
  slug: string;
  label: string;
  is_active: boolean;
}

interface DynamicTableColumn {
  column: string;
  type: string;
}

interface ClinicalDocumentItem {
  document_id: string;
  title: string;
  content_markdown: string;
  is_active: boolean;
}

interface ClinicalChunkItem {
  chunk_id: string;
  heading: string | null;
  content_markdown: string;
}

// V2-8: knowledge-base CRUD screen, reachable from operator navigation,
// separate from the conversation workspace. Reuses the operator's existing
// session — no new role. Minimal functional version; the full visual
// redesign is Phase 9's job (V2-1), same as the rest of this SPA so far.
export function KnowledgeAdminPage() {
  const [token] = useState(() => sessionStorage.getItem("operator_token") || "");
  const [qaItems, setQaItems] = useState<QAItem[]>([]);
  const [documents, setDocuments] = useState<ClinicalDocumentItem[]>([]);
  const [chunksByDocument, setChunksByDocument] = useState<Record<string, ClinicalChunkItem[]>>({});
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  // V3-1×V3-8 "transformar em Q&A": one-time handoff from OperatorPage. A
  // lazy useState initializer (not a ref, not an effect) is React's
  // sanctioned way to run one-off setup exactly once on mount — same
  // pattern this component already uses for reading the operator token
  // above — so this consumes (reads and clears) the handoff exactly once,
  // never re-applying it on a later visit/reload.
  const [prefill] = useState(() => {
    const raw = sessionStorage.getItem("qa_transform_prefill");
    if (raw) sessionStorage.removeItem("qa_transform_prefill");
    return raw ? (JSON.parse(raw) as { question: string; answer: string; category_slug: string | null }) : null;
  });

  const [categories, setCategories] = useState<Category[]>([]);
  const [qaCategory, setQaCategory] = useState(prefill?.category_slug ?? "");
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [newCategorySlug, setNewCategorySlug] = useState("");
  const [newCategoryLabel, setNewCategoryLabel] = useState("");
  const [qaQuestion, setQaQuestion] = useState(prefill?.question ?? "");
  const [qaAnswer, setQaAnswer] = useState(prefill?.answer ?? "");
  const [dynamicTables, setDynamicTables] = useState<string[]>([]);
  const [qaBindingTable, setQaBindingTable] = useState("");
  const [tableColumns, setTableColumns] = useState<DynamicTableColumn[]>([]);
  const [bindingFilter, setBindingFilter] = useState<Record<string, string>>({});
  const [bindingOutputColumns, setBindingOutputColumns] = useState<{ column: string; variable_name: string }[]>([]);
  const [filterColumnDraft, setFilterColumnDraft] = useState("");
  const [filterValueDraft, setFilterValueDraft] = useState("");
  const [outputColumnDraft, setOutputColumnDraft] = useState("");
  const [outputVariableDraft, setOutputVariableDraft] = useState("");

  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");

  const loadAll = useCallback(async () => {
    if (!token) return;
    setQaItems(await api<QAItem[]>("/operator/knowledge/qa", {}, token));
    setDocuments(await api<ClinicalDocumentItem[]>("/operator/knowledge/clinical-documents", {}, token));
    // V3-8: category list stays live — fetched every load, never a fixed
    // copy, so it can never drift from what other operators just created.
    setCategories(await api<Category[]>("/operator/knowledge/categories", {}, token));
    setDynamicTables(await api<string[]>("/operator/knowledge/dynamic-tables", {}, token));
    setLoaded(true);
  }, [token]);

  const selectBindingTable = async (table: string) => {
    setQaBindingTable(table);
    setBindingFilter({});
    setBindingOutputColumns([]);
    setFilterColumnDraft("");
    setOutputColumnDraft("");
    setTableColumns(table ? await api<DynamicTableColumn[]>(`/operator/knowledge/dynamic-tables/${table}/columns`, {}, token) : []);
  };
  const addFilter = () => {
    if (!filterColumnDraft || !filterValueDraft) return;
    setBindingFilter((current) => ({ ...current, [filterColumnDraft]: filterValueDraft }));
    setFilterColumnDraft("");
    setFilterValueDraft("");
  };
  const removeFilter = (column: string) => {
    setBindingFilter((current) => {
      const next = { ...current };
      delete next[column];
      return next;
    });
  };
  const addOutputColumn = () => {
    if (!outputColumnDraft || !outputVariableDraft) return;
    setBindingOutputColumns((current) => [...current, { column: outputColumnDraft, variable_name: outputVariableDraft }]);
    setOutputColumnDraft("");
    setOutputVariableDraft("");
  };
  const removeOutputColumn = (column: string) => {
    setBindingOutputColumns((current) => current.filter((item) => item.column !== column));
  };

  const createCategory = async () => {
    const created = await api<Category>("/operator/knowledge/categories", { method: "POST", body: JSON.stringify({ slug: newCategorySlug, label: newCategoryLabel }) }, token);
    setCategories((current) => [...current, created].sort((a, b) => a.slug.localeCompare(b.slug)));
    setQaCategory(created.slug);
    setNewCategorySlug("");
    setNewCategoryLabel("");
    setCreatingCategory(false);
  };

  useEffect(() => {
    const initial = window.setTimeout(() => void loadAll().catch((caught) => setError(errorMessage(caught))), 0);
    return () => window.clearTimeout(initial);
  }, [loadAll]);

  const loadChunks = async (documentId: string) => {
    const chunks = await api<ClinicalChunkItem[]>(`/operator/knowledge/clinical-documents/${documentId}/chunks`, {}, token);
    setChunksByDocument((current) => ({ ...current, [documentId]: chunks }));
  };

  const createQA = async (event: FormEvent) => {
    event.preventDefault();
    const dynamic_binding = qaBindingTable
      ? { source_table: qaBindingTable, filter: bindingFilter, output_columns: bindingOutputColumns, row_limit: 4 }
      : null;
    await api("/operator/knowledge/qa", { method: "POST", body: JSON.stringify({ category: qaCategory, question: qaQuestion, answer_markdown: qaAnswer, dynamic_binding }) }, token);
    setQaCategory("");
    setQaQuestion("");
    setQaAnswer("");
    await selectBindingTable("");
    await loadAll();
  };

  const deactivateQA = async (qaId: string) => {
    await api(`/operator/knowledge/qa/${qaId}`, { method: "DELETE" }, token);
    await loadAll();
  };

  const createDocument = async (event: FormEvent) => {
    event.preventDefault();
    await api("/operator/knowledge/clinical-documents", { method: "POST", body: JSON.stringify({ title: docTitle, content_markdown: docContent }) }, token);
    setDocTitle("");
    setDocContent("");
    await loadAll();
  };

  const deactivateDocument = async (documentId: string) => {
    await api(`/operator/knowledge/clinical-documents/${documentId}`, { method: "DELETE" }, token);
    await loadAll();
  };

  if (!token) {
    return <main>
      <div className="card stack">
        <h1>Registros de conhecimento</h1>
        <p>Faça login como operador para gerenciar registros.</p>
        <Link to="/operator">Ir para o login do operador</Link>
      </div>
    </main>;
  }

  return <main className="knowledge-admin stack">
    <h1>Registros de conhecimento</h1>
    {error && <p role="alert">{error}</p>}
    <section className="card">
      <h2>Perguntas e respostas</h2>
      <form onSubmit={(event) => void createQA(event).catch((caught) => setError(errorMessage(caught)))}>
        {!creatingCategory && <label htmlFor="qa-category">Categoria
          <select id="qa-category" value={qaCategory} onChange={(event) => setQaCategory(event.target.value)} required>
            <option value="" disabled>Selecione uma categoria</option>
            {categories.map((category) => <option key={category.slug} value={category.slug}>{category.label}</option>)}
          </select>
        </label>}
        {!creatingCategory && <button type="button" className="btn-ghost" onClick={() => setCreatingCategory(true)}>Criar nova categoria</button>}
        {creatingCategory && <fieldset>
          <legend>Nova categoria</legend>
          <label htmlFor="new-category-slug">Identificador<input id="new-category-slug" value={newCategorySlug} onChange={(event) => setNewCategorySlug(event.target.value)} required /></label>
          <label htmlFor="new-category-label">Rótulo<input id="new-category-label" value={newCategoryLabel} onChange={(event) => setNewCategoryLabel(event.target.value)} required /></label>
          <button type="button" onClick={() => void createCategory().catch((caught) => setError(errorMessage(caught)))}>Criar categoria</button>
          <button type="button" className="btn-ghost" onClick={() => setCreatingCategory(false)}>Cancelar</button>
        </fieldset>}
        <label htmlFor="qa-question">Pergunta<input id="qa-question" value={qaQuestion} onChange={(event) => setQaQuestion(event.target.value)} required /></label>
        <label htmlFor="qa-answer">Resposta<textarea id="qa-answer" value={qaAnswer} onChange={(event) => setQaAnswer(event.target.value)} required /></label>
        <fieldset>
          <legend>Vínculo dinâmico (opcional)</legend>
          <label htmlFor="qa-binding-table">Tabela
            <select id="qa-binding-table" value={qaBindingTable} onChange={(event) => void selectBindingTable(event.target.value).catch((caught) => setError(errorMessage(caught)))}>
              <option value="">Nenhuma (resposta estática)</option>
              {dynamicTables.map((table) => <option key={table} value={table}>{table}</option>)}
            </select>
          </label>
          {qaBindingTable && <>
            <div className="stack" style={{ gap: "var(--space-2)" }}>
              <span className="message-author">Filtro</span>
              {Object.entries(bindingFilter).map(([column, value]) => <span key={column} className="badge badge-active">{column} = {value} <button type="button" className="btn-ghost" onClick={() => removeFilter(column)} aria-label={`Remover filtro ${column}`}>×</button></span>)}
              <div className="stack" style={{ gap: "var(--space-2)", flexDirection: "row" }}>
                <select aria-label="Coluna do filtro" value={filterColumnDraft} onChange={(event) => setFilterColumnDraft(event.target.value)}>
                  <option value="">Coluna…</option>
                  {tableColumns.map((col) => <option key={col.column} value={col.column}>{col.column} ({col.type})</option>)}
                </select>
                <input aria-label="Valor do filtro" value={filterValueDraft} onChange={(event) => setFilterValueDraft(event.target.value)} placeholder="valor" />
                <button type="button" className="btn-ghost" onClick={addFilter}>Adicionar filtro</button>
              </div>
            </div>
            <div className="stack" style={{ gap: "var(--space-2)" }}>
              <span className="message-author">Colunas de saída</span>
              {bindingOutputColumns.map((item) => <span key={item.column} className="badge badge-active">{item.column} → {"{{" + item.variable_name + "}}"} <button type="button" className="btn-ghost" onClick={() => removeOutputColumn(item.column)} aria-label={`Remover coluna ${item.column}`}>×</button></span>)}
              <div className="stack" style={{ gap: "var(--space-2)", flexDirection: "row" }}>
                <select aria-label="Coluna de saída" value={outputColumnDraft} onChange={(event) => setOutputColumnDraft(event.target.value)}>
                  <option value="">Coluna…</option>
                  {tableColumns.map((col) => <option key={col.column} value={col.column}>{col.column} ({col.type})</option>)}
                </select>
                <input aria-label="Nome da variável" value={outputVariableDraft} onChange={(event) => setOutputVariableDraft(event.target.value)} placeholder="nome da variável" />
                <button type="button" className="btn-ghost" onClick={addOutputColumn}>Adicionar coluna</button>
              </div>
            </div>
          </>}
        </fieldset>
        <button>Adicionar pergunta e resposta</button>
      </form>
      {!loaded && <p className="is-loading">Carregando registros…</p>}
      {loaded && qaItems.length === 0 && <p className="empty-state">Nenhuma pergunta e resposta cadastrada ainda.</p>}
      <ul>
        {qaItems.map((item) => <li key={item.qa_id}>
          <strong>{item.question}</strong>
          <MessageBody body={item.answer_markdown} />
          {item.dynamic_binding && <small>Vínculo dinâmico: {item.dynamic_binding.source_table}</small>}
          <button type="button" className="btn-danger" onClick={() => void deactivateQA(item.qa_id).catch((caught) => setError(errorMessage(caught)))}>Desativar</button>
        </li>)}
      </ul>
    </section>
    <section className="card">
      <h2>Documentos clínicos</h2>
      <form onSubmit={(event) => void createDocument(event).catch((caught) => setError(errorMessage(caught)))}>
        <label htmlFor="doc-title">Título<input id="doc-title" value={docTitle} onChange={(event) => setDocTitle(event.target.value)} required /></label>
        <label htmlFor="doc-content">Conteúdo<textarea id="doc-content" value={docContent} onChange={(event) => setDocContent(event.target.value)} required /></label>
        <button>Adicionar documento</button>
      </form>
      {loaded && documents.length === 0 && <p className="empty-state">Nenhum documento clínico cadastrado ainda.</p>}
      <ul>
        {documents.map((document) => <li key={document.document_id}>
          <strong>{document.title}</strong>
          <MessageBody body={document.content_markdown} />
          <button type="button" className="btn-secondary" onClick={() => void loadChunks(document.document_id).catch((caught) => setError(errorMessage(caught)))}>Ver seções</button>
          <button type="button" className="btn-danger" onClick={() => void deactivateDocument(document.document_id).catch((caught) => setError(errorMessage(caught)))}>Desativar</button>
          {chunksByDocument[document.document_id] && <ul>{chunksByDocument[document.document_id].map((chunk) => <li key={chunk.chunk_id}>{chunk.heading}: <MessageBody body={chunk.content_markdown} /></li>)}</ul>}
        </li>)}
      </ul>
    </section>
  </main>;
}

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? "active" : "";
}

export function App() {
  return <><nav className="app-nav" aria-label="Navegação principal">
    <NavLink to="/customer" className={navLinkClassName}>Cliente</NavLink>
    <NavLink to="/operator" className={navLinkClassName}>Operador</NavLink>
    <NavLink to="/operator/knowledge" className={navLinkClassName}>Registros</NavLink>
  </nav><Routes><Route path="/customer" element={<CustomerPage />} /><Route path="/operator" element={<OperatorPage />} /><Route path="/operator/knowledge" element={<KnowledgeAdminPage />} /><Route path="*" element={<Navigate to="/customer" replace />} /></Routes></>;
}

const root = document.getElementById("root");
if (root) ReactDOM.createRoot(root).render(<React.StrictMode><BrowserRouter><App /></BrowserRouter></React.StrictMode>);
