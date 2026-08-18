# V3 Acceptance Protocol

This is the executable definition of DONE for V3, supplementary to `spec.md`
§5. It extends `specs/002-v2-commercial-product-experience/acceptance.md`
(itself extending V1's) — this document does not repeat scenarios V3 leaves
unchanged (queue/capacity, N1 manual messaging, citation exposure, take-over,
token display/rate-limiting, typing-debounced automatic trigger mechanics,
dynamic-evidence pattern resolution, knowledge-CRUD `validate_binding`)
except where a V3 change requires re-proving them. Not yet executed — no
Execution record section exists until Phase 13 (`tasks.md` T130) runs it.

## A. Environment

- [ ] V3 migration (`tasks.md` T016) applies cleanly on top of the V2
  acceptance database, and on an empty database migrated through V1 then V2
  then V3.
- [ ] Existing V1/V2 conversations/messages/generations/qa_entries/documents
  rows are unaffected by the migration; every distinct `qa_entries.category`
  and `documents.cancer_type` value survives the `content.categories`
  backfill with no loss (`tasks.md` T011/T017).
- [ ] Compose stack starts healthy with no new required infrastructure — no
  scheduler/background worker was added for V3-9's countdown or any other
  outcome (`plan.md` §2/§23).

## B. Operator feedback taxonomy [V3-1]

1. For a generation an operator sends unmodified (via the reply box, not
   quick-approve), confirm `ai.draft_accepted` is recorded and
   `classify_generation` returns `approve` — no new column was needed.
2. For a generation an operator edits before sending, confirm
   `ai.draft_edited` is recorded and `classify_generation` returns `edit`.
3. Call `mark-incorrect` on a generation from earlier in the conversation
   history (not the latest); confirm it succeeds, `marked_incorrect_at`/
   `marked_incorrect_by_operator_id` are set, and `generation.marked_incorrect`
   is audited.
4. Re-call `mark-incorrect` on the same generation; confirm it is idempotent
   (timestamp updates, no error, no duplicate row).
5. Call `escalate` on a generation; confirm `escalated_at`/
   `escalated_by_operator_id` are set, `generation.escalated` is audited, and
   no queue/routing side effect occurs anywhere in the system.
6. Call `mark-incorrect`/`escalate` with a `generation_id` that belongs to a
   different conversation than the `conversation_id` in the path; confirm
   `422`.
7. Confirm a single generation can carry both `edit` and, later,
   `marked_incorrect` simultaneously (independent, non-exclusive facts).

## C. Quick-approve action [V3-2]

1. With a `latest_generation.status == "ANSWER"`, click "Aprovar"; confirm
   the customer-visible message body is byte-for-byte identical to
   `draft_text`, and `ai.draft_accepted` (not `_edited`) is recorded.
2. Confirm quick-approve calls the same
   `POST /operator/conversations/{id}/messages` endpoint as every other send
   — no dedicated quick-approve endpoint exists.
3. Generate a newer draft in the same conversation, then attempt to send
   against the now-stale earlier `generation_id`; confirm `409
   STALE_GENERATION`.
4. Negative test: confirm no code path reaches
   `POST /operator/conversations/{id}/messages` without `CurrentOperator` +
   assignment-gating — quick-approve inherits this, it does not add its own
   check.

## D. Human Correction Rate [V3-3]

1. Run `docs/metrics/v3_queries.sql`'s HCR query against a fixture dataset
   with a known mix of `approve`/`edit` events; confirm the computed rate
   matches a hand-calculated value, overall and per category.
2. Confirm the query only reads `audit_events`/`ai_generations` —
   reproducible from raw stored data by an independent query (acceptance
   outcome 3), not from any cached/derived value.

## E. Read-only management metrics [V3-4]

1. Confirm `docs/metrics/v3_queries.sql` covers abstention rate, HCR,
   generation volume by trigger/category, and V3-12's average
   score/resolved-rate — each with an explicit "sem categoria" row for
   `category_slug IS NULL`, never a silently dropped bucket.
2. Confirm there is no backend endpoint or frontend route serving these
   queries — read-only is enforced by the complete absence of a write
   surface, not by hiding a control in the UI.

## F. Evaluation datasets/suites [V3-5]

1. Create an evaluation case via `POST /operator/evaluation/cases`; confirm
   it never creates a `Conversation` or `Message` row anywhere.
2. Confirm `content.evaluation_cases` has no FK path into
   `conversations`/`ai_generations`, and no production query
   (`docs/metrics/v3_queries.sql`) ever joins against it — structural
   isolation (acceptance outcome 5), not a runtime filter.
3. `PATCH` a case's `actual_status`/`actual_notes`; confirm no automated
   process ever calls this endpoint — only a manual reviewer action does.
4. Confirm a case is traceable back to its `category_slug`.

## G. Regenerate-with-instruction [V3-6]

1. Submit `instruction_text` on a `/drafts` call together with
   `selected_message_ids`; confirm both are honored (combined, not
   replaced) and `instruction_text` is stored on the resulting generation.
2. Confirm the resulting generation is still an internal draft only — no
   customer-visible message is created by this call.
3. Confirm `instruction_text` is retrievable in operator/audit views
   (`ai.draft_generated`/`ai.draft_abstained` payload) and never appears in
   any public/customer-facing response schema.
4. Confirm the instruction text is never echoed verbatim into `draft_text`
   unless the operator explicitly sends text containing it.

## H. Clear/reset control [V3-7]

1. Generate a draft and run a manual search; click "Limpar"; confirm the
   draft panel and evidence-search results both empty.
2. Confirm message-selection state (checked messages) is unaffected by
   "Limpar".
3. Confirm no durably stored `ai_generations`/`audit_events` row is deleted
   or altered by "Limpar", and no new row is created by it either (pure
   client-side reset, no server round-trip).
4. Confirm the conversation remains open with no navigation required to use
   "Limpar".

## I. Guided knowledge-CRUD inputs and transformar em Q&A [V3-8, V3-1×V3-8]

1. Open the create/edit Q&A form; confirm the category field is a `<select>`
   sourced from `GET /operator/knowledge/categories`, reflecting a category
   another operator just created (no client-side staleness).
2. Create a new category inline; confirm it appears in the registry
   immediately and is usable on the same form without a page reload.
3. Confirm the `Tabela` dropdown lists exactly `ALLOWLISTED_TABLES`'s keys
   and never an unlisted name.
4. Select a table; confirm `Filtro`/`Colunas de saída` builders are
   populated only from that table's real columns via the new
   `dynamic-tables/{table}/columns` endpoint — never hand-typed JSON.
5. Request columns for a non-allowlisted table name directly against the
   API; confirm `404`, and confirm the implementation never falls through
   to a raw `information_schema` query for an arbitrary name.
6. On a generation tagged `edit`, click "Transformar em Q&A"; confirm the
   create form opens pre-filled with the customer's message as `question`,
   the sent text as `answer_markdown`, and the generation's `category_slug`
   as the suggested category.
7. Confirm no `content.qa_entries` row exists until the operator explicitly
   confirms/submits the pre-filled form (acceptance outcome 9a).

## J. Automatic-draft countdown indicator [V3-9]

1. With no pending uncovered customer activity, confirm
   `automatic_draft_eligible: false` and no countdown is shown.
2. After a new customer message, confirm `automatic_draft_eligible: true`
   and `automatic_draft_seconds_remaining` starts at
   `AUTOMATIC_TRIGGER_IDLE_SECONDS` and counts down, resyncing each poll.
3. Send another customer message before the countdown reaches zero; confirm
   the countdown resets, matching V2-7's existing debounce-reset behavior
   exactly (no divergent clock).
4. Let the countdown reach zero; confirm the UI shows a distinct "gerando…"
   state, not a stale "0", until the next poll's `latest_generation`
   confirms the generation landed.
5. Background the tab past the threshold and resume; confirm the countdown
   never displays a negative value.
6. Confirm the countdown itself never triggers a generation — it only
   reflects server-computed state from `evaluate_automatic_trigger`'s
   existing guard; rerun V2 `acceptance.md` §D (typing-debounce) to confirm
   no regression.

## K. Scroll to top on evidence selection [V3-10]

1. Run a manual search returning several results scrolled below the fold;
   click "Selecionar" on one; confirm the page scrolls to the top and the
   draft panel is visible without further scrolling.
2. While the resulting draft/evidence state is displayed, let a 2-second
   poll refresh unrelated conversation state; confirm the scroll position
   is not yanked back to top by that unrelated re-render.
3. Confirm "Gerar rascunho" and regenerate-with-instruction do **not**
   trigger this scroll (scoped to evidence selection only, per `plan.md`
   §13's resolution).

## L. Confirm before closing a conversation [V3-11]

1. On the customer page, click "Encerrar conversa"; confirm a confirmation
   prompt appears and the conversation is **not** yet closed.
2. Choose "Retornar e continuar conversa"; confirm the conversation's
   status and all other state are completely unchanged, and no request was
   sent to the close endpoint.
3. Confirm the close action; confirm the conversation closes exactly as
   before V3 (no backend/API change).
4. Repeat 1-3 on the operator page.

## M. Post-conversation satisfaction survey [V3-12]

1. Attempt to submit a satisfaction response against a conversation that is
   not yet `CLOSED`; confirm `409 NOT_CLOSED`.
2. Close a conversation (per §L), then submit a score (1-5) and
   `resolved` (true/false); confirm `201` and that `category_slug` matches
   the conversation's actual most-recent categorized generation.
3. Submit a second response against the same conversation; confirm `409
   ALREADY_SUBMITTED`.
4. On the customer page, dismiss/skip the survey without answering; confirm
   no request is sent and the page does not re-prompt.
5. Confirm skipping never blocked or delayed the close that already
   completed in step 2/§L.

## N. Security negative checks (extends V1/V2 §I)

- every new operator endpoint (mark-incorrect, escalate, categories,
  dynamic-tables, evaluation cases) rejects a request without a valid
  operator bearer, and rejects an operator not assigned to the conversation
  where assignment-gating applies;
- the new public endpoint (satisfaction) rejects a request without a valid,
  conversation-bound token, and the raw token is never persisted/logged;
- column introspection never accepts a table name outside
  `ALLOWLISTED_TABLES`, under any input including path-traversal-style or
  SQL-metacharacter-laden table names;
- `instruction_text`/`manual_search_text` are absent from every
  public/customer-facing response schema, confirmed by a full response-body
  scan across `/public/*` routes.

## O. Quality gates

- backend tests pass (including new V3 suites);
- frontend tests pass;
- E2E critical flows pass, including the new scenarios in `tasks.md`
  T131-T132;
- type/lint gates pass;
- `contracts/openapi.yaml` (V3 delta) matches implementation;
- the SQL `CASE` expressions in `docs/metrics/v3_queries.sql` agree with
  `classify_generation()`'s Python logic against the same fixture data
  (`tasks.md` T111);
- no material V3 spec/plan/code divergence remains (`analysis.md`).

## P. V1/V2 invariant regression (confirm unchanged under V3)

- explicit human send remains the only path to a customer-visible operator
  message, for every generation trigger and every new V3 action
  (quick-approve, regenerate-with-instruction);
- append-only audit remains true for every new V3 event type;
- no chain-of-thought is persisted anywhere in the new `ai_generations`
  columns, `content.evaluation_cases`, or
  `conversation_satisfaction_responses`;
- capacity (max-4), take-over, citation exposure, and multiline rendering
  are unaffected by the V3 changes (spot-check, not a full rerun of V1/V2's
  own scenarios) — this is `spec.md` acceptance outcome 7.
