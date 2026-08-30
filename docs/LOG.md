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

