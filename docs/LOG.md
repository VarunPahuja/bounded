# LOG

Append-only. One entry per phase: date, what shipped, what broke, what changed my mind.

## 2026-08-30 — Phase 0: Scaffold and contracts

**Shipped:** repo public on GitHub (`VarunPahuja/bounded-`), MIT license, `CLAUDE.md`
and `docs/MASTER.md` in place, `contracts/models.py` frozen with all required
types (`Mandate`, `PolicyIR`, `Action`, `ActionType`, `VerificationResult`,
`Counterexample`, `LedgerEntry`, plus `CounterexampleStep` and the supporting
enums). `docs/CONTEXT.md` written. ADR-0001 (Z3 over Cedar/CEL) and ADR-0005
(LLM proposes, solver decides) written and accepted. All 14 Phase 0 tests
green: round-trip through `model_dump_json()`, `Action` rejects
non-positive amounts, `PolicyIR` rejects a monthly cap below the per-txn cap.

**Broke:** nothing — Phase 0 is scaffolding and types, low-risk by design.
The gap wasn't a bug, it was sequencing: the models and tests landed before
the ADRs and LOG.md did, which inverts MASTER.md's own instruction to write
ADR-0001 and 0005 *before* any code. Caught on a manual phase check rather
than a hook, since nothing currently enforces "ADR exists" before "test
passes."

**Changed my mind:** nothing on scope or design. Confirmed the ADR-writing
step needs to happen at the start of a phase checklist, not the end, given
it slipped once already.

## 2026-08-30 — Phase 1: the Z3 core

**Shipped:** `verifier/model.py`, `encode.py`, `explain.py`, `bmc.py`.
Two entry points, deliberately not interchangeable:

- `verify_guard(policy, guard, horizon=8) -> VerificationResult` — true
  BMC. Symbolic action type, order, and amount per step, admitted only by
  a `guard` predicate conjoined into the transition relation. Runs a
  cheap depth-1 check for P1 (can the guard admit a single over-cap
  capture?) plus a horizon-k search for P2/P3 (can a sequence of
  individually-admitted actions collectively breach the window cap or
  refund soundness?). This is the proof the project's claim rests on.
- `replay_trace(policy, scenario, horizon=8) -> Counterexample | None` —
  plain Python arithmetic over one concrete, already-known action
  sequence. No search, no solver, no soundness claim. For the eval
  harness and demo narration only. Never called verification, in code
  or in docs.

12 tests green in `tests/verifier/`, plus `test_agreement.py` (10
scenarios asserting `replay_trace` and `verify_guard` agree, since they
are two independent implementations of the same accounting rules and
drift between them would mean the demo narrates one thing while the
proof proves another). Full suite: 28 tests, ~1s. `verify_guard`'s
soundness proof at k=8 (`test_cumulative_guard_is_sound`, both caps
active) solves in 0.10s wall-clock.

ADR-0006 (refunds are gross, not net), ADR-0007 (`NUM_ORDER_SLOTS = 2`,
soundness scoped to traces touching at most 2 orders), ADR-0008
(`MAX_AMOUNT_PAISE` bound and why it has to sit well above every cap in
use) — all written and accepted.

