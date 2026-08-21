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
  // AA-10/010/011: set on any of the three autonomous-send exceptions
  // (Constitution Amendments 1.1.0, 1.2.0, 1.3.0), surfaced here purely as
  // an operator transparency cue.
  autonomous_source?: "booking_script" | "governed_autonomy" | "ungoverned_n5" | null;
}

interface CustomerConversation {
  id: string;
  status: ConversationStatus;
  messages: Message[];
  // 008/CS-4: true only while an automatic-draft debounce window is open —
  // never a seconds-remaining count (that stays operator-only).
  preparing_response?: boolean;
  // 007/BS-6: a single rendered summary line once a booking flow has
  // completed for this conversation — session-only (never written to
  // sessionStorage), computed fresh by the backend on every read.
  booking_summary_line?: string | null;
}

interface OperatorConversation extends CustomerConversation {
  effective_mode: MaturityMode;
  is_customer_typing?: boolean;
  latest_generation?: Draft | null;
  // V3-9: present whenever there is customer activity not yet covered by a
  // generation — mirrors evaluate_automatic_trigger's own guard exactly.
  automatic_draft_eligible?: boolean;
  automatic_draft_seconds_remaining?: number | null;
  // 007/BS-5: present once a booking flow has completed for this
  // conversation — `has_slot_detail` distinguishes a full (GB) summary
  // from a specialty-only (AA-10) one, matching spec.md §6's honesty limit.
  booking_summary?: { source: string; line: string; has_slot_detail: boolean } | null;
  // 010/GA-3: the open (PENDING) autonomous-send window for this
  // conversation, if any — full draft text included (unlike the queue-item
  // summary below), since PAUSE/EDIT act on it directly.
  pending_autonomous_send?: PendingAutonomousSend | null;
}

interface PendingAutonomousSendSummary {
  id: string;
  // 011: nullable — an N5 (ungoverned) pending send has no matched category.
  category: string | null;
  mechanism: "governed_autonomy" | "ungoverned_n5";
  resolves_at: string;
}

interface PendingAutonomousSend extends PendingAutonomousSendSummary {
  id: string;
  draft_text: string;
}

