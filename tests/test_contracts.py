from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts.models import (
    Action,
    ActionType,
    Counterexample,
    CounterexampleStep,
    LedgerDecision,
    LedgerEntry,
    Mandate,
    PolicyIR,
    Verdict,
    VerificationResult,
    Window,
)

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _action(**overrides) -> Action:
    fields = dict(
        action_id="act-1",
        action_type=ActionType.CAPTURE,
        order_id="order-1",
        amount_paise=5000,
        category="electronics",
        occurred_at=NOW,
    )
    fields.update(overrides)
    return Action(**fields)


def _policy_ir(**overrides) -> PolicyIR:
    fields: dict = {}
    fields.update(overrides)
    return PolicyIR(**fields)


def _mandate() -> Mandate:
    return Mandate(
        mandate_id="mandate-1",
        principal_id="merchant-1",
        agent_id="agent-1",
        natural_language_text="Spend up to 15000 rupees per month on electronics.",
        policy=_policy_ir(
            per_txn_cap_paise=500000,
            window_cap_paise=1500000,
            window=Window.MONTH,
        ),
        issued_at=NOW,
    )


def _counterexample() -> Counterexample:
    return Counterexample(
        violated_property="P2",
        trace=[
            CounterexampleStep(
                step_index=1,
                action_type=ActionType.CAPTURE,
                order_id="order-1",
                amount_paise=600000,
            ),
            CounterexampleStep(
                step_index=2,
                action_type=ActionType.CAPTURE,
                order_id="order-2",
                amount_paise=600000,
            ),
            CounterexampleStep(
                step_index=3,
                action_type=ActionType.CAPTURE,
                order_id="order-3",
                amount_paise=600000,
            ),
        ],
        violation_step_index=3,
        explanation="step 3: capture 6000 pushes month_spend above the 15000 cap",
    )


def _verification_result(violation: bool) -> VerificationResult:
    return VerificationResult(
        verdict=Verdict.VIOLATION if violation else Verdict.SAFE,
        properties_checked=["P1", "P2", "P3", "P4"],
        horizon=8,
        counterexample=_counterexample() if violation else None,
        latency_ms=42.5,
    )


def _ledger_entry() -> LedgerEntry:
    return LedgerEntry(
        index=1,
        entry_id="entry-1",
        timestamp=NOW,
        decision=LedgerDecision.BLOCK,
        action=_action(),
        verification_result=_verification_result(violation=True),
        prev_hash="0" * 64,
        entry_hash="a" * 64,
        signature="b" * 128,
    )


# --- Phase 0 test case 1: every model round-trips through model_dump_json() ---


@pytest.mark.parametrize(
    "instance",
    [
        _action(),
        _policy_ir(),
        _mandate(),
        _counterexample(),
        _verification_result(violation=True),
        _verification_result(violation=False),
        _ledger_entry(),
    ],
)
def test_model_round_trips_through_json(instance):
    model_cls = type(instance)
    rehydrated = model_cls.model_validate_json(instance.model_dump_json())
    assert rehydrated == instance


# --- Phase 0 test case 2: Action rejects negative amounts ---


def test_action_rejects_negative_amount():
    with pytest.raises(ValidationError):
        _action(amount_paise=-100)


def test_action_rejects_zero_amount():
    with pytest.raises(ValidationError):
        _action(amount_paise=0)


def test_action_accepts_positive_amount():
    assert _action(amount_paise=1).amount_paise == 1


# --- Phase 0 test case 3: PolicyIR rejects a monthly cap lower than a per-txn cap ---


def test_policy_ir_rejects_monthly_cap_below_per_txn_cap():
    with pytest.raises(ValidationError):
        PolicyIR(
            per_txn_cap_paise=500000,
            window_cap_paise=100000,
            window=Window.MONTH,
        )


def test_policy_ir_accepts_monthly_cap_at_or_above_per_txn_cap():
    policy = PolicyIR(
        per_txn_cap_paise=500000,
        window_cap_paise=500000,
        window=Window.MONTH,
    )
    assert policy.window_cap_paise == 500000


def test_policy_ir_day_window_not_checked_against_per_txn_cap():
    # The Phase 0 invariant is specifically about the monthly window.
    policy = PolicyIR(
        per_txn_cap_paise=500000,
        window_cap_paise=100000,
        window=Window.DAY,
    )
    assert policy.window_cap_paise == 100000


def test_policy_ir_with_no_caps_is_valid():
    assert PolicyIR().per_txn_cap_paise is None