**Broke:** the real one. My first implementation of Phase 1 was wrong
in a way that would have quietly gutted the project's central claim.
MASTER.md's Phase 1 spec, read literally, described unrolling a
transition system and checking properties — I built exactly that, but
fed it a fully concrete, already-decided sequence of actions and let Z3
confirm the arithmetic. That's not bounded model checking. It's a
Python loop wearing an SMT solver as a costume: every input is known in
advance, so "UNSAT" means nothing more than "I added these numbers up
correctly." It proves nothing about what a guard would *let an agent
do* — which is the actual claim in MASTER.md section 1 ("no reachable
sequence of agent actions... can breach it"). I got as far as writing
eight passing tests and a plausible-sounding writeup before this was
caught, entirely because the reviewer asked what property was actually
being proven rather than trusting that green tests meant the thesis
held.

The fix: the guard predicate — the thing that decides whether to admit
a proposed action — has to live *inside* the transition relation, and
the actions themselves have to be free variables Z3 chooses
adversarially, bounded only by what the guard and the encoding's finite
domains (`NUM_ORDER_SLOTS`, `MAX_AMOUNT_PAISE`) allow. `verify_guard` is
that. The renamed `replay_trace` is what my original design actually
was, kept because it's still useful — just never again described as
verification.

Two smaller breaks surfaced while building the corrected version:

1. My first `verify_guard` test scenarios asserted `SAT` without
   requiring the counterexample to be more than one step. A guard that
   checks nothing at all would pass those tests too — the assertion
   `len(trace) >= 2` (plus "every individual action is within the cap
   it's supposed to enforce") is what actually forces the test to prove
   the *compositional* bug, not just the absence of a guard.
2. `GuardFn` initially inferred its position in the trace from call
   order — a mutable closure counter would have worked for the main
   horizon loop alone, but `verify_guard`'s P1 pre-check calls the
   guard once more, on a separate isolated system, before the main loop
   starts. That extra call would have silently desynced any
   scenario-pinning guard. Caught while building the agreement test,
   fixed by making the step index an explicit parameter instead of an
   inferred one.

**Changed my mind:** assumed `VerificationResult` would need a contracts
amendment to carry a bound alongside a sound/unsound verdict. It didn't
— `horizon: int` and `properties_checked: list[str]` were already there
from Phase 0, just under `verdict`/`latency_ms` instead of the informal
names I'd been using in conversation. No amendment needed; the frozen
file was already right.

## 2026-08-30 — Phase 2: the typed IR and transpiler

**Shipped:** `HandPolicy` deleted outright — `verifier/encode.py`,
`bmc.py`, `model.py` take `contracts.models.PolicyIR` directly, no
converter. The alternative (a converter layer) was rejected before any
code was written: `PolicyIR`'s overlapping fields already match
`HandPolicy`'s names exactly, so a converter would have been pure
indirection whose only real function was reintroducing, one layer up,
the exact drift risk `test_agreement.py` exists to catch — a field
added to `PolicyIR` and forgotten in the converter, silently never
reaching `encode.py`.

P4 (category) entered the symbolic model (ADR-0009): `category_idx`,
bounded by the policy's own named categories plus one `OTHER` sentinel
— no arbitrary constant needed, unlike `NUM_ORDER_SLOTS`, because a
policy's allowed/blocked categories are already a small, exact, known
set the moment the policy exists. Checked as a depth-1 check
(`_check_p4`), symmetric to P1. `sound_capture_guard` now enforces it;
`naive_capture_guard` still doesn't, on purpose.

**The window question, argued properly (ADR-0010).** `PolicyIR.window`
(day/month) is read but the BMC model has no calendar-time dimension —
`window_cap_paise` is proven as a cumulative cap over the traced
horizon, regardless of which window value is set. This is a different
class of problem from the two genuinely out-of-scope fields
(`max_txn_count`, `require_human_above_paise`): those are *visibly
absent* from `properties_checked`, so nobody mistakes them for
enforced. `window` is read, changes what a merchant would believe
`window_cap_paise` means, and has zero effect on what's proven — a
silent policy-widening bug sitting just outside what
`test_every_ir_field_encoded` can see, since the field *is* touched by
code, just not honored the way its name implies.

Two options on the table: reject window values the model can't honor
at validation (cheap, but since *neither* day nor month gets real
calendar treatment yet, a faithful version would have to reject the
field whenever it's set at all — making it unusable rather than
clarified, for a field that gets genuine meaning once Phase 3/4 supply
a real starting state from the ledger); or report what was actually
proven on the result itself. Went with the second:
`properties_checked`'s P2 entry is now `"P2[window=month,horizon-
cumulative]"` rather than a bare `"P2"` — the caveat travels with the
verdict on the same field every consumer already reads, matching the
pattern already established for `horizon` in Phase 1. Locked down by
`test_window_semantics_are_reported`: a DAY policy and a MONTH policy
must produce distinguishable results, or the test fails.

**Broke:** while validating that the strengthened
`test_every_ir_field_encoded` (see below) actually catches a real
regression rather than passing vacuously, I disabled
`sound_capture_guard`'s per-transaction check with a scratch script,
confirmed the test failed correctly, and then ran `git checkout --
verifier/encode.py` to restore it — except `verifier/encode.py` had
never been committed with any of this phase's work yet, so the
checkout silently reverted the entire file to the pre-Phase-2, still-
`HandPolicy`-importing version, deleting the whole rewrite from the
working tree. No data was lost — the content was still in-session and
got rewritten byte-for-byte — but it's a reminder that "restore this
one file" and "discard everything uncommitted in this file" are the
same command with no warning between them, and I should have diffed
before running it, not after.

**Changed my mind, twice, in the same direction:** first drafted
`test_every_ir_field_encoded` as a membership check against two
hand-maintained lists (`_ENCODED_FIELDS`, `_DEFERRED_FIELDS`) — caught,
correctly, as a tripwire that a field could pass by sitting in the
right list with a plausible comment, never actually reaching a
constraint. Strengthened to `test_encoded_fields_actually_change_
constraints`: for each field, two policies differing only in that
field must produce a different Z3 constraint string. Doing this
surfaced a real architectural fact worth stating plainly: `encode()`
itself only builds the bare transition skeleton — `per_txn_cap_paise`
and `window_cap_paise` never reach it at all, they're consumed by the
guard functions and `invariant_holds`, only when `verify_guard` runs a
real check. Only the category fields change `encode()`'s own output.
That's correct, not a bug — a "guard" has to stay swappable between
naive and sound, so cap logic can't be unconditionally baked into the
base transition system — but it meant the differential test had to
probe whichever function actually consumes each field, not `encode()`
uniformly, with the mismatch documented rather than smoothed over.

## 2026-08-31 — Phase 3 Part B: the rail, and what building it required

**Shipped:** `rail/config.py` (boot guard refusing non-`rzp_test_` keys,
`.env` via `python-dotenv`, a `masked_key_id()` helper so nothing ever
prints the key secret), `rail/razorpay_client.py` (`create_order`,
`attempt_capture`, `refund`, `fetch_payment`, `verify_payment_signature`),
`rail/webhook.py` (`verify_webhook_signature` over raw bytes,
`process_webhook_event` with retry-on-chain-contention plus a UNIQUE
constraint for dedupe), a UNIQUE constraint on `ledger_entries.entry_id`,
`scripts/seed.py`. All against real Razorpay test mode, nothing mocked.

**The agent's action space got redefined mid-phase, and it's more
accurate, not smaller.** The original plan had the agent creating
payments. In a real Razorpay merchant setup the customer creates
payments; the merchant (or its agent) captures, refunds, and pays out —
all server-side, no browser. So Phase 3 split in two: a setup step
outside the agent's path (a human pays a manually-captured order via
Checkout, once, ahead of time — `scripts/seed.py` prepares the orders,
does not touch the agent), and the rail itself, which is exactly
capture/refund/fetch/webhook — the surface an unbounded agent is
actually dangerous on, because it already has money sitting authorized
in the merchant's account.

