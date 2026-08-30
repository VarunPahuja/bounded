"""Bounded model checking entry points.

verify_guard is the proof: symbolic actions and amounts, admitted only
by the given guard, checked against the policy's invariants. It runs
three checks:

  - P1, depth-1: can the guard admit a single capture that exceeds
    per_txn_cap_paise on its own?
  - P4, depth-1: can the guard admit a single capture in a category the
    policy disallows? (ADR-0009 — category_idx's domain is the policy's
    own vocabulary, so this needs no arbitrary bound.)
  - P2/P3, depth-k: can a sequence of guard-admitted actions, each
    individually compliant, collectively breach the window cap or
    refund soundness within `horizon` steps?

Both depth-1 checks are state-independent, so they're checked once each
rather than unrolled to the horizon.

UNSAT on all three means: no admissible trace of that length breaches
the invariant — sound to depth k, and only to depth k. That bound
travels with the verdict on VerificationResult.horizon, on both the
sound and the unsound path. properties_checked additionally carries a
window-granularity caveat on P2 (ADR-0010): window_cap_paise is proven
cumulative over the horizon, not resolved against a real calendar
boundary, and that has to be visible on the result rather than implied.

replay_trace is not a proof. It walks one concrete, already-known
sequence of actions through the same accounting rules and reports the
first step, if any, that breaches the policy — plain Python arithmetic,
no search, no solver. It exists for the eval harness and for rendering
"what happened" in the demo. It is never called verification, in code
or in docs (see ADR-0005's sibling rule: the guard/proof path is the
only thing allowed to make a soundness claim).
"""

from __future__ import annotations

import time
from typing import Optional

from z3 import Not, Or, sat

from contracts.models import Action, ActionType, Counterexample, CounterexampleStep, PolicyIR, Verdict, VerificationResult
from verifier.encode import GuardFn, category_admissible_indices, invariant_holds
from verifier.explain import decode_guard_counterexample, decode_p1_violation, decode_p4_violation
from verifier.model import ACTION_CAPTURE, add_transition_relation, build_symbolic_system, category_vocabulary


def _properties_checked(policy: PolicyIR) -> list[str]:
    properties = []
    if policy.per_txn_cap_paise is not None:
        properties.append("P1")
    if policy.window_cap_paise is not None:
        # ADR-0010: window is read but not calendar-enforced — the
        # caveat travels with the verdict, not just a docstring.
        window_label = policy.window.value if policy.window is not None else "unset"
        properties.append(f"P2[window={window_label},horizon-cumulative]")
    properties.append("P3")  # refund soundness is always on
    if policy.allowed_categories is not None or policy.blocked_categories:
        properties.append("P4")
    return properties


def _check_p1(policy: PolicyIR, guard: GuardFn):
    """Depth-1: does the guard ever admit a single capture whose amount
    exceeds per_txn_cap_paise? Returns a Counterexample or None.
    """
    if policy.per_txn_cap_paise is None:
        return None

    solver, steps, states = build_symbolic_system(policy, horizon=1)
    sv, s0 = steps[0], states[0]
    solver.add(guard(policy, sv, s0, 0))
    solver.add(sv.action_type == ACTION_CAPTURE)
    solver.add(sv.amount_paise > policy.per_txn_cap_paise)

    if solver.check() != sat:
        return None
    return decode_p1_violation(solver.model(), sv)


def _check_p4(policy: PolicyIR, guard: GuardFn):
    """Depth-1: does the guard ever admit a single capture in a category
    the policy disallows? Returns a Counterexample or None.
    """
    if policy.allowed_categories is None and not policy.blocked_categories:
        return None

    vocabulary = category_vocabulary(policy)
    admissible = category_admissible_indices(policy, vocabulary)
    inadmissible = [i for i in range(len(vocabulary) + 1) if i not in admissible]
    if not inadmissible:
        return None

    solver, steps, states = build_symbolic_system(policy, horizon=1)
    sv, s0 = steps[0], states[0]
    solver.add(guard(policy, sv, s0, 0))
    solver.add(sv.action_type == ACTION_CAPTURE)
    solver.add(Or(*(sv.category_idx == i for i in inadmissible)))

    if solver.check() != sat:
        return None
    return decode_p4_violation(solver.model(), sv, vocabulary)


def verify_guard(policy: PolicyIR, guard: GuardFn, horizon: int = 8) -> VerificationResult:
    start = time.perf_counter()
    properties_checked = _properties_checked(policy)

    counterexample = _check_p1(policy, guard)
    if counterexample is None:
        counterexample = _check_p4(policy, guard)

    if counterexample is None:
        solver, steps, states = build_symbolic_system(policy, horizon)
        add_transition_relation(solver, steps, states)

        for t, sv in enumerate(steps):
            solver.add(guard(policy, sv, states[t], t))

        solver.add(Or(*(Not(invariant_holds(policy, states[t + 1])) for t in range(horizon))))

        if solver.check() == sat:
            counterexample = decode_guard_counterexample(solver.model(), policy, steps, states, horizon)

    latency_ms = (time.perf_counter() - start) * 1000
    return VerificationResult(
        verdict=Verdict.VIOLATION if counterexample else Verdict.SAFE,
        properties_checked=properties_checked,
        horizon=horizon,
        counterexample=counterexample,
        latency_ms=latency_ms,
    )


def _replay_violated_property(
    policy: PolicyIR,
    action: Action,
    month_spend: int,
    captured: dict[str, int],
    refunded: dict[str, int],
) -> Optional[str]:
    """Checked against state *after* applying `action`, matching
    verify_guard's states[t + 1] convention.
    """
    if action.action_type == ActionType.CAPTURE:
        if policy.per_txn_cap_paise is not None and action.amount_paise > policy.per_txn_cap_paise:
            return "P1"
        if policy.window_cap_paise is not None and month_spend > policy.window_cap_paise:
            return "P2"
        if policy.allowed_categories is not None and action.category not in policy.allowed_categories:
            return "P4"
        if action.category in policy.blocked_categories:
            return "P4"
    if action.action_type == ActionType.REFUND:
        if refunded.get(action.order_id, 0) > captured.get(action.order_id, 0):
            return "P3"
    return None


def replay_trace(policy: PolicyIR, scenario: list[Action], horizon: int = 8) -> Optional[Counterexample]:
    if len(scenario) > horizon:
        raise ValueError(f"scenario length {len(scenario)} exceeds horizon {horizon}")

    month_spend = 0
    captured: dict[str, int] = {}
    refunded: dict[str, int] = {}
    trace: list[CounterexampleStep] = []

    for index, action in enumerate(scenario, start=1):
        trace.append(
            CounterexampleStep(
                step_index=index,
                action_type=action.action_type,
                order_id=action.order_id,
                amount_paise=action.amount_paise,
                category=action.category,
            )
        )

        if action.action_type == ActionType.CAPTURE:
            month_spend += action.amount_paise
            captured[action.order_id] = captured.get(action.order_id, 0) + action.amount_paise
        elif action.action_type == ActionType.REFUND:
            refunded[action.order_id] = refunded.get(action.order_id, 0) + action.amount_paise

        violated = _replay_violated_property(policy, action, month_spend, captured, refunded)
        if violated is not None:
            return Counterexample(
                violated_property=violated,
                trace=trace,
                violation_step_index=index,
                explanation=(
                    f"step {index}: {action.action_type.value} of {action.amount_paise} paise "
                    f"on {action.order_id} violates {violated}."
                ),
            )

    return None
