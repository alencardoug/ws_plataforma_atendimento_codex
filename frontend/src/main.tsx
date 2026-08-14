import React, { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
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

interface Draft {
  id: string;
  status: "ANSWER" | "ABSTAIN";
  draft_text: string;
  evidence: Evidence[];
  trigger?: "AUTOMATIC" | "MANUAL_DRAFT" | "MANUAL_EVIDENCE";
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

export function ManualEvidence({ evidence, onSelect }: { evidence: Evidence; onSelect?: () => void }) {
  return <article className="manual-evidence"><strong>{evidence.title}</strong>{evidence.section && <small>Seção: {evidence.section}</small>}<MessageBody body={evidence.content} />{evidence.matched_child_excerpt && <><small>Trecho encontrado</small><MessageBody body={evidence.matched_child_excerpt} /></>}{onSelect && <button type="button" onClick={onSelect}>Selecionar</button>}</article>;
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
    return <main><h1>Atendimento</h1><p>Converse anonimamente com nossa equipe.</p><button onClick={() => void start().catch((caught) => setError(errorMessage(caught)))}>Iniciar conversa</button>{error && <p role="alert">{error}</p>}</main>;
  }

  return <main><h1>Atendimento</h1><p>Status: <strong>{conversation?.status || "carregando"}</strong></p><p className="conversation-token" aria-label="Código desta conversa">Código da conversa: <strong>{token}</strong> <button type="button" onClick={() => void copyToken()}>{tokenCopied ? "Copiado!" : "Copiar"}</button></p><section className="messages" aria-live="polite">{conversation?.messages.map((message) => <article key={message.id} className={message.author_type.toLowerCase()}><strong>{message.author_type === "CUSTOMER" ? "Você" : "Atendente"}</strong><MessageBody body={message.body} />{message.citations?.map((citation) => <small key={`${citation.title}-${citation.section || ""}`}>Fonte: {citation.title}{citation.section ? ` — ${citation.section}` : ""}</small>)}</article>)}</section><form onSubmit={(event) => void send(event).catch((caught) => setError(errorMessage(caught)))}><label>Mensagem<textarea value={text} onChange={(event) => setText(event.target.value)} required /></label><button disabled={conversation?.status === "CLOSED"}>Enviar</button></form>{conversation?.status !== "CLOSED" && <button onClick={() => void close().catch((caught) => setError(errorMessage(caught)))}>Encerrar conversa</button>}{error && <p role="alert">{error}</p>}</main>;
}

export function OperatorPage() {
  const [token, setToken] = useState(() => sessionStorage.getItem("operator_token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [selected, setSelected] = useState<OperatorConversation | null>(null);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchEvidence, setSearchEvidence] = useState<Evidence[]>([]);
  const [selectedMessageIds, setSelectedMessageIds] = useState<Set<string>>(new Set());
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
  };
  const claim = async (conversationId: string) => {
    await api<OperatorConversation>(`/operator/conversations/${conversationId}/claim`, { method: "POST" }, token);
    await load();
    await open(conversationId);
  };
  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    await api<Message>(`/operator/conversations/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ body: text, source_generation_id: draft?.id || null, citation_retrieval_hit_ids: [] }) }, token);
    setText("");
    setDraft(null);
    await open(selected.id);
  };
  const canGenerate = selectedMessageIds.size > 0 || searchQuery.trim().length > 0;
  const generate = async () => {
    if (!selected || !canGenerate) return;
    setDraft(await api<Draft>(`/operator/conversations/${selected.id}/drafts`, {
      method: "POST",
      body: JSON.stringify({ selected_message_ids: [...selectedMessageIds], manual_search_text: searchQuery }),
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
    return <main><h1>Espaço do operador</h1><form onSubmit={(event) => void login(event).catch((caught) => setError(errorMessage(caught)))}><label>E-mail<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><label>Senha<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><button>Entrar</button></form>{error && <p role="alert">{error}</p>}</main>;
  }

  const searchAvailable = selected?.effective_mode === "N2" || runtimeConfig?.n1_assistive_search_enabled;
  const useDraftLabel = draft?.evidence.find((item) => item.rank === 1)?.knowledge_type === "CLINICAL" ? "Usar documento completo" : "Usar sugestão";
  return <main className="workspace"><aside><h2>Fila</h2>{items.map((conversation) => <div key={conversation.id}><button onClick={() => void (conversation.status === "WAITING" ? claim(conversation.id) : open(conversation.id)).catch((caught) => setError(errorMessage(caught)))}>{conversation.status} · {conversation.effective_mode} · {conversation.id.slice(0, 8)}</button></div>)}</aside><section><h1>Conversa {selected?.effective_mode}</h1>{selected?.is_customer_typing && <p aria-live="polite" className="typing-indicator">Cliente está digitando…</p>}{selected && <button type="button" onClick={clearMessageSelection}>Desmarcar conversas</button>}{selected?.messages.map((message) => <article key={message.id}><label><input type="checkbox" checked={selectedMessageIds.has(message.id)} onChange={() => toggleMessageSelection(message.id)} aria-label={`Incluir mensagem de ${message.author_type === "CUSTOMER" ? "cliente" : "operador"} no contexto`} /><strong>{message.author_type}</strong></label><MessageBody body={message.body} /></article>)}{selected && <form onSubmit={(event) => void send(event).catch((caught) => setError(errorMessage(caught)))}><textarea value={text} onChange={(event) => setText(event.target.value)} required /><button>Enviar</button></form>}{selected && <button onClick={() => void closeConversation().catch((caught) => setError(errorMessage(caught)))}>Encerrar conversa</button>}</section><aside><h2>IA / Evidências</h2>{selected?.effective_mode === "N2" && <button disabled={!canGenerate} onClick={() => void generate().catch((caught) => setError(errorMessage(caught)))}>Gerar rascunho</button>}{selected?.effective_mode === "N2" && <button onClick={() => void takeOver().catch((caught) => setError(errorMessage(caught)))}>Assumir controle</button>}{selected && searchAvailable && <form onSubmit={(event) => void search(event).catch((caught) => setError(errorMessage(caught)))}><label>Busca manual<input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} required /></label><button>Buscar evidências</button></form>}{selected?.effective_mode === "N1" && !searchAvailable && <p>Busca assistiva N1 desabilitada.</p>}{draft && <div><p>{draft.status}</p><p>{draft.draft_text}</p><button onClick={() => setText(draft.draft_text)}>{useDraftLabel}</button>{draft.evidence.map((item) => <small key={item.retrieval_hit_id}>{item.title}</small>)}</div>}{searchEvidence.map((item) => <ManualEvidence key={item.retrieval_hit_id} evidence={item} onSelect={() => void selectEvidence(item.retrieval_hit_id).catch((caught) => setError(errorMessage(caught)))} />)}{error && <p role="alert">{error}</p>}</aside></main>;
}

export function App() {
  return <><nav aria-label="Navegação principal"><Link to="/customer">Cliente</Link><Link to="/operator">Operador</Link></nav><Routes><Route path="/customer" element={<CustomerPage />} /><Route path="/operator" element={<OperatorPage />} /><Route path="*" element={<Navigate to="/customer" replace />} /></Routes></>;
}

const root = document.getElementById("root");
if (root) ReactDOM.createRoot(root).render(<React.StrictMode><BrowserRouter><App /></BrowserRouter></React.StrictMode>);
