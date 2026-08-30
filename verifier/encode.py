"""Z3 constraint builders.

Guard functions model admissibility rules a real interceptor might apply
to a single proposed action. Each is deliberately either naive (checks
less than the policy actually needs) or sound (checks the running
accumulated state before admitting), so verify_guard can prove the
difference between them rather than assert it.

invariant_holds is the cumulative property a sound guard must never let
a trace escape, no matter how many admissible actions compose it.

encode() is the transpiler MASTER.md's Phase 2 asks for: a pure function
from PolicyIR to Z3 constraints, no guard, no invariant negation — just
the shared transition system every check in this project is built on.

replay_trace (concrete-scenario checking, verifier/bmc.py) does not use
this module: its properties are plain Python arithmetic over a fully
determined trace, not Z3 constraints over free variables. There is
nothing to search for once every action is already known.
"""

from __future__ import annotations

from typing import Callable

from z3 import And, BoolRef, BoolVal, If, Implies, Or, Solver, Sum

from contracts.models import PolicyIR
from verifier.model import (
    ACTION_CAPTURE,
    ACTION_REFUND,
    NUM_ORDER_SLOTS,
    State,
    StepVars,
    add_transition_relation,
    build_symbolic_system,
    category_vocabulary,
)

# t (the step index) is explicit rather than inferred from call order.
# verify_guard calls a guard once per step in a horizon-k system, but
# also once more on an isolated depth-1 system for the P1/P4 pre-checks
# (verifier/bmc.py:_check_p1, _check_p4) — a guard that tracked position
# via a mutable counter would desync between those call sites. Explicit
# t also lets a guard pin an exact scenario for testing (see
# tests/verifier/test_agreement.py) without relying on call order.
GuardFn = Callable[[PolicyIR, StepVars, State, int], BoolRef]


def _captured_for_order(sv: StepVars, s0: State) -> BoolRef:
    return Sum([If(sv.order_idx == slot, s0.captured[slot], 0) for slot in range(NUM_ORDER_SLOTS)])


def _refunded_for_order(sv: StepVars, s0: State) -> BoolRef:
    return Sum([If(sv.order_idx == slot, s0.refunded[slot], 0) for slot in range(NUM_ORDER_SLOTS)])


def category_admissible_indices(policy: PolicyIR, vocabulary: list[str]) -> set[int]:
    """Which category_idx values (see verifier/model.py:category_vocabulary,
    ADR-0009) this policy's allowlist/blocklist admits. index ==
    len(vocabulary) is the OTHER sentinel: admissible only when there's
    no allowlist (an unset allowlist means "anything not blocked is fine").
    """
    other_index = len(vocabulary)
    admissible = set()
    for i, name in enumerate(vocabulary):
        if policy.allowed_categories is not None and name not in policy.allowed_categories:
            continue
        if name in policy.blocked_categories:
            continue
        admissible.add(i)
    if policy.allowed_categories is None:
        admissible.add(other_index)
    return admissible


def naive_capture_guard(policy: PolicyIR, sv: StepVars, s0: State, t: int) -> BoolRef:
    """Checks the per-transaction cap only. Blind to how much of the
    window has already been spent, and blind to category — the exact
    bug this project exists to catch: compliant on every individual
    call, unsound in aggregate.
    """
    if policy.per_txn_cap_paise is None:
        return BoolVal(True)
    return Implies(sv.action_type == ACTION_CAPTURE, sv.amount_paise <= policy.per_txn_cap_paise)


def sound_capture_guard(policy: PolicyIR, sv: StepVars, s0: State, t: int) -> BoolRef:
    """Checks the per-transaction cap, the running window spend
    (including this capture), and category admissibility (P4, ADR-0009)
    before admitting a capture.
    """
    parts = []
    if policy.per_txn_cap_paise is not None:
        parts.append(sv.amount_paise <= policy.per_txn_cap_paise)
    if policy.window_cap_paise is not None:
        parts.append(s0.month_spend + sv.amount_paise <= policy.window_cap_paise)
    if policy.allowed_categories is not None or policy.blocked_categories:
        vocabulary = category_vocabulary(policy)
        admissible = category_admissible_indices(policy, vocabulary)
        parts.append(Or(*(sv.category_idx == i for i in admissible)))
    if not parts:
        return BoolVal(True)
    return Implies(sv.action_type == ACTION_CAPTURE, And(*parts))


def naive_refund_guard(policy: PolicyIR, sv: StepVars, s0: State, t: int) -> BoolRef:
    """Checks this refund's amount against the order's total captured
    amount, but not against how much of that order has already been
    refunded. A single refund can therefore never breach P3 by itself —
    only a split sequence, each refund individually within the captured
    total, can push the cumulative refunded amount past it.
    """
    return Implies(sv.action_type == ACTION_REFUND, sv.amount_paise <= _captured_for_order(sv, s0))


def sound_refund_guard(policy: PolicyIR, sv: StepVars, s0: State, t: int) -> BoolRef:
    """Admits a refund only if refunded-so-far plus this refund would not
    exceed captured-so-far, for the order it targets.
    """
    return Implies(
        sv.action_type == ACTION_REFUND,
        _refunded_for_order(sv, s0) + sv.amount_paise <= _captured_for_order(sv, s0),
    )


def admit_everything(policy: PolicyIR, sv: StepVars, s0: State, t: int) -> BoolRef:
    """No admission rule at all. Used only to prove the transition
    relation itself is satisfiable and reachable — see
    test_search_space_is_non_empty. Never compose this into a guard
    under test; it would make every property vacuously violable.
    """
    return BoolVal(True)


def compose_guard(capture_guard: GuardFn, refund_guard: GuardFn) -> GuardFn:
    """A guard under test is the conjunction of an admission rule per
    action type. Composing lets a test isolate one naive rule while
    keeping every other action type soundly admitted, so a violation
    found by verify_guard can only be attributed to the rule under test.
    """

    def guard(policy: PolicyIR, sv: StepVars, s0: State, t: int) -> BoolRef:
        return And(capture_guard(policy, sv, s0, t), refund_guard(policy, sv, s0, t))

    return guard


def invariant_holds(policy: PolicyIR, s: State) -> BoolRef:
    """The cumulative invariants a sound guard must never let a trace
    escape: P2 window cap (if configured) and P3 refund soundness
    (always on — PolicyIR.refund_bounded_by_capture is Literal[True]).
    P1 and P4 are per-action, not cumulative — checked separately as
    depth-1 checks (verifier/bmc.py:_check_p1, _check_p4).
    """
    parts = []
    if policy.window_cap_paise is not None:
        parts.append(s.month_spend <= policy.window_cap_paise)
    for slot in range(NUM_ORDER_SLOTS):
        parts.append(s.refunded[slot] <= s.captured[slot])
    return And(*parts)


def encode(policy: PolicyIR, horizon: int = 8) -> Solver:
    """The transpiler: a pure function from PolicyIR to Z3 constraints.
    Same input, same constraints, every time — no guard, no invariant
    negation, just the transition system and its input bounds. Every
    check in this module (verify_guard's P1/P4 depth-1 checks, its
    horizon-k P2/P3 search) is built by adding more to a solver shaped
    exactly like this one.
    """
    solver, steps, states = build_symbolic_system(policy, horizon)
    add_transition_relation(solver, steps, states)
    return solver
