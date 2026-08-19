# Cross-Artifact Analysis: Dynamic Pricing and Guided Booking Selection

## 1. Pre-implementation consistency review (2026-08-19)

Performed per `AGENTS.md`'s required SDD flow, step 3, before any code was
written. One real finding, corrected immediately (not left for
implementation to silently work around):

- `data-model.md`'s first draft proposed matching customer text against
  `Message.body`/generation `draft_text` to detect "was the preceding
  sent message a GB-2 confirmation question" (GB-4's trigger condition).
  Cross-checking `infrastructure/models.py` found `Message` already
  carries `source_generation_id` — a direct FK set on every sent draft —
  which answers the same question exactly and more reliably, with zero
  new lookup mechanism. `data-model.md` §3 and `plan.md` §5.3 were
  corrected before `tasks.md` was written, so no task ever targeted the
  discarded design.

`spec.md`'s FR labels (PL-1..4, PM-1..4, GB-1..5) were confirmed to each
have a corresponding `plan.md` section and `tasks.md` task before
implementation began (`checklists/traceability.md`).

## 2. §6 boundary verification (post-implementation)

Every item `spec.md` §6 declares out of scope was checked against the
actual diff, not just re-asserted:

- **Constitution Amendment 1.1.0 / AA-10 not extended**: `git diff` on
  `booking_script/service.py` and `booking_script/parsing.py` is empty.
  `test_005_booking_script_containment.py` proves no import coupling in
  either direction, source-level, independent of git state (durable past
  this feature's own commit).
- **No `insurance_lookup`/`convenio` change**: `documents/qa/qa-catalog.jsonl`
  diff touches exactly QA-028 through QA-034 (7 lines); QA-035/036/037 are
  untouched. `NAMED_RESOLVERS` gained exactly one new entry
  (`price_lookup`); `insurance_lookup` was never added.
- **No `payment_simulator` resolver, no payment link/timer**: PM-3's
  content correction describes AA-10's existing sim/não step; no new
  resolver, no new code path claims to handle payment.
- **No real booking/holds/identity/payment**: GB-1/GB-2/GB-4 write only to
  the new `appointment_offer_presentations` table (offer metadata already
  shown to the customer) and produce `AIGeneration` rows — `scheduling.*`
  write surface is unchanged from 004 (still only `scheduling/seeding.py`
  inserts `schedule_slots`; GB code never imports it).
- **No scheduling CRUD**: no new operator-facing schedule-editing endpoint
  was added.

## 3. Mid-implementation correction: embedding-threshold calibration

Documented in full in `acceptance.md`'s "genuine mid-implementation design
correction" section. Summary for this document's purpose: `plan.md`'s
initial threshold design was evidence-free (a guessed constant by
analogy), caught by this feature's own acceptance protocol (the real-
provider smoke test) before the record was written, and corrected with
measured evidence documented inline in both `plan.md` and
`guided_booking.py`. This is the kind of finding a convergence review
exists to catch — recorded here rather than smoothed over.

## 4. Regression-test corrections (expected, not incidental)

Two pre-existing tests asserted "`price_lookup` still abstains" as part of
004's own unimplemented-resolver regression coverage. Now that PL-1
implements `price_lookup` for real, those specific assertions are
necessarily superseded — this is proof the feature works, not a broken
test. Both were updated to target `insurance_lookup` instead (still
genuinely unimplemented), preserving the original tests' intent (catching
an *accidental* widening of what resolves) rather than deleting the
coverage:

- `tests/test_dynamic_pattern_dispatch.py::test_unimplemented_resolver_name_still_abstains`
- `tests/smoke_v4_appointment_availability.py`'s equivalent HTTP-level check

Both updates are documented inline in the affected files, pointing back
to this package.

## 5. Full-suite convergence

- Backend `ruff check .`: clean.
- Backend `mypy customer_care/`: clean (49 files). `mypy` against `tests/`
  carries the same pre-existing 75-error baseline (confirmed via `git
  stash` comparison) plus zero new errors after this feature's touched
  test files were corrected.
