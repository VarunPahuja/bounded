# ADR-0008: MAX_AMOUNT_PAISE bounds every symbolic amount

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

BMC requires every free variable to be bounded, or the search space is
infinite and Z3 returns `unknown` instead of a real `sat`/`unsat`
verdict (z3-bmc skill, "encoding gotchas"). `amount_paise` is a free
`Int` per step in `verify_guard`'s symbolic transition system and needs
an explicit upper bound to keep the search finite. But an `unsat`
result is only a meaningful soundness claim if the bound was never the
reason an attack wasn't found — if the ceiling is too low, "sound" and
"we didn't let Z3 try hard enough" become indistinguishable.

## Decision

Bound `amount_paise` to `[0, MAX_AMOUNT_PAISE]` with
`MAX_AMOUNT_PAISE = 10_000_000` (paise; 100,000 rupees), a fixed
constant in `verifier/model.py`. This is set well above every
`per_txn_cap_paise` / `window_cap_paise` used anywhere in this project's
tests and eval corpus (all in the low tens of thousands of paise), so
the bound is never the binding constraint standing between the search
and a real counterexample.

## Alternatives considered

### Bound tied to the policy under test, e.g. MAX_AMOUNT_PAISE = window_cap_paise
Rejected: makes an attack that needs a single action modestly over cap
indistinguishable from one that needs to blow past it by orders of
magnitude, and ties an encoding constant to per-call policy data instead
of being one fixed, auditable number every reader of the code can check
against every cap in use.

### Unbounded Int
Rejected outright — this is the specific mistake the skill warns about.
`unsat` degrading to `unknown` silently would look identical to a real
proof unless every caller separately checked `solver.reason_unknown()`.

## Consequences

Positive:
- One fixed constant; every UNSAT result in this project carries the
  same meaning without per-call reasoning about whether the bound was
  large enough.

Negative / accepted costs:
- Nothing currently asserts that `MAX_AMOUNT_PAISE` stays comfortably
  above every policy cap in use. A future policy with a cap in the tens
  of millions of paise would silently make its `verify_guard` result
  meaningless — the search would be artificially constrained and no
  error would surface.

## Revisit when

- Any `per_txn_cap_paise` or `window_cap_paise` used in a real policy
  approaches `MAX_AMOUNT_PAISE`'s order of magnitude — at that point add
  a guard rail that raises rather than silently proving nothing, rather
  than only raising the constant.