interface ConversationSummary {
  id: string;
  status: ConversationStatus;
  effective_mode: MaturityMode;
  unread_customer_messages: number;
  // 010, T20: category + resolves_at only, not the full draft text.
  pending_autonomous_send?: PendingAutonomousSendSummary | null;
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

// 010, T21/T22: computed fresh at render time from the server's own
// resolves_at, not a separately-ticking client interval — the queue's
// existing 2s poll already keeps this reasonably live, matching this
// project's "good enough, no added complexity" bar for a value this
// coarse (window_seconds defaults to 30+).
function secondsUntil(isoTimestamp: string): number {
  return Math.max(0, Math.round((new Date(isoTimestamp).getTime() - Date.now()) / 1000));
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

// 009/EV-1..EV-2: a CLINICAL item's full parent document (`content`) is
// never rendered by default — only its matched child excerpt, with a
// "Trazer documento" action that reveals `content` (already present in the
// fetched payload, no new request). An ADMIN_QA item has no parent to gate
// and keeps the single-phase behavior this component's predecessor
// (ManualEvidence) always had. Used for both manual-search evidence and
// (009/EV-3) automatic-draft evidence — one shared rendering, since
// select_evidence() already treats both sources identically.
export function EvidenceCandidate({ evidence, onSelect, revealed, onReveal }: { evidence: Evidence; onSelect?: () => void; revealed: boolean; onReveal: () => void }) {
  const isClinical = evidence.knowledge_type === "CLINICAL";
  const showFull = !isClinical || revealed;
  return <article className="evidence-item">
    <strong>{evidence.title}</strong>
    {evidence.section && <small>Seção: {evidence.section}</small>}
    {isClinical && !showFull && evidence.matched_child_excerpt && <>
      <small>Trecho encontrado</small>
      <MessageBody body={evidence.matched_child_excerpt} />
      <button type="button" className="btn-secondary" onClick={onReveal}>Trazer documento</button>
    </>}
    {showFull && <>
      <MessageBody body={evidence.content} />
      {isClinical && evidence.matched_child_excerpt && <><small>Trecho encontrado</small><MessageBody body={evidence.matched_child_excerpt} /></>}
      {onSelect && <button type="button" onClick={onSelect}>Selecionar</button>}
    </>}
  </article>;
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

// V3-11: purely a client-side guard in front of the existing close
// endpoint on both surfaces — no backend/API change. Shared between
// CustomerPage and OperatorPage so the copy stays identical.
function CloseConfirmPrompt({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return <div className="close-confirm" role="alertdialog" aria-label="Confirmar encerramento">
    <p>Deseja encerrar a conversa?</p>
    <button type="button" className="btn-danger" onClick={onConfirm}>Encerrar conversa</button>
    <button type="button" className="btn-ghost" onClick={onCancel}>Retornar e continuar conversa</button>
  </div>;
}

const SCORE_EMOJI: Record<number, string> = { 1: "😡", 2: "🙁", 3: "😐", 4: "🙂", 5: "😄" };

// V3-12: optional, never blocks/delays the close that already happened —
// pure local state until the operator explicitly submits or skips.
function SatisfactionSurvey({ onSubmit, onSkip }: { onSubmit: (score: number, resolved: boolean) => void; onSkip: () => void }) {
  const [score, setScore] = useState<number | null>(null);
  const [resolved, setResolved] = useState<boolean | null>(null);
  return <div className="satisfaction-survey stack" aria-label="Pesquisa de satisfação">
    <p>Como você avalia este atendimento?</p>
    <div className="satisfaction-scores">
      {[1, 2, 3, 4, 5].map((value) => <button key={value} type="button" aria-pressed={score === value} className={score === value ? "btn-secondary" : "btn-ghost"} onClick={() => setScore(value)}>{SCORE_EMOJI[value]}</button>)}
    </div>
    <p>Sua necessidade foi resolvida?</p>
    <div className="satisfaction-resolved">
      <button type="button" aria-pressed={resolved === true} className={resolved === true ? "btn-secondary" : "btn-ghost"} onClick={() => setResolved(true)}>Sim 🙂</button>
      <button type="button" aria-pressed={resolved === false} className={resolved === false ? "btn-secondary" : "btn-ghost"} onClick={() => setResolved(false)}>Não 🙁</button>
    </div>
    <div className="satisfaction-actions">
      <button type="button" disabled={score === null || resolved === null} onClick={() => score !== null && resolved !== null && onSubmit(score, resolved)}>Enviar avaliação</button>
      <button type="button" className="btn-ghost" onClick={onSkip}>Pular</button>
    </div>
  </div>;
}

export function CustomerPage() {
  const [id, setId] = useState(() => sessionStorage.getItem("conversation_id") || "");
  const [token, setToken] = useState(() => sessionStorage.getItem("conversation_token") || "");
  const [conversation, setConversation] = useState<CustomerConversation | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [tokenCopied, setTokenCopied] = useState(false);
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [surveyState, setSurveyState] = useState<"pending" | "dismissed" | "submitted">("pending");
  const [startCountdown, setStartCountdown] = useState<number | null>(null);

  useEffect(() => {
    document.documentElement.dataset.page = "customer";
    return () => {
      delete document.documentElement.dataset.page;
    };
  }, []);

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

  // Purely cosmetic cold-start expectation-setter: begins 0.5s after the
  // click and counts down 8s, but never gates the real request — whichever
  // finishes first (the API response or the countdown) wins, since a
  // successful start() unmounts this view via the `id` state change.
  const handleStart = () => {
    setError("");
    setStartCountdown(null);
    const reveal = window.setTimeout(() => setStartCountdown(8), 500);
    void start().catch((caught) => {
      window.clearTimeout(reveal);
      setStartCountdown(null);
      setError(errorMessage(caught));
    });
  };

  const startCountdownActive = startCountdown !== null && startCountdown > 0;
  useEffect(() => {
    if (!startCountdownActive) return;
    const timer = window.setInterval(() => setStartCountdown((current) => (current === null ? null : Math.max(0, current - 1))), 1000);
    return () => window.clearInterval(timer);
  }, [startCountdownActive]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    await api<Message>(`/public/conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ body: text }) }, token);
    setText("");
    await refresh();
  };

  const close = async () => {
    setConfirmingClose(false);
    const closed = await api<CustomerConversation>(`/public/conversations/${id}`, { method: "POST" }, token);
    setConversation(closed);
    setSurveyState("pending");
  };

  const submitSurvey = async (score: number, resolved: boolean) => {
    await api(`/public/conversations/${id}/satisfaction`, { method: "POST", body: JSON.stringify({ score, resolved }) }, token);
    setSurveyState("submitted");
    sessionStorage.removeItem("conversation_id");
    sessionStorage.removeItem("conversation_token");
  };
  const skipSurvey = () => {
    setSurveyState("dismissed");
    sessionStorage.removeItem("conversation_id");
    sessionStorage.removeItem("conversation_token");
  };

  if (!id) {
    return <main>
      <div className="card stack">
        <h1>Canal de agendamento e informações</h1>
        <p className="disclaimer-banner">
          <strong>Projeto de demonstração técnica (portfólio)</strong>
          Esta instituição, seus profissionais, procedimentos e todo o conteúdo clínico exibido aqui são fictícios. Não é um serviço de saúde real — não envie dados pessoais ou de saúde verídicos.
        </p>
        <p>Converse anonimamente com nossos atendentes e agentes.</p>
        <p>Agende consultas e consulte informações clínicas — por exemplo, como se preparar para procedimentos cirúrgicos e de tratamento, além dos cuidados após os procedimentos.</p>
        <p>Também há informações administrativas, diretrizes em casos de emergência e detalhes de acompanhamentos pós-tratamento, como atendimento psico-oncológico, nutricional, endocrinológico e fisioterapêutico.</p>
        <button onClick={handleStart} disabled={startCountdown !== null}>Iniciar conversa</button>
        {startCountdown !== null && (
          <p aria-live="polite" className="typing-indicator">
            {startCountdown > 0 ? `Preparando atendimento… ${startCountdown}s` : "Preparando atendimento…"}
          </p>
        )}
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
      {/* 008/CS-4: deliberately its own line, not sharing "Digitando…"'s
          span below — distinct location as well as distinct copy, so the
          two cues (this one reflects the operator's side preparing a
          reply; "Digitando…" reflects the customer's own typing) can never
          be mistaken for one another even if both are true at once. */}
      {conversation?.preparing_response && <p aria-live="polite" className="typing-indicator">Preparando resposta…</p>}
      <form onSubmit={(event) => void send(event).catch((caught) => setError(errorMessage(caught)))}>
        <label htmlFor="customer-message">Mensagem<textarea id="customer-message" value={text} onChange={(event) => setText(event.target.value)} required disabled={conversation?.status === "CLOSED"} /></label>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <button disabled={conversation?.status === "CLOSED"}>Enviar</button>
          {text.trim().length > 0 && conversation?.status !== "CLOSED" && <span aria-live="polite" className="typing-indicator">Digitando…</span>}
        </div>
      </form>
      {/* 007/BS-6/BS-7: session-only — computed fresh from the response
          already fetched by the poll above, nothing written to
          sessionStorage. Position is exact per spec.md BS-7: below
          "Enviar", above "Encerrar conversa". */}
      {conversation?.booking_summary_line && <p className="booking-summary" aria-label="Agendamento realizado">{conversation.booking_summary_line}</p>}
      {conversation?.status !== "CLOSED" && (confirmingClose
        ? <CloseConfirmPrompt onConfirm={() => void close().catch((caught) => setError(errorMessage(caught)))} onCancel={() => setConfirmingClose(false)} />
        : <button type="button" className="btn-ghost" onClick={() => setConfirmingClose(true)}>Encerrar conversa</button>)}
      {conversation?.status === "CLOSED" && surveyState === "pending" && <SatisfactionSurvey onSubmit={(score, resolved) => void submitSurvey(score, resolved).catch((caught) => setError(errorMessage(caught)))} onSkip={skipSurvey} />}
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
  // 009/EV-1..EV-2: which CLINICAL evidence items have had their full
  // parent document explicitly revealed ("Trazer documento"). Lifted here
  // (not local state inside EvidenceCandidate) so a poll-driven re-render
  // of `draft` never collapses an already-revealed card back to hidden.
  const [revealedEvidenceIds, setRevealedEvidenceIds] = useState<Set<string>>(new Set());
  const revealDocument = (retrievalHitId: string) => {
    setRevealedEvidenceIds((prev) => new Set(prev).add(retrievalHitId));
    // 009/EV-5: "Trazer documento" takes over the top-of-page scroll V3-10
    // originally gave to evidence selection.
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const [selectedMessageIds, setSelectedMessageIds] = useState<Set<string>>(new Set());
  const [showRequestDebug, setShowRequestDebug] = useState(false);
  const [markedIncorrectIds, setMarkedIncorrectIds] = useState<Set<string>>(new Set());
  const [escalatedIds, setEscalatedIds] = useState<Set<string>>(new Set());
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [error, setError] = useState("");
  const [countdown, setCountdown] = useState<number | null>(null);
  // AA-9: a global ops action, not tied to any conversation — its status
  // line lives in the queue sidebar regardless of what's selected.
  const [availabilityMessage, setAvailabilityMessage] = useState("");

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

  // V3-9: resyncs from the server on every poll response (`selected`
  // changes), never a locally-invented clock — client-clock drift never
  // compounds since this only ever overwrites, never accumulates. Adjusted
  // during render (React's documented pattern for "reset state when some
  // other value changes"), guarded by comparing against the previously
  // seen source values — not an effect+setState, which this project's
  // stricter eslint rules reject as a cascading-render risk.
  const [countdownSource, setCountdownSource] = useState<{ eligible?: boolean; remaining?: number | null }>({});
  if (countdownSource.eligible !== selected?.automatic_draft_eligible || countdownSource.remaining !== selected?.automatic_draft_seconds_remaining) {
    setCountdownSource({ eligible: selected?.automatic_draft_eligible, remaining: selected?.automatic_draft_seconds_remaining });
    setCountdown(selected?.automatic_draft_eligible ? (selected?.automatic_draft_seconds_remaining ?? null) : null);
  }

  // Ticks once a second between polls. Depends on countdownActive (not
  // countdown itself) so the interval is only re-created when switching
  // between "showing" and "hidden," never restarted every tick.
  const countdownActive = countdown !== null;
  useEffect(() => {
    if (!countdownActive) return;
    const timer = window.setInterval(() => setCountdown((current) => (current === null ? null : Math.max(0, current - 1))), 1000);
    return () => window.clearInterval(timer);
  }, [countdownActive]);

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
    setConfirmingClose(false);
  };
  const claim = async (conversationId: string) => {
    await api<OperatorConversation>(`/operator/conversations/${conversationId}/claim`, { method: "POST" }, token);
    await load();
    await open(conversationId);
  };
  // AA-9: not conversation-scoped — usable with no conversation selected.
  const ensureAvailability = async () => {
    const data = await api<{ created_d1: number; created_d7: number; already_sufficient: boolean; message: string }>("/operator/scheduling/ensure-availability", { method: "POST" }, token);
    setAvailabilityMessage(data.message);
  };
  // 006/SV: a separate, wider one-time bulk fill — every specialty, every
  // business day through 2026-12-30 — not a replacement for AA-9's own
  // D+1/D+7 generalist-only button above.
  const ensureWideAvailability = async () => {
    const data = await api<{ specialty_count: number; business_day_count: number; slots_created: number; message: string }>("/operator/scheduling/ensure-wide-availability", { method: "POST" }, token);
    setAvailabilityMessage(data.message);
  };
  // 010/GA-4: available on any conversation regardless of claim status
  // (plan.md §4 — PAUSE works even on a WAITING conversation, since GA-6
  // allows autonomy there) — a direct queue-item action rather than
  // requiring the operator to open/claim the conversation first.
  const pauseAutonomousSend = async (conversationId: string, pendingId: string) => {
    await api(`/operator/conversations/${conversationId}/pending-autonomous-send/${pendingId}/pause`, { method: "POST" }, token);
    await load();
    if (selectedId === conversationId) await refreshSelected();
  };
  // Ops/testing convenience: `items` (scope=all) already scopes its ACTIVE
  // rows to this operator's own assignments server-side, so every close()
  // on an already-active conversation is authorized by construction. A
  // WAITING one has no assignment yet — close() requires one
  // (require_assignment), so each is claimed immediately before its own
  // close call. Both loops are sequential, one conversation at a time (not
  // Promise.all): for WAITING rows specifically, this also keeps this
  // operator's active count low at every instant — each newly-claimed
  // conversation is closed again before the next claim, so the V1
  // max-4-active limit is never actually at risk regardless of how many
  // WAITING conversations exist. One failure doesn't abort the rest; the
  // queue list only reloads once, at the end.
  const closeAllConversations = async () => {
    const activeIds = items.filter((conversation) => conversation.status === "ACTIVE").map((conversation) => conversation.id);
    const waitingIds = items.filter((conversation) => conversation.status === "WAITING").map((conversation) => conversation.id);
    const total = activeIds.length + waitingIds.length;
    if (total === 0) return;
    if (!window.confirm(`Encerrar ${total} conversa(s) (${activeIds.length} ativa(s), ${waitingIds.length} aguardando)?`)) return;
    for (const conversationId of activeIds) {
      await api<ConversationSummary>(`/operator/conversations/${conversationId}/close`, { method: "POST" }, token);
    }
    for (const conversationId of waitingIds) {
      await api<OperatorConversation>(`/operator/conversations/${conversationId}/claim`, { method: "POST" }, token);
      await api<ConversationSummary>(`/operator/conversations/${conversationId}/close`, { method: "POST" }, token);
    }
    if (selectedId && (activeIds.includes(selectedId) || waitingIds.includes(selectedId))) {
      setSelected(null);
      setDraft(null);
      setSearchEvidence([]);
    }
    await load();
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
    setConfirmingClose(false);
    await api<ConversationSummary>(`/operator/conversations/${selected.id}/close`, { method: "POST" }, token);
    setSelected(null);
    setDraft(null);
    setSearchEvidence([]);
    setRevealedEvidenceIds(new Set());
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
    // V3-10, corrected by 009/EV-5 (D-039): originally scrolled to the page
    // top; now scrolls the reply textarea into view instead, since
    // "Trazer documento" (above) took over the top-of-page scroll for the
    // one case (revealing a long parent) where starting at the top still
    // helps. Fires only here, inside this click handler, never inside a
    // useEffect keyed on poll-refreshed state, so the 2-second poll's
    // unrelated re-renders can never re-trigger it.
    document.getElementById("operator-reply")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  // V3-7: purely client-side reset, independent of message-selection state
  // ("desmarcar conversas", V2-4). No server round-trip, no durable row
  // touched — HCR/V3-1 metrics do not distinguish "generated and
  // discarded" from "never generated" for V3 (spec.md's resolution).
  const clearDraftAndSearch = () => {
    setDraft(null);
    setSearchEvidence([]);
    setRevealedEvidenceIds(new Set());
    setSearchQuery("");
    setInstructionText("");
    setShowRequestDebug(false);
  };

  if (!token) {
    return <main>
      <div className="card stack">
        <h1>Espaço do operador</h1>
        <p className="disclaimer-banner">
          <strong>Projeto de demonstração técnica (portfólio)</strong>
          Ambiente fictício de estudo de caso — nenhum dado ou atendimento aqui é real.
        </p>
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
      {items.map((conversation) => <div key={conversation.id} className="queue-row">
        <button
          type="button"
          className="queue-item"
          aria-current={conversation.id === selectedId ? "true" : undefined}
          onClick={() => void (conversation.status === "WAITING" ? claim(conversation.id) : open(conversation.id)).catch((caught) => setError(errorMessage(caught)))}
        >
          <StatusBadge status={conversation.status} />{" "}
          <span>{conversation.effective_mode} · {conversation.id.slice(0, 8)}</span>{" "}
          {conversation.unread_customer_messages > 0 && <span className="badge badge-waiting" title="Mensagens do cliente ainda sem resposta do operador">{conversation.unread_customer_messages} sem resposta</span>}{" "}
          {conversation.pending_autonomous_send && <span className="badge badge-autonomy" title={conversation.pending_autonomous_send.mechanism === "ungoverned_n5" ? "Resposta autônoma pendente — modo N5, sem evidência" : `Resposta autônoma pendente (categoria: ${conversation.pending_autonomous_send.category})`}>envio autônomo em {secondsUntil(conversation.pending_autonomous_send.resolves_at)}s</span>}
        </button>
        {/* 010/GA-4: works even for a WAITING conversation no operator has
            claimed yet (GA-6) — a direct action here avoids forcing a
            claim just to stop an autonomous send. */}
        {conversation.pending_autonomous_send && <button type="button" className="btn-ghost" onClick={() => void pauseAutonomousSend(conversation.id, (conversation.pending_autonomous_send as PendingAutonomousSendSummary).id).catch((caught) => setError(errorMessage(caught)))} title="Pausar envio autônomo">Pausar</button>}
      </div>)}
      <button type="button" className="btn-ghost" onClick={() => void closeAllConversations().catch((caught) => setError(errorMessage(caught)))}>Encerrar todas as conversas</button>
      <button type="button" className="btn-ghost" onClick={() => void ensureAvailability().catch((caught) => setError(errorMessage(caught)))}>Garantir disponibilidade (D+1/D+7)</button>
      <button type="button" className="btn-ghost" onClick={() => void ensureWideAvailability().catch((caught) => setError(errorMessage(caught)))}>Preencher agenda ampla (até 30/12/2026)</button>
      {availabilityMessage && <p role="status" aria-live="polite">{availabilityMessage}</p>}
      {/* 010/GA-3, GA-5, T23: window_seconds and the kill switch live on
          the knowledge-admin page instead (alongside category autonomy
          management, consolidating all autonomy configuration in one
          place) — found live that a checkbox/number input here, ahead of
          the conversation section's own message-selection checkboxes in
          DOM order, broke pre-existing tests' `getByRole("checkbox").first()`
          assumptions elsewhere on this same page. */}
    </aside>
    <section className="card">
      {selected ? <>
        <h1>Conversa {selected.effective_mode}</h1>
        {/* 007/BS-5: read fresh from appointment_bookings on every poll —
            has_slot_detail distinguishes a full (GB) summary from a
            specialty-only (AA-10) one (spec.md §6). */}
        {selected.booking_summary && <p className="booking-summary" aria-label="Agendamento realizado">{selected.booking_summary.line}</p>}
        {selected.is_customer_typing && <p aria-live="polite" className="typing-indicator">Cliente está digitando…</p>}
        {countdown !== null && <p aria-live="polite" className="typing-indicator">{countdown > 0 ? `Respondendo em ${countdown}s…` : "Gerando resposta…"}</p>}
        {/* 010/GA-4, T22: read-only preview, not the editable reply
            textarea — EDIT works by pre-filling that existing textarea
            below (reusing "Usar sugestão"'s own copy-into-textarea
            pattern) and sending normally, which resolves the pending row
            as a side effect (plan.md §4) without a dedicated endpoint. */}
        {selected.pending_autonomous_send && <div className="card pending-autonomy" aria-label="Envio autônomo pendente">
          <p><strong>Envio autônomo pendente</strong> — {selected.pending_autonomous_send.mechanism === "ungoverned_n5" ? "modo N5, sem evidência" : `categoria "${selected.pending_autonomous_send.category}"`}, em {secondsUntil(selected.pending_autonomous_send.resolves_at)}s.</p>
          <MessageBody body={selected.pending_autonomous_send.draft_text} />
          <div className="stack" style={{ gap: "var(--space-2)" }}>
            <button type="button" className="btn-ghost" onClick={() => void pauseAutonomousSend(selected.id, (selected.pending_autonomous_send as PendingAutonomousSend).id).catch((caught) => setError(errorMessage(caught)))}>Pausar</button>
            <button type="button" className="btn-secondary" onClick={() => { setText((selected.pending_autonomous_send as PendingAutonomousSend).draft_text); document.getElementById("operator-reply")?.focus(); }}>Editar</button>
            <button type="button" className="btn-secondary" onClick={() => void takeOver().catch((caught) => setError(errorMessage(caught)))}>Assumir controle</button>
          </div>
        </div>}
        <button type="button" className="btn-ghost" onClick={clearMessageSelection}>Desmarcar conversas</button>
        <div className="messages">
          {selected.messages.length === 0 && <p className="empty-state">Sem mensagens nesta conversa ainda.</p>}
          {selected.messages.map((message) => <article key={message.id} className={`message ${message.author_type.toLowerCase()}`}>
            <label className="message-select">
              <input type="checkbox" checked={selectedMessageIds.has(message.id)} onChange={() => toggleMessageSelection(message.id)} aria-label={`Incluir mensagem de ${message.author_type === "CUSTOMER" ? "cliente" : "operador"} no contexto`} />
              <span className="message-author">{message.author_type === "CUSTOMER" ? "Cliente" : "Operador"}</span>
              {/* 010, T24: generalized from booking_script-only to either
                  autonomous-send exception, one shared badge. */}
              {message.autonomous_source && <span className="badge" title={message.autonomous_source === "booking_script" ? "Enviada automaticamente pelo fluxo de agendamento simulado, sem clique do operador" : message.autonomous_source === "ungoverned_n5" ? "Enviada automaticamente sem evidência — modo N5, demonstração" : "Enviada automaticamente por resposta autônoma governada, sem clique do operador"}>automático</span>}
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
          {confirmingClose
            ? <CloseConfirmPrompt onConfirm={() => void closeConversation().catch((caught) => setError(errorMessage(caught)))} onCancel={() => setConfirmingClose(false)} />
            : <button type="button" className="btn-ghost" onClick={() => setConfirmingClose(true)}>Encerrar conversa</button>}
        </> : <p className="is-loading">Esta conversa está encerrada.</p>}
      </> : <p className="empty-state">Selecione uma conversa na fila para começar.</p>}
    </section>
    <aside className="card" aria-label="IA e evidências">
      <h2>IA / Evidências</h2>
      {aiEligible && <div className="stack" style={{ gap: "var(--space-2)" }}>
        <label htmlFor="instruction-text">Instrução para regenerar (opcional)<input id="instruction-text" value={instructionText} onChange={(event) => setInstructionText(event.target.value)} placeholder="ex.: seja mais formal" /></label>
        <button disabled={!canGenerate} onClick={() => void generate().catch((caught) => setError(errorMessage(caught)))}>Gerar rascunho</button>
        <button type="button" className="btn-secondary" onClick={() => void takeOver().catch((caught) => setError(errorMessage(caught)))}>Assumir controle</button>
        {(draft || searchEvidence.length > 0) && <button type="button" className="btn-ghost" onClick={clearDraftAndSearch}>Limpar</button>}
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
        {/* 009/EV-3: previously an inert <small> citation label with no
            selection mechanism — each item is now its own selectable
            candidate card, alongside (not replacing) "Usar sugestão" above. */}
        {draft.evidence.map((item) => <EvidenceCandidate key={item.retrieval_hit_id} evidence={item} revealed={revealedEvidenceIds.has(item.retrieval_hit_id)} onReveal={() => revealDocument(item.retrieval_hit_id)} onSelect={aiEligible ? () => void selectEvidence(item.retrieval_hit_id).catch((caught) => setError(errorMessage(caught))) : undefined} />)}
      </div>}
      {showRequestDebug && draft?.request_messages && <RequestDebugDialog messages={draft.request_messages} onClose={() => setShowRequestDebug(false)} />}
      {searchEvidence.map((item) => <EvidenceCandidate key={item.retrieval_hit_id} evidence={item} revealed={revealedEvidenceIds.has(item.retrieval_hit_id)} onReveal={() => revealDocument(item.retrieval_hit_id)} onSelect={aiEligible ? () => void selectEvidence(item.retrieval_hit_id).catch((caught) => setError(errorMessage(caught))) : undefined} />)}
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
  // 010/GA-1: default false — no category is autonomous until an
  // operator explicitly turns it on.
  autonomy_enabled: boolean;
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
  const [autonomySettings, setAutonomySettings] = useState<{ window_seconds: number; kill_switch_enabled: boolean; n5_kill_switch_enabled: boolean; automatic_trigger_idle_seconds: number } | null>(null);
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
    // 010/GA-3, GA-5: global, not per-conversation — consolidated here
    // alongside category autonomy management (plan.md §5's UI scope was
    // left to implementation judgment; found live that placing this on
    // OperatorPage's own queue sidebar collided with pre-existing tests'
    // `getByRole("checkbox").first()` assumptions there).
    setAutonomySettings(await api<{ window_seconds: number; kill_switch_enabled: boolean; n5_kill_switch_enabled: boolean; automatic_trigger_idle_seconds: number }>("/operator/autonomy-settings", {}, token));
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

  // 010/GA-1: any authenticated operator, no separate supervisor role.
  const toggleCategoryAutonomy = async (slug: string, enabled: boolean) => {
    const updated = await api<Category>(`/operator/knowledge/categories/${slug}/autonomy`, { method: "POST", body: JSON.stringify({ enabled }) }, token);
    setCategories((current) => current.map((category) => (category.slug === slug ? updated : category)));
  };
  const setAutonomyWindowSeconds = async (windowSeconds: number) => {
    setAutonomySettings(await api("/operator/autonomy-settings", { method: "POST", body: JSON.stringify({ window_seconds: windowSeconds }) }, token));
  };
  const setAutonomyKillSwitch = async (enabled: boolean) => {
    setAutonomySettings(await api("/operator/autonomy-settings", { method: "POST", body: JSON.stringify({ kill_switch_enabled: enabled }) }, token));
  };
  const setN5KillSwitch = async (enabled: boolean) => {
    setAutonomySettings(await api("/operator/autonomy-settings", { method: "POST", body: JSON.stringify({ n5_kill_switch_enabled: enabled }) }, token));
  };
  const setAutomaticTriggerIdleSeconds = async (seconds: number) => {
    setAutonomySettings(await api("/operator/autonomy-settings", { method: "POST", body: JSON.stringify({ automatic_trigger_idle_seconds: seconds }) }, token));
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
      <h2>Autonomia por categoria</h2>
      {/* 010/GA-1, T23: no category is autonomous until explicitly turned
          on here — default false for every row. The checkbox's own
          accessible name is deliberately NOT built from `category.label`
          directly (an explicit aria-label instead of wrapping a <label>
          around the raw category text) — found live that a category
          whose own label happens to start with "Categoria" (as this
          page's pre-existing "Criar categoria" flow's own fixture
          categories do, e.g. v2.spec.ts's own test categories) collided
          with existing `getByLabel("Categoria")` queries elsewhere on
          this same page, a strict-mode violation neither side caused on
          its own. */}
      <ul className="stack" style={{ gap: "var(--space-2)" }}>
        {categories.map((category) => <li key={category.slug}>
          <input type="checkbox" id={`autonomy-${category.slug}`} aria-label={`Autonomia para ${category.slug}`} checked={category.autonomy_enabled} onChange={(event) => void toggleCategoryAutonomy(category.slug, event.target.checked).catch((caught) => setError(errorMessage(caught)))} />
          {" "}<label htmlFor={`autonomy-${category.slug}`}>{category.label} ({category.slug})</label>
        </li>)}
      </ul>
      {/* 010/GA-3, GA-5: global, not per-category — window_seconds down to
          0 (immediate send, Constitution Amendment 1.2.0 (d)) and the
          kill switch, consolidated here with category management. */}
      {autonomySettings && <div className="stack" style={{ gap: "var(--space-2)" }}>
        <label htmlFor="autonomy-window">Janela de veto (segundos, 0 = envio imediato)
          <input id="autonomy-window" type="number" min={0} value={autonomySettings.window_seconds} onChange={(event) => void setAutonomyWindowSeconds(Number(event.target.value)).catch((caught) => setError(errorMessage(caught)))} />
        </label>
        <label htmlFor="autonomy-kill-switch">
          <input id="autonomy-kill-switch" type="checkbox" checked={autonomySettings.kill_switch_enabled} onChange={(event) => void setAutonomyKillSwitch(event.target.checked).catch((caught) => setError(errorMessage(caught)))} />
          {" "}Envio autônomo ativado (interruptor geral)
        </label>
        <label htmlFor="autonomy-idle-seconds">Tempo de espera antes do rascunho automático (segundos)
          <input id="autonomy-idle-seconds" type="number" min={0} value={autonomySettings.automatic_trigger_idle_seconds} onChange={(event) => void setAutomaticTriggerIdleSeconds(Number(event.target.value)).catch((caught) => setError(errorMessage(caught)))} />
        </label>
        {/* 011 (Constitution Amendment 1.3.0): independent of the kill
            switch above — neither implies the other. Label makes the
            demo-only scope explicit, matching the disclaimer banner.
            Explicit aria-label (not the visible label text, which
            contains the lowercase word "categoria") — found live that the
            visible text collided case-insensitively with v2.spec.ts's own
            pre-existing `getByLabel("Categoria")` queries elsewhere on
            this page, the same collision class feature 010 hit and fixed
            for the per-category checkboxes below. */}
        <label htmlFor="n5-kill-switch">
          <input id="n5-kill-switch" type="checkbox" aria-label="Autonomia sem filtro de evidência (N5)" checked={autonomySettings.n5_kill_switch_enabled} onChange={(event) => void setN5KillSwitch(event.target.checked).catch((caught) => setError(errorMessage(caught)))} />
          {" "}Autonomia sem filtro de evidência — N5 (demonstração fictícia, sem categoria/evidência necessária)
        </label>
      </div>}
    </section>
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
