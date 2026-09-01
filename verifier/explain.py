"""Counterexample model -> readable step trace.

decode_p1_violation and decode_p4_violation handle the two depth-1
per-action checks. decode_guard_counterexample handles the horizon-k
cumulative search. A decoder for replay_trace's concrete-scenario
traces is added in the next pass.
"""

from __future__ import annotations

from z3 import ModelRef, is_true

from contracts.models import Action, ActionType, Counterexample, CounterexampleStep, PolicyIR
from verifier.model import (
    ACTION_CAPTURE,
    ACTION_CREATE_ORDER,
    ACTION_REFUND,
    NUM_ORDER_SLOTS,
    State,
    StepVars,
)

_ACTION_TYPE_BY_CODE = {
    ACTION_CREATE_ORDER: ActionType.CREATE_ORDER,
    ACTION_CAPTURE: ActionType.CAPTURE,
    ACTION_REFUND: ActionType.REFUND,
}


def decode_p1_violation(model: ModelRef, sv: StepVars) -> Counterexample:
    """A single admitted capture whose amount exceeds per_txn_cap_paise.
    Depth-1: this cannot depend on accumulated state, so it needs no
    horizon to find — it either holds for every admissible capture or
    it doesn't.
    """
    step = CounterexampleStep(
        step_index=1,
        action_type=ActionType.CAPTURE,
        order_id=f"order-{model.eval(sv.order_idx, model_completion=True).as_long()}",
        amount_paise=model.eval(sv.amount_paise, model_completion=True).as_long(),
    )
    return Counterexample(
        violated_property="P1",
        trace=[step],
        violation_step_index=1,
        explanation=(
            f"step 1: the guard admitted a single capture of {step.amount_paise} paise, "
            "exceeding per_txn_cap_paise on its own — no sequence needed."
        ),
    )


def decode_p4_violation(model: ModelRef, sv: StepVars, vocabulary: list[str]) -> Counterexample:
    """A single admitted capture in a category the policy disallows.
    Depth-1, same reasoning as P1: category admissibility doesn't depend
    on accumulated state.
    """
    idx = model.eval(sv.category_idx, model_completion=True).as_long()
    category = vocabulary[idx] if idx < len(vocabulary) else None
    step = CounterexampleStep(
        step_index=1,
        action_type=ActionType.CAPTURE,
        order_id=f"order-{model.eval(sv.order_idx, model_completion=True).as_long()}",
        amount_paise=model.eval(sv.amount_paise, model_completion=True).as_long(),
        category=category,
    )
    return Counterexample(
        violated_property="P4",
        trace=[step],
        violation_step_index=1,
        explanation=(
            f"step 1: the guard admitted a single capture in category "
            f"{category or 'unlisted'}, outside the policy's allowed/blocked rules — "
            "no sequence needed."
        ),
    )


def decode_guard_counterexample(
    model: ModelRef,
    policy: PolicyIR,
    steps: list[StepVars],
    states: list[State],
    horizon: int,
) -> Counterexample:
    """Walks the model step by step — the trace is uniquely determined
    once every free variable is assigned — to find the first index at
    which a cumulative invariant breaks, then renders the prefix up to
    and including that step.
    """

    for t in range(horizon):
        s1 = states[t + 1]

        window_ok = policy.window_cap_paise is None or is_true(
            model.eval(s1.month_spend <= policy.window_cap_paise, model_completion=True)
        )
        refund_ok = all(
            is_true(model.eval(s1.refunded[slot] <= s1.captured[slot], model_completion=True))
            for slot in range(NUM_ORDER_SLOTS)
        )

        if window_ok and refund_ok:
            continue

        violated_property = "P2" if not window_ok else "P3"
        violation_step_index = t + 1
        trace = [
            CounterexampleStep(
                step_index=i + 1,
                action_type=_ACTION_TYPE_BY_CODE[model.eval(steps[i].action_type, model_completion=True).as_long()],
                order_id=f"order-{model.eval(steps[i].order_idx, model_completion=True).as_long()}",
                amount_paise=model.eval(steps[i].amount_paise, model_completion=True).as_long(),
            )
            for i in range(violation_step_index)
        ]
        explanation = (
            f"step {violation_step_index}: every action in this {violation_step_index}-step trace "
            f"was individually admitted by the guard, but the sequence collectively violates "
            f"{violated_property}."
        )
        return Counterexample(
            violated_property=violated_property,
            trace=trace,
            violation_step_index=violation_step_index,
            explanation=explanation,
        )

    raise AssertionError("solver returned sat but no violating step was found while decoding the model")


def decode_action_rejection(
    policy: PolicyIR,
    action: Action,
    month_spend: int,
    captured_for_order: int,
    refunded_for_order: int,
) -> Counterexample:
    """Concrete, single-action counterpart to decode_guard_counterexample.
    verify_action's decision is already made by Z3 by the time this runs
    (UNSAT means the guard rejects this exact action from this exact real
    state) -- this only names which property is responsible, by evaluating
    each one directly against the same concrete numbers the solver was
    given. No search, no model to read off; every value is already known.
    """
    if action.action_type == ActionType.CAPTURE:
        if policy.per_txn_cap_paise is not None and action.amount_paise > policy.per_txn_cap_paise:
            violated = "P1"
        elif (
            policy.window_cap_paise is not None
            and month_spend + action.amount_paise > policy.window_cap_paise
        ):
            violated = "P2"
        elif policy.allowed_categories is not None and action.category not in policy.allowed_categories:
            violated = "P4"
        elif action.category in policy.blocked_categories:
            violated = "P4"
        else:
            # The guard rejected this capture for a reason not enumerated
            # above -- shouldn't happen given sound_capture_guard's actual
            # conditions, but never leave the property unnamed.
            violated = "P1"
    elif action.action_type == ActionType.REFUND:
        violated = "P3"
    else:
        violated = "unknown"

    step = CounterexampleStep(
        step_index=1,
        action_type=action.action_type,
        order_id=action.order_id,
        amount_paise=action.amount_paise,
        category=action.category,
    )
    return Counterexample(
        violated_property=violated,
        trace=[step],
        violation_step_index=1,
        explanation=(
            f"step 1: {action.action_type.value} of {action.amount_paise} paise "
            f"on {action.order_id} was rejected by the guard against the current "
            f"account state -- violates {violated}."
        ),
    )