- `pytest tests/`: 139 passed (was 129 before this feature; +10 net new:
  6 `test_price_lookup_resolver.py`, 12 `test_guided_booking.py`, 2
  `test_005_booking_script_containment.py`, minus 0 removed — the count
  also reflects `test_appointment_seeding.py`'s 8 tests which happened to
  be excluded from one intermediate run by operator error, not by design;
  the final full run includes them).
- All 17 `smoke_*.py` scripts pass (16 pre-existing + `smoke_v5_guided_booking.py`),
  run in the dependency order 004's own acceptance record established.
- One pre-existing local-environment failure (`smoke_resilience.py`,
  stale Playwright fixture data from unrelated prior sessions) confirmed
  present identically on the pre-005 baseline via `git stash` — not a
  regression this feature introduced, not fixed by this feature either
  (out of scope: it is local dev-database hygiene, not a code defect).

## 6. Final verdict

**GO**, 2026-08-19. `spec.md` §8's 10 acceptance outcomes all pass with
real evidence (`acceptance.md`); `spec.md` §6's every "not authorized"
boundary is verified intact by structural, not just behavioral, proof;
the one real design defect found during implementation (threshold
calibration) was corrected before this record closed, with the evidence
that caught it preserved rather than discarded.

## 7. Correction convergence (2026-08-19, D-033)

Real use immediately after §6's verdict found two defects §1-§5's own
analysis had not anticipated: embedding similarity cannot resolve ordinal
replies at all (not a calibration gap — a category error, comparing
positional language against content-based descriptions), and the
standalone confirmation step created a dead end rather than a continuous
flow. Both are now fixed (spec.md §10, `acceptance.md`'s Correction
record).

**Boundary re-verification, same rigor as §2 above, re-run after the
correction:**

- `git diff` on `booking_script/service.py`/`parsing.py`: still empty.
- Import-graph containment re-verified, now precisely (not "zero
  coupling" — D-033 introduces one disclosed import of two pure functions
  from `booking_script.parsing`): `test_005_booking_script_containment.py`
  asserts this via `ast` parsing specifically because a raw-text scan
  falsely flagged the module's own docstring (which explains, in prose,
  why `send_scripted_message` must never be called) — a real, if minor,
  test-design lesson from this correction: verify source *structure*, not
  substring presence, when the forbidden name is also worth explaining in
  documentation.
- `conversation.booking_script_step` is confirmed never read or written
  by any D-033 code (`guided_booking.py`'s own new
  `_latest_operator_message_trigger`/`pending_redaction_step`/
  `interpret_cpf_reply`/`interpret_payment_reply`/`advance_guided_booking`
  all key off `Message.source_generation_id` and `ai_generations.trigger`
  instead) — grep-verified, not just asserted.
- `smoke_v4_booking_script.py` (AA-10's own full autonomous script) re-run
  unmodified and still passes byte-for-byte identically, confirming this
  correction did not regress the one path it deliberately leaves alone.

**A second, genuine finding surfaced only by attempting the real
end-to-end smoke test** (not by static review): the original correction
design assumed `interpret_cpf_reply`/`interpret_payment_reply` could read
the customer's raw reply from the already-persisted `Message.body` at
draft-generation time. This is impossible by construction — that value is
redacted at message-creation time, before any later draft-generation call
could ever see it. Caught immediately by writing the real HTTP smoke test
this correction's own acceptance protocol requires, not discovered later.
Fixed by moving the interpretation to message-creation time itself
(`advance_guided_booking`, mirroring `advance_booking_script`'s own
call-site shape) and staging only the safe, already-computed result.

## 8. Final verdict (correction)

**GO**, 2026-08-19. Both real defects are fixed with real evidence
(`acceptance.md`'s Correction record); AA-10's constitutional boundary is
re-verified structurally intact; the correction's own narrow, disclosed
exception to the original "zero coupling" claim is verified precisely.
