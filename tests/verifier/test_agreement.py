"""replay_trace (plain Python) and verify_guard (Z3) implement the same
accounting rules independently. If they drift, the demo narrates one
thing and the proof proves another — this is the test that would catch
that drift.

For each scenario, a guard is built that admits exactly that scenario's
actions, step by step, and nothing else (_exact_trace_guard). Running
that guard through verify_guard at horizon == len(scenario) forces Z3
to search a trace space containing exactly one trace: the scenario
itself. Its verdict must then agree with replay_trace's verdict on the
identical scenario.

Two scope gaps, both real, both worth stating rather than hiding:

  - NUM_ORDER_SLOTS = 2 (ADR-0007) means a scenario using 3+ distinct
    orders cannot be pinned as-is — order_idx would have to exceed the
    symbolic bound, which makes the whole system trivially unsatisfiable
    for a reason unrelated to the trace. Where the original replay_trace
    test scenario uses 3+ orders, this file reuses the same action
    sequence with order labels collapsed to fit 2 slots. That's sound
    for P2 (window cap doesn't depend on order identity) and P3 (per-
    order accounting still holds correctly *for the relabeled orders*,
    which is all this test checks).
  - P4 (category) is not part of the symbolic model verify_guard
    searches over — no guard could restrict admission by category yet.
    test_p4_category_violation's scenario is excluded outright: there is
    no verify_guard side to agree or disagree with.
"""

from datetime import datetime, timezone

from z3 import And

from contracts.models import Action, ActionType, PolicyIR, Verdict
from verifier.bmc import replay_trace, verify_guard
from verifier.encode import GuardFn
from verifier.model import ACTION_CAPTURE, ACTION_CREATE_ORDER, ACTION_REFUND, NUM_ORDER_SLOTS

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)

_ACTION_CODE_BY_TYPE = {
    ActionType.CREATE_ORDER: ACTION_CREATE_ORDER,
    ActionType.CAPTURE: ACTION_CAPTURE,
    ActionType.REFUND: ACTION_REFUND,
}


def _action(action_type: ActionType, order_id: str, amount_paise: int, **overrides) -> Action:
    fields = dict(
        action_id=f"{order_id}-{action_type.value}-{overrides.get('category', '')}",
        action_type=action_type,
        order_id=order_id,
        amount_paise=amount_paise,
        category="electronics",
        occurred_at=NOW,
    )
    fields.update(overrides)
    return Action(**fields)


def _capture(order_id: str, amount_paise: int, **overrides) -> Action:
    return _action(ActionType.CAPTURE, order_id, amount_paise, **overrides)


def _refund(order_id: str, amount_paise: int, **overrides) -> Action:
    return _action(ActionType.REFUND, order_id, amount_paise, **overrides)


def _exact_trace_guard(scenario: list[Action]) -> GuardFn:
    """Admits exactly this scenario's action at each step index and
    nothing else. Relies on t being explicit (verifier/encode.py's
    GuardFn signature), not on call order.
    """
    order_slots = {oid: i for i, oid in enumerate(dict.fromkeys(a.order_id for a in scenario))}
    assert len(order_slots) <= NUM_ORDER_SLOTS, (
        f"scenario uses {len(order_slots)} distinct orders; NUM_ORDER_SLOTS is {NUM_ORDER_SLOTS}. "
        "Relabel the scenario's order_ids before adding it here."
    )

    def guard(policy: PolicyIR, sv, s0, t: int):
        action = scenario[t]
        return And(
            sv.action_type == _ACTION_CODE_BY_TYPE[action.action_type],
            sv.order_idx == order_slots[action.order_id],
            sv.amount_paise == action.amount_paise,
        )

    return guard


# (policy, scenario) pairs. Mirrors the eight replay_trace scenarios
# (test_p4_category_violation excluded, per module docstring; test_p2_
# multi_step and test_solver_terminates relabeled to fit NUM_ORDER_SLOTS),
# plus additional cases mixing both caps and multi-order refunds.
_AGREEMENT_SCENARIOS: list[tuple[PolicyIR, list[Action]]] = [
    # test_p1_violation_found
    (PolicyIR(per_txn_cap_paise=5000), [_capture("order-1", 6000)]),
    # test_p2_multi_step, order-3 relabeled to order-1 (P2 is order-blind)
    (
        PolicyIR(window_cap_paise=15000),
        [_capture("order-1", 6000), _capture("order-2", 6000), _capture("order-1", 6000)],
    ),
    # test_p2_safe
    (PolicyIR(window_cap_paise=15000), [_capture("order-1", 6000), _capture("order-2", 6000)]),
    # test_p3_refund_exceeds_capture
    (
        PolicyIR(),
        [_capture("order-1", 5000), _refund("order-1", 3000), _refund("order-1", 3000)],
    ),
    # test_p3_split_refunds_ok
    (
        PolicyIR(),
        [_capture("order-1", 5000), _refund("order-1", 2000), _refund("order-1", 3000)],
    ),
    # test_solver_terminates, 8 orders collapsed to 2, no caps so no violation either way
    (
        PolicyIR(),
        [_capture(f"order-{i % 2}", 1000) for i in range(8)],
    ),
    # both caps set, safe
    (
        PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000),
        [_capture("order-1", 5000), _capture("order-2", 5000)],
    ),
    # both caps set, violation is cumulative (P2), not per-action (P1)
    (
        PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000),
        [_capture("order-1", 5000), _capture("order-2", 5000), _capture("order-1", 5000), _capture("order-2", 5000)],
    ),
    # multi-order refund: order-2's refund alone exceeds order-2's capture
    (
        PolicyIR(),
        [_capture("order-1", 3000), _capture("order-2", 4000), _refund("order-1", 1000), _refund("order-2", 5000)],
    ),
    # P1 violation with window_cap also configured but never reached
    (
        PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000),
        [_capture("order-1", 6000)],
    ),
]


def test_replay_agrees_with_symbolic():
    for policy, scenario in _AGREEMENT_SCENARIOS:
        replay_result = replay_trace(policy, scenario, horizon=len(scenario))
        guard_result = verify_guard(policy, _exact_trace_guard(scenario), horizon=len(scenario))

        if replay_result is None:
            assert guard_result.verdict == Verdict.SAFE, (policy, scenario, guard_result)
        else:
            assert guard_result.verdict == Verdict.VIOLATION, (policy, scenario, replay_result, guard_result)
            assert guard_result.counterexample.violated_property == replay_result.violated_property, (
                policy,
                scenario,
                replay_result.violated_property,
                guard_result.counterexample.violated_property,
            )