**`createUpi` (S2S/headless UPI collect) does not work with these test
keys.** `POST /v1/payments/create/upi` returns a genuine 400 —
`{"error":{"code":"BAD_REQUEST_ERROR","description":"The requested URL
was not found on the server.","metadata":{"order_id":"order_..."}}}` —
confirmed via the SDK and a raw `requests.post` call, with the
`metadata.order_id` proving it reached a real handler rather than
hitting a malformed path. S2S/headless payment creation is a
separately-provisioned integration, gated per-merchant; test-mode API
keys don't get it by default, and enabling it means contacting Razorpay,
not an API call. **This is why payment creation moved outside the
agent's path** — there was no working headless alternative to fall back
to inside it.

**Razorpay's own docs disagree with themselves on the auto-refund window
for an authorized-but-uncaptured payment.** The parameter-level API
reference (`manual_expiry_period`, default and max both `7200` minutes)
and the FAQ page both say **5 days**. The rainy-day capture-settings
overview page says **3 days**, and separately caps the same setting's
max at "3 days" — inconsistent with its own `7200`-minute figure on the
API reference page. Trusted the API reference as authoritative (it's the
actual parameter the backend reads), but the practical takeaway holds
either way: both figures are far longer than a demo beat or an overnight
gap, so `payment_capture: 0` stays and `scripts/seed.py` runs 24-48h
ahead of recording — enough margin to not care which of Razorpay's own
pages is stale.

