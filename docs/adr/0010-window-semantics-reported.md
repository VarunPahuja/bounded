# ADR-0010: Window granularity is reported on the verdict, not silently ignored

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

`PolicyIR.window` (day/month) is read by `encode.py` but the BMC model
has no calendar-time dimension — `window_cap_paise` is checked as a
cumulative cap over the traced `horizon`, regardless of which `window`
value is set. Left undocumented, this is a materially different problem
from `max_txn_count`/`require_human_above_paise` (handled by the
allowlist-with-reasons pattern in `test_every_ir_field_encoded`): those
two fields are *visibly absent* from `properties_checked`, so nobody
can mistake them for enforced. `window` is read, it changes what a
merchant believes `window_cap_paise` means (a day's spend vs. a
month's), and it has zero effect on what's actually proven. That is the
exact silent policy-widening bug `test_every_ir_field_encoded` exists
to prevent, sitting just outside what that test can see — the field
*is* accounted for in the sense that code touches it, just not honored
in the sense a merchant reading "window: month" would assume.

## Decision

**Option B.** `properties_checked`'s P2 entry is qualified with the
actual window value and an explicit caveat instead of a bare `"P2"` —
e.g. `"P2[window=month,horizon-cumulative]"`. The qualifier travels
with the verdict on the same structured field every consumer of
`VerificationResult` already reads (`properties_checked`), the same
pattern Phase 1 established for `horizon`: a caller cannot report what
was proven without also seeing the bound on the claim.

## Alternatives considered

### Option A: reject any window value the current model cannot honor
Considered seriously, rejected. Since *neither* day nor month gets true
calendar-boundary treatment yet, a faithful version of "reject what
can't be honored" would have to reject `window` whenever it's set at
all — not one value over the other, since neither is more honored than
the other. That makes the field entirely unusable rather than
clarified, for a field that will get genuine meaning once Phase 3/4
supply a real starting-state reconstruction from the ledger with actual
calendar resets. It would also need to live either inside `PolicyIR`'s
own pydantic validator — touching the frozen contracts file, not
approved for this — or as an ad hoc rejection at the `encode()`
boundary, inconsistent with how every other IR field is consumed
(read and reflected in the result, not gatekept at the door).

## Consequences

Positive:
- Day and month stay usable and stay distinguishable in the result
  without touching frozen contracts, and without discarding information
  a caller might reasonably want to log even though it isn't enforced
  yet.
- No new field, no contracts amendment — `properties_checked` is
  already `list[str]`.

Negative / accepted costs:
- `properties_checked` entries are no longer a fixed four-item
  vocabulary (`"P1"`..`"P4"`). A consumer doing exact string equality
  against `"P2"` instead of a prefix/substring check will break. This
  has to be documented for Phase 6's eval harness and Phase 7's
  dashboard, both of which read `properties_checked` directly.

## Revisit when

- Phase 3/4 give the verifier a real starting state, reconstructed from
  the ledger, with actual calendar-boundary resets. At that point
  `window` gains genuine enforced meaning and the qualifier changes
  from `horizon-cumulative` to something like `calendar-bounded`.
