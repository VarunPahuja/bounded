"""Shared builders for tests/ledger/*.py. Not a test module itself."""

from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from contracts.models import (
    Action,
    ActionType,
    Counterexample,
    CounterexampleStep,
    LedgerDecision,
    Verdict,
    VerificationResult,
)
from ledger.chain import append_entry


def ts(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 8, 30, 12, 0, 0, 500_000, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )


def sample_action(amount_paise: int = 5_000) -> Action:
    return Action(
        action_id="act-1",
        action_type=ActionType.CAPTURE,
        order_id="order_1",
        amount_paise=amount_paise,
        category="software",
        occurred_at=ts(),
    )


def sample_verification_result() -> VerificationResult:
    return VerificationResult(
        verdict=Verdict.SAFE,
        properties_checked=["P1", "P2[window=month,horizon-cumulative]"],
        horizon=8,
        counterexample=None,
        latency_ms=12.5,
    )


def sample_violation_result() -> VerificationResult:
    return VerificationResult(
        verdict=Verdict.VIOLATION,
        properties_checked=["P1"],
        horizon=8,
        counterexample=Counterexample(
            violated_property="P1",
            trace=[
                CounterexampleStep(
                    step_index=0,
                    action_type=ActionType.CAPTURE,
                    order_id="order_1",
                    amount_paise=6_000,
                    category="software",
                )
            ],
            violation_step_index=0,
            explanation="capture of 6000 exceeds per-txn cap",
        ),
        latency_ms=8.1,
    )


def build_chain(n: int, private_key: Ed25519PrivateKey) -> list:
    entries = []
    prev = None
    for i in range(n):
        if i % 3 == 0:
            action, vr = None, None
            decision = LedgerDecision.GENESIS if i == 0 else LedgerDecision.ALLOW
        elif i % 3 == 1:
            action, vr = sample_action(1_000 * i), sample_verification_result()
            decision = LedgerDecision.ALLOW
        else:
            action, vr = sample_action(1_000 * i), sample_violation_result()
            decision = LedgerDecision.BLOCK
        entry = append_entry(
            prev,
            entry_id=f"entry-{i}",
            timestamp=ts(i),
            decision=decision,
            private_key=private_key,
            action=action,
            verification_result=vr,
            razorpay_payment_id=f"pay_{i}" if decision == LedgerDecision.ALLOW else None,
        )
        entries.append(entry)
        prev = entry
    return entries
