# THREATS

Named limitations of the enforcement guarantee, stated plainly rather than
left for a reviewer to find. Each entry names the threat, why the system
does not (and structurally cannot, from inside this repo) catch it, and
its consequence.

## Out-of-band money movement bypasses the invariant entirely

**Threat:** Money moves at Razorpay without going through
`propose_action` (`rail/interceptor.py`). Two concrete ways this happens:

1. A refund or other action issued from the Razorpay dashboard by a human
   with account access.
2. A webhook for an event the interceptor never proposed.

**Why the system can't catch it:** `verify_action`'s soundness
(ADR-0011) is inductive: it holds only if the real current state,
reconstructed from the ledger, actually equals real current spend. That
equality itself holds only if every action that ever moved money did so
through the interceptor. The AST test enforcing "the solver decides"
(CLAUDE.md's one rule) checks that no code path *in this repo* skips the
guard — it has no way to see money movement that never enters this repo
at all.

Case 2 is sharper than it first looks. `reconstruct_state` only counts a
ledger entry that has both `action` and `razorpay_payment_id` set.
Webhook-recorded entries carry `razorpay_payment_id` but no `Action` (see
`reconstruct_state`'s docstring), so they are structurally invisible to
the state sum. That's deliberate and correct for its stated purpose: it's
what stops a webhook echo of a capture the interceptor already recorded
from being double-counted. The same exclusion, applied to a webhook with
no matching interceptor-side record, makes genuinely out-of-band money
invisible too — it's one property serving two purposes, one wanted and
one not.

**Consequence:** `reconstruct_state` returns a total strictly below real
spend. `verify_action` then reasons from a real-current-state value that
understates reality, and can return ALLOW for an action that pushes true
spend past the policy cap while the ledger's own arithmetic looks correct
at every step. The proof is sound with respect to the ledger; it is not
sound with respect to the account if the account can be moved by anything
other than the ledger's own writer.

**Status:** Not mitigated in code. The guarantee holds under the stated
precondition — the interceptor is the sole path through which money moves
at Razorpay — which is an operational discipline (API-key scoping,
dashboard access control, webhook completeness) external to this repo,
not something this repo can enforce on its own. See ADR-0011's amendment.

**Possible detection (not prevention), if cheap:** `reconstruct_state`
could compare its computed total against what Razorpay's API reports for
the same window and flag a divergence. This would catch the drift after
the fact, not prevent the ALLOW that let it through. Not implemented as
of Phase 4 — evaluated as low priority against Phase 5 scope.

## A block caused by `MAX_AMOUNT_PAISE` is mislabeled as a per-transaction-cap violation

**Threat:** not a soundness gap — the decision itself is correct and
fail-closed. `MAX_AMOUNT_PAISE` (`verifier/model.py`, ADR-0008,
10,000,000 paise / Rs 100,000) bounds the symbolic `amount_paise` variable
in `build_symbolic_system`, used by both the offline `verify_guard` proof
and the runtime `verify_action` check. If a proposed action's amount
exceeds this constant, `verify_action`'s solver call becomes UNSAT purely
from that domain conflict (`sv.amount_paise == action.amount_paise` vs.
`sv.amount_paise <= MAX_AMOUNT_PAISE`), independent of the guard, the
invariant, or the merchant's stated `per_txn_cap_paise` — even one set
well above the attempted amount. The action is correctly blocked.

**Why the explanation is wrong:** `decode_action_rejection`
(`verifier/explain.py`) reasons only about `PolicyIR` fields to name which
property was violated. It has no way to see the encoding's own domain
bound, so a CAPTURE rejection it can't otherwise explain falls through to
its documented `P1` default (the comment above that branch already says
"shouldn't happen given `sound_capture_guard`'s actual conditions" — this
is exactly the case where it does happen). Confirmed live (2026-09-02,
Phase 6a, eval scenario `adv-013-near-max-amount-paise-block`):
`per_txn_cap_paise=20,000,000`, action amount `10,000,100` →
`Verdict.VIOLATION`, `Counterexample.violated_property == "P1"`, even
though `10,000,100 < 20,000,000` and the stated per-transaction cap was
never actually exceeded.

**Consequence:** a merchant whose mandate legitimately authorizes single
payments above Rs 100,000 (a real, plausible mandate — nothing in
`contracts/models.py` bounds `per_txn_cap_paise`'s upper value) will have
every such payment blocked by this project regardless of what they
authorized, and the ledger/UI would report it as a per-transaction-cap
violation the merchant never actually stated — a misleading audit trail
for a real, silent capability ceiling. `properties_checked` never lists
anything named after `MAX_AMOUNT_PAISE`, so nothing on the
`VerificationResult` itself hints that the stated policy wasn't the actual
reason.

**Status:** Not fixed in code. Discovered during Phase 6a's
`adversarial_vs_ours` eval class (ADR-0013), which was specifically
authored to probe boundaries this project already admits to (ADR-0008
itself names "any per_txn_cap_paise... approaching MAX_AMOUNT_PAISE's
order of magnitude" as a revisit trigger). The fix, when picked up, is
narrow: `decode_action_rejection` needs a case for "amount exceeds
`MAX_AMOUNT_PAISE`" that names it honestly instead of falling through to
`P1`, and arguably `PolicyIR` should reject (or `verify_action` should
raise loudly on) a `per_txn_cap_paise` set above `MAX_AMOUNT_PAISE` at
policy-construction or activation time, rather than silently proving
something the encoding can't actually check. Not attempted here —
`verifier/` changes are outside this eval-build's scope, and MASTER.md's
5 September deadline was three days out when this was found.
