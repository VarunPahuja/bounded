# ADR-0011: verify_action's soundness is inductive, not a fresh horizon-k proof per call

- Status: Accepted
- Date: 2026-08-31
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

Phase 4's interceptor has to decide, for one concrete proposed action and
the real current account state, ALLOW or BLOCK — and per CLAUDE.md, the
solver decides, never Python arithmetic re-deriving the same answer.
`verify_guard` (Phase 1/2) already proves guard soundness, but always from
a zero starting state and over a symbolic, adversarially-chosen sequence —
it answers "can any guard-admitted trace of up to k steps, starting from
nothing, breach the invariant?", not "is this one action, from where the
account actually is right now, safe to admit?"

Running a fresh horizon-k adversarial search on every proposed action,
seeded from the real state, was the other option: prove not just that this
action is safe, but that no k-step continuation from here could be. That
is strictly more than the interceptor needs to answer per action, and it
would make every `propose_action` call pay for a search whose result is
already implied by something proven once.

## Decision

`verify_action` (`verifier/bmc.py`) checks a single action with a depth-1
Z3 query: state pinned to the real reconstructed values, the action's
fields pinned to its concrete values, and `solver.check()` on
`guard(...) AND invariant_holds(next_state)`. No search — every variable
is concrete, so the query has one answer, just computed via Z3 rather
than hand-written arithmetic (`_replay_violated_property`'s domain,
which is deliberately never called verification).

This is sound by induction, not by a fresh per-call proof:

1. `verify_guard` establishes once (at policy-load time, from the zero
   state) that `guard` never admits a horizon-k sequence that breaches
   the invariant.
2. `sound_capture_guard` / `sound_refund_guard` decide admissibility using
   only the current step's state and the current action — nothing about
   *how many* steps came before, or in what order. There is no
   horizon-specific term in either function.
3. The real current state, reconstructed from the ledger
   (`rail/interceptor.py`), already satisfies the invariant — by the same
   induction: every action that ever executed did so because a prior call
   to this same check admitted it from a prior invariant-satisfying
   state, and genesis (state = 0) satisfies it trivially.
4. Therefore: admitting one more guard-compliant action from that real
   state cannot break the invariant either — the one-step check IS the
   inductive step of the exact property `verify_guard` proves the base
   case and closure for.

## Alternatives considered

### Re-run verify_guard (or an equivalent horizon-k search) per action, seeded from real state
Rejected: strictly more computation for an answer already implied by (1)-(4)
above, and it changes the character of the runtime guarantee from "this
action is safe" to "no k-step continuation from here is unsafe" — a
claim `propose_action` doesn't need to make per call, since it only ever
admits one action before re-checking the (now-updated) real state on the
next proposal. Continuously re-verifying the whole future is the offline
soundness proof's job, not every request's.

### Skip Z3 entirely, decide in plain Python (`_replay_violated_property`)
Rejected outright — this is the one rule the project cannot break. The
per-action arithmetic in `_replay_violated_property` is real code doing
the same sums, but it exists for the eval harness and demo narration and
is explicitly never permitted to be the enforcement decision. Routing the
concrete check through Z3 keeps `verify_action` and `verify_guard`
provably the same guard functions making the call, so there is no drift
between what was proven sound offline and what is enforced live.

## Consequences

Positive:
- `propose_action` stays cheap per call (a pinned depth-1 SAT check, not a
  horizon-k search) while still routing every decision through Z3.
- The inductive argument only holds as long as the *same* guard object
  (`compose_guard(sound_capture_guard, sound_refund_guard)`) is used both
  to certify soundness via `verify_guard` and to decide live via
  `verify_action` — `rail/interceptor.py` hard-codes this single guard
  constant rather than accepting a caller-supplied one, so the two can't
  drift apart by construction.

Negative / accepted costs:
- The induction is only as good as its base case and closure actually
  being checked: if `verify_guard` is never run for a policy (or is run
  against a *different* guard than the one wired into the interceptor),
  `verify_action`'s per-call soundness claim is unearned — nothing in
  `propose_action` currently re-verifies that `verify_guard(policy, GUARD)`
  returned SAFE before serving live traffic on that policy. This has to
  be a deployment-time discipline (verify-then-serve), not something this
  ADR can enforce in code without adding a real dependency between policy
  activation and a `verify_guard` call — worth revisiting if this project
  grows a policy-activation path (Phase 5+) rather than constructing
  `PolicyIR` directly in tests.
- Inherits ADR-0007's 2-order-slot scope: `verify_action` only ever
  reasons about the one order the proposed action targets (pinned to
  slot 0) plus an unused slot 1 — consistent with, not broader than,
  what `verify_guard` already proved sound over.

## Revisit when

- Phase 5+ adds a real policy-activation step, at which point
  `verify_guard(policy, GUARD)` returning SAFE should gate whether a
  policy is servable at all, closing the "unearned induction" gap above.

## Amendment (2026-09-01): the induction's unstated precondition

Step 3 of the induction ("the real current state ... already satisfies the
invariant") is true only if every action that ever moved money at Razorpay
did so *through* `propose_action`. The AST test enforcing "the solver
decides" (CLAUDE.md's one rule) checks that no code path in this repo
bypasses the guard. It cannot see money that moves at Razorpay with no
corresponding `Action` in our system, because there is no code path for it
to catch — the movement never touches this repo at all. Two concrete ways
that happens:

1. A refund issued from the Razorpay dashboard, by a human with account
   access, outside the interceptor entirely.
2. A webhook for an event the interceptor never proposed — the payload
   `reconstruct_state` would need to count, but its own predicate is built
   to exclude exactly this shape. Per its docstring
   (`rail/interceptor.py`'s `reconstruct_state`), an entry needs both
   `action` and `razorpay_payment_id` set to count; webhook-recorded
   entries carry `razorpay_payment_id` but never an `Action`, so they are
   structurally invisible to the sum. That exclusion is deliberate and
   correct for its stated purpose — it is what stops a webhook echo of a
   capture the interceptor already recorded from being double-counted.
   It is the same property, applied to an entry with no matching
   interceptor-side record at all, that makes genuinely out-of-band money
   invisible too.

If either happens, `reconstruct_state` returns a total strictly lower than
what Razorpay actually holds. `verify_action`'s depth-1 check then reasons
from a real-current-state value that is wrong, and can return ALLOW for an
action that pushes true spend past the policy cap while the ledger's own
math looks correct throughout.

This is not fixed in code by this amendment. Soundness as proven here
holds under the precondition that **the interceptor is the sole path
through which money moves at Razorpay** — no dashboard actions, no
unproposed webhook-originating movement. That precondition is external to
this repo and unenforceable by it; see `docs/THREATS.md` for the named
threat and its consequence.
