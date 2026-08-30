# ADR-0006: Refunds do not reduce month_spend — gross accounting, not net

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

P2 (window cap) tracks cumulative captured value against `window_cap_paise`
within a period. A refund could plausibly restore some of that budget —
"net" accounting, where `month_spend` decreases when a captured order is
refunded — or it could leave `month_spend` untouched — "gross" accounting,
where the cap tracks total value ever moved, independent of what came
back. `verifier/model.py`'s transition relation has to pick one; the two
give different verdicts for the same trace.

## Decision

`month_spend` only increases, on `capture`. A `refund` never decreases it.
The window cap is therefore a ceiling on cumulative captured value moved
within the window, not on net exposure.

## Alternatives considered

### Net accounting: refund reduces month_spend
Rejected: it turns the window cap into something an agent can launder
around. Capture 10,000, refund 10,000, capture 10,000 again, repeat —
under net accounting this is unlimited value in motion through a
"bounded" window, because every refund silently restores the budget the
cap is supposed to protect. It also requires trusting that a refund is a
genuine reversal rather than itself a step in an adversarial sequence,
which is exactly the class of action this project treats as untrusted
until proven compliant.

## Consequences

Positive:
- The window cap is a true ceiling on total value moved, provable by BMC
  without reasoning about refund authenticity.
- Simpler invariant: `month_spend` is monotonic, one direction, one rule.

Negative / accepted costs:
- A legitimate merchant flow — capture 10,000, refund it in full, then
  want to capture another legitimate 10,000 in the same window — gets
  blocked by the window cap even though net exposure is zero. This is a
  deliberate, conservative choice, not an oversight, and it narrows the
  claim: the mandate language and the demo describe the cap as
  "cumulative captured value in the window," never "net spend." Getting
  this wrong in the pitch is an overclaim.

## Revisit when

- The eval corpus (Phase 6) produces a false-positive class specifically
  from this gap (capture-then-refund-then-recapture flows), or
- a future `PolicyIR` field explicitly asks for net accounting as an
  opt-in — it should never be the silent default.
