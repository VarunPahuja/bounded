"""Counterexample model -> readable step trace.

decode_p1_violation handles the depth-1 per-action check. decode_guard_
counterexample handles the horizon-k cumulative search. A decoder for
replay_trace's concrete-scenario traces is added in the next pass.
"""

from __future__ import annotations

from z3 import ArithRef, ModelRef, is_true

from contracts.models import ActionType, Counterexample, CounterexampleStep
from verifier.model import (
    ACTION_CAPTURE,
    ACTION_CREATE_ORDER,
    ACTION_REFUND,
    NUM_ORDER_SLOTS,
    HandPolicy,
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


def decode_guard_counterexample(
    model: ModelRef,
    policy: HandPolicy,
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
