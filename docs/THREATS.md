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
