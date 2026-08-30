# ADR-0007: NUM_ORDER_SLOTS = 2 bounds the symbolic order universe

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

`verify_guard` needs `order_id` in the search space so Z3 can discover
attacks that split refunds or captures across orders, not only within
one. Real order IDs are unbounded strings; a bounded-Int BMC encoding
needs a finite domain to stay in `Int` arithmetic (per CLAUDE.md: no
`Real`, and per the z3-bmc skill: every free variable must be bounded or
`unsat` degrades to `unknown`).

## Decision

Model the order universe as `NUM_ORDER_SLOTS = 2` symbolic slots
(`verifier/model.py`), each carrying its own `captured`/`refunded` Int
state. `order_idx` is a free `Int` in `[0, 2)`. Every soundness claim
`verify_guard` produces is therefore scoped: **sound over traces that
touch at most 2 distinct orders within the horizon.** This scope has to
be stated wherever a `verify_guard` UNSAT result is reported as a
soundness claim — it is not a universal proof over arbitrary order
counts.

## Alternatives considered

### Z3 Array or uninterpreted sort for unbounded order identity
Rejected for Phase 1: array theory with a symbolic index is materially
harder for Z3 to reason about and slower to decode into a readable
trace, in exchange for coverage this project doesn't need yet — a guard
bug that manifests only when 3+ orders interact simultaneously, as
opposed to any bug that already shows up with 2. Every attack class in
MASTER.md's threat model (split-transaction, split-refund) generalizes
from the 2-order case; a guard unsound at 2 orders is unsound, full
stop, and a guard sound at 2 orders needs an inductive argument BMC
alone doesn't give to claim soundness at N orders anyway.

### NUM_ORDER_SLOTS = 1
Rejected: collapses to a single order, so it cannot represent any
cross-order attack — e.g. an agent that spreads captures across two
orders specifically to evade a naive guard whose accounting is scoped
per-order. That is a real attack shape this project claims to catch and
a 1-slot model would make it structurally unrepresentable, not just
untested.

## Consequences

Positive:
- Cheap, tractable encoding; catches same-order split attacks and
  simple 2-order cross-order attacks, which is what the current test
  suite and eval corpus target.

Negative / accepted costs:
- An UNSAT result from `verify_guard` says nothing rigorous about a
  guard that is broken only when 3+ orders interact (for example, an
  aggregate computed from a fixed-size cache that overflows past 2
  entries). This has to be a caveat on the claim, not a footnote.

## Revisit when

- The real interceptor's per-order state representation (Phase 3/4) has
  an implementation detail whose correctness depends on order count
  (a fixed-size cache is the obvious failure mode), or
- Phase 6 red-teaming specifically targets attacks spanning 3+ orders.
