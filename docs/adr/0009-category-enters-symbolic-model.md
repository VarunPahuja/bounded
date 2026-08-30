# ADR-0009: Category (P4) enters the symbolic model as a depth-1 check

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

Phase 1 left P4 (category restriction) entirely outside `verify_guard`'s
symbolic model. `order_id` needed `NUM_ORDER_SLOTS` — an artificial
bound — because any string could be an order (ADR-0007), and category
was assumed, without checking, to need the same treatment. Phase 2
moves `encode.py` onto `PolicyIR`, which already carries
`allowed_categories`/`blocked_categories`. Leaving P4 permanently
replay-only while P1–P3 all have genuine BMC proofs would be a
permanent, unstated asymmetry baked into the one type that now drives
the whole encoding — the "P1 through P4" framing already established in
Phase 1's docstrings and ADRs would be one property short of true.

## Decision

Category enters the symbolic model as `category_idx`, a bounded `Int`
per step — same shape as `order_idx` — but its domain is determined by
the *policy being encoded*, not a fixed global constant: the vocabulary
is exactly the category names the policy mentions in
`allowed_categories`/`blocked_categories`, plus one sentinel index
(`OTHER`) for any category the policy doesn't name (`OTHER` is
admissible only when there's no allowlist — an unset allowlist means
"anything not explicitly blocked is fine").

Checked as a depth-1 check (`_check_p4`, `verifier/bmc.py`), symmetric
to `_check_p1`: like the per-transaction cap, category admissibility
doesn't depend on accumulated state — whether this capture's category
is allowed has nothing to do with prior steps. `sound_capture_guard` is
extended to enforce it; `naive_capture_guard` stays unaware of it, the
same way it's unaware of the window cap — "naive" means "checks less
than the policy needs," and category is one more thing it doesn't check.

## Alternatives considered

### Leave category replay-only, permanently
Rejected: makes P4 the one property in "P1 through P4" that can never
be proven, only narrated after the fact from a scenario that already
happened. That gap was tolerable while `HandPolicy` was a hand-picked
subset built before the real IR existed; it stops being tolerable once
`PolicyIR` — carrying the field, presented to a merchant, potentially
even described in the demo — is the only input type Phase 2 accepts.

### Bound category with a fixed global constant, the same way NUM_ORDER_SLOTS bounds orders
Rejected: orders are genuinely open-ended real-world identifiers,
which is why `NUM_ORDER_SLOTS` needed its own ADR-0007 defending an
arbitrary choice. A policy's admissible/blocked categories are not
open-ended — they're a small, exact, known set the moment the policy
exists. A fixed global bound would either be too small (silently
truncating a policy that names more categories than the constant
allows) or an arbitrary number defended the way ADR-0008 had to defend
`MAX_AMOUNT_PAISE`, for a problem that doesn't actually require an
arbitrary bound: the policy itself already provides the exact one.

## Consequences

Positive:
- P1 through P4 is now a uniformly provable claim — no property carries
  a permanent asterisk saying "checked by replay only."
- No new arbitrary constant, no new ADR needed to defend a magic number.

Negative / accepted costs:
- The category vocabulary — and therefore `category_idx`'s bound — is
  policy-dependent, not a fixed global like `NUM_ORDER_SLOTS`.
  `build_symbolic_system` now takes the full `PolicyIR`, not just
  `horizon`, so it can compute that bound. This is a real API change
  from Phase 1, not just a type-hint swap.

## Revisit when

- A future property needs to reason about category *cumulatively* —
  e.g. "no more than X captures of category Y per window" — that needs
  category-indexed state (a captured/refunded-per-category array,
  analogous to per-order state), which is a materially bigger change
  than the depth-1 check made here.