**UPI is not enabled by default in test-mode Checkout.** Seeding a real
authorized payment required a card — `5267 3181 8797 5449` worked
(MasterCard, credit, mock OTP page); `4111 1111 1111 1111` (the commonly
copy-pasted Visa test number) failed as an **international** card
against an Indian test account. Use `5267 3181 8797 5449`.

**Refunds have a hard floor of INR 1.00 (100 paise), enforced per call,
not in aggregate.** `BadRequestError: The amount must be atleast INR
1.00`. Confirmed the "per call" part empirically, not just assumed it:
against a payment already refunded 200 paise (comfortably over the
floor in aggregate), a further 50-paise refund was still rejected with
the identical error, while a 150-paise refund on the same payment
succeeded immediately after. So the floor is checked per individual
refund call, never against the running total — which means a two-leg
split-refund attack scenario (P3) is fully constructible as long as each
leg clears 100 paise; nothing about the floor makes split refunds
impossible, it just sets a per-leg minimum. `scripts/seed.py` defaults
to Rs 1,000 per seeded order specifically so both a meaningful partial
refund and a two-leg split both sit an order of magnitude above that
floor.

**Resolved: `test_order_capture_refund_live` and `test_failure_handle`
consume human-seeded payment ids, skipped cleanly if unset.** There is
no automatable way to produce a payment in test mode at all — every one
requires either a browser step or the S2S path confirmed blocked above
— so both tests read a payment id from an env var
(`RAZORPAY_TEST_AUTHORIZED_PAYMENT_ID` / `RAZORPAY_TEST_FAILED_PAYMENT_ID`)
and `pytest.skip` with an explicit reason when it's absent, rather than
mocking Razorpay (off the table per CLAUDE.md) or hard-failing `pytest`
for lacking a browser. When seeded, the calls are real, nothing mocked.

**Producing a genuinely `failed` test payment took three attempts, and
the two documented-sounding approaches were both wrong.** What actually
happened, in order:

1. A card OTP entered under 4 digits (the officially documented way to
   "fail the payment") does show "Payment Failed, Retry" client-side,
   but the underlying payment entity never transitions past
   `status: "created"` — no `error_code`, no `error_description`,
   confirmed still stuck there minutes later (not a sync delay).
2. A "declining" test card number surfaced by a web search summary
   (Mastercard `5305 6200 0007 0009`, supposedly simulating
   `authentication_failed`) **authorized successfully** instead —
   exactly the "hardcoded list from a blog post" trap the
   razorpay-testmode skill already warned against, and this time the
   trap was a search-engine AI summary, not a blog post directly.
3. **What worked:** the international-card rejection already noted
   above (`4111 1111 1111 1111` against a domestic-only Indian test
   account) produces a real `status: "failed"` payment with everything
   populated — `error_code: "BAD_REQUEST_ERROR"`,
   `error_reason: "international_transaction_not_allowed"`,
   `error_source: "business"`. This is now the documented way to seed a
   failed payment, in the skill.

