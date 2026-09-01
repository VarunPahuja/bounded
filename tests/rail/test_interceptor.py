"""Phase 4 spec (MASTER.md, CLAUDE.md). Written first, before rail/interceptor.py
exists -- per CLAUDE.md's own instruction for this phase: "Write test_fail_closed
first. Then the design decision. Then build." This file defines propose_action's
contract for the fail-closed case, the single most important guarantee in the
repo: a solver exception, a solver timeout (reported as Verdict.ERROR), or an
unreadable ledger state must all BLOCK, never ALLOW, and must never let a
Razorpay call happen. "Malformed policy" collapses to the same exception-from-
verify_action shape as a genuine encoding bug -- fail-closed doesn't get to
distinguish the two, it just has to never fall through to ALLOW either way.

Mocks rail.interceptor.attempt_capture / .refund directly (not the razorpay
SDK client) because propose_action must never even reach the rail layer on
any of these paths -- call count 0, not "the call failed."
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dotenv import load_dotenv

from contracts.models import (
    Action,
    ActionType,
    LedgerDecision,
    PolicyIR,
    Verdict,
    VerificationResult,
)
from ledger.chain import append_entry
from ledger.store import append as ledger_append, load_all, make_engine
from rail.interceptor import AccountState, propose_action, reconstruct_state
from rail.razorpay_client import CaptureResult, fetch_payment

load_dotenv()

NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)
AUTHORIZED_PAYMENT_ID = os.environ.get("RAZORPAY_TEST_AUTHORIZED_PAYMENT_ID")


def _seeded_engine(private_key: Ed25519PrivateKey):
    engine = make_engine()
    genesis = append_entry(
        None,
        entry_id="genesis",
        timestamp=NOW,
        decision=LedgerDecision.GENESIS,
        private_key=private_key,
    )
    ledger_append(engine, genesis)
    return engine


def _capture_action(amount_paise: int = 5_000) -> Action:
    return Action(
        action_id="act-fail-closed",
        action_type=ActionType.CAPTURE,
        order_id="order_1",
        amount_paise=amount_paise,
        category="software",
        occurred_at=NOW,
    )


def _policy() -> PolicyIR:
    return PolicyIR(per_txn_cap_paise=10_000, window_cap_paise=50_000)


def _assert_blocked_no_rail_call(engine, private_key, action, mock_capture, mock_refund):
    decision = propose_action(action, _policy(), engine, private_key)

    assert decision.allowed is False
    assert decision.verification.verdict != Verdict.SAFE
    assert decision.razorpay_payment_id is None
    mock_capture.assert_not_called()
    mock_refund.assert_not_called()

    entries = load_all(engine)
    assert len(entries) == 2  # genesis + this decision, nothing else
    assert entries[-1].decision == LedgerDecision.BLOCK
    assert entries[-1].razorpay_payment_id is None
    assert entries[-1].action == action
    return decision


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_fail_closed_on_solver_exception(mock_capture, mock_refund):
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    action = _capture_action()

    with patch("rail.interceptor.verify_action", side_effect=RuntimeError("z3 blew up")):
        _assert_blocked_no_rail_call(engine, private_key, action, mock_capture, mock_refund)


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_fail_closed_on_solver_timeout(mock_capture, mock_refund):
    # verify_action's own contract (see the design writeup) is to translate a
    # Z3 "unknown" result into Verdict.ERROR rather than raise -- propose_action
    # must treat ERROR exactly like an exception: block, don't guess.
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    action = _capture_action()

    timeout_result = VerificationResult(
        verdict=Verdict.ERROR,
        properties_checked=[],
        horizon=8,
        counterexample=None,
        latency_ms=30_000.0,
        error_message="solver returned unknown (timeout) -- failing closed",
    )
    with patch("rail.interceptor.verify_action", return_value=timeout_result):
        decision = _assert_blocked_no_rail_call(engine, private_key, action, mock_capture, mock_refund)

    assert decision.verification.error_message is not None


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_fail_closed_on_malformed_policy(mock_capture, mock_refund):
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    action = _capture_action()

    with patch("rail.interceptor.verify_action", side_effect=ValueError("bad policy encoding")):
        _assert_blocked_no_rail_call(engine, private_key, action, mock_capture, mock_refund)


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_fail_closed_on_missing_state(mock_capture, mock_refund):
    # reconstruct_state can't read a coherent state from the ledger (e.g. a
    # broken engine) -- propose_action must block rather than verify a
    # proposed action against a fabricated or stale state.
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    action = _capture_action()

    with patch("rail.interceptor.reconstruct_state", side_effect=RuntimeError("ledger unreadable")):
        _assert_blocked_no_rail_call(engine, private_key, action, mock_capture, mock_refund)


def test_fail_closed_never_raises_out_of_propose_action():
    # However verification fails internally, propose_action itself must
    # return a BLOCK decision, not propagate the exception -- a caller that
    # forgets to wrap every call site in try/except must still fail closed.
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    action = _capture_action()

    with patch("rail.interceptor.verify_action", side_effect=RuntimeError("z3 blew up")):
        decision = propose_action(action, _policy(), engine, private_key)

    assert decision.allowed is False


# ============================================================
# Compliant / violating decisions, ledger recording, ordering
# ============================================================


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_violating_action_blocked(mock_capture, mock_refund):
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    policy = PolicyIR(per_txn_cap_paise=1_000)
    action = _capture_action(amount_paise=5_000)  # exceeds the per-txn cap

    decision = propose_action(action, policy, engine, private_key)

    assert decision.allowed is False
    assert decision.verification.verdict == Verdict.VIOLATION
    mock_capture.assert_not_called()
    mock_refund.assert_not_called()


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_block_writes_ledger_entry(mock_capture, mock_refund):
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    policy = PolicyIR(per_txn_cap_paise=1_000)
    action = _capture_action(amount_paise=5_000)

    propose_action(action, policy, engine, private_key)

    entries = load_all(engine)
    assert len(entries) == 2  # genesis + this block, nothing more
    blocked = entries[-1]
    assert blocked.decision == LedgerDecision.BLOCK
    assert blocked.action == action
    assert blocked.razorpay_payment_id is None
    assert blocked.verification_result is not None
    assert blocked.verification_result.verdict == Verdict.VIOLATION
    assert blocked.verification_result.counterexample is not None
    assert blocked.verification_result.counterexample.violated_property == "P1"


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_ledger_entry_precedes_call(mock_capture, mock_refund):
    # The decision entry must be visible in the ledger at the moment the
    # rail is called -- if the process died right here, the ledger would
    # already show intent, not silence.
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    policy = PolicyIR(per_txn_cap_paise=10_000, window_cap_paise=50_000)
    action = _capture_action(amount_paise=5_000)

    ledger_length_at_call_time = []

    def fake_capture(payment_id, amount_paise):
        ledger_length_at_call_time.append(len(load_all(engine)))
        return CaptureResult(success=True, payment={"id": payment_id, "status": "captured"})

    mock_capture.side_effect = fake_capture

    decision = propose_action(action, policy, engine, private_key)

    assert ledger_length_at_call_time == [2]  # genesis + decision entry, BEFORE the outcome entry
    assert decision.allowed is True
    entries = load_all(engine)
    assert len(entries) == 3  # genesis, decision, outcome
    assert entries[1].decision == LedgerDecision.ALLOW
    assert entries[1].razorpay_payment_id is None  # decision entry: pre-call, outcome unknown yet
    assert entries[2].razorpay_payment_id == action.order_id  # outcome entry: confirmed


# ============================================================
# State reconstruction: the three-way ledger predicate
# ============================================================


def _order_action(action_id: str, amount_paise: int, order_id: str = "order_1") -> Action:
    return Action(
        action_id=action_id,
        action_type=ActionType.CAPTURE,
        order_id=order_id,
        amount_paise=amount_paise,
        category="software",
        occurred_at=NOW,
    )


@patch("rail.interceptor.refund")
@patch("rail.interceptor.attempt_capture")
def test_state_reconstruction(mock_capture, mock_refund):
    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    policy = PolicyIR(per_txn_cap_paise=10_000, window_cap_paise=100_000)

    # 1. A genuinely executed capture -- must count.
    mock_capture.return_value = CaptureResult(success=True, payment={"id": "order_1", "status": "captured"})
    ok = propose_action(_order_action("act-ok", 3_000), policy, engine, private_key)
    assert ok.allowed is True
    assert ok.razorpay_payment_id is not None

    # 2. Blocked by the guard -- action.amount_paise exceeds per_txn_cap_paise,
    # so the rail is never called; must not count.
    blocked = propose_action(_order_action("act-blocked", 999_999), policy, engine, private_key)
    assert blocked.allowed is False

    # 3. Allowed by the guard (well within both caps), but the rail call
    # itself fails -- must not count either.
    mock_capture.return_value = CaptureResult(success=False, error="already captured")
    failed = propose_action(_order_action("act-failed", 2_000), policy, engine, private_key)
    assert failed.allowed is True  # the verifier said this was safe
    assert failed.razorpay_payment_id is None  # but Razorpay rejected it

    state = reconstruct_state(engine)
    assert isinstance(state, AccountState)
    assert state.month_spend == 3_000  # only case 1
    assert state.captured == {"order_1": 3_000}
    assert state.refunded == {}


# ============================================================
# Live: a real payment id comes back, and the ledger's reconstructed
# state agrees with what Razorpay itself reports (test_state_reconstruction's
# live half -- see that test above for the deterministic half of the same
# claim: the reconstruction predicate itself).
# ============================================================


def test_compliant_action_executes():
    if AUTHORIZED_PAYMENT_ID is None:
        pytest.skip(
            "RAZORPAY_TEST_AUTHORIZED_PAYMENT_ID not set -- see "
            "tests/rail/test_razorpay_client_live.py's docstring to seed one."
        )

    before = fetch_payment(AUTHORIZED_PAYMENT_ID)
    if before["status"] != "authorized":
        pytest.skip(
            f"{AUTHORIZED_PAYMENT_ID} is {before['status']!r}, not 'authorized' -- "
            "already consumed by a previous run, or past the manual capture window. "
            "Reseed and update the env var."
        )
    amount = before["amount"]

    private_key = Ed25519PrivateKey.generate()
    engine = _seeded_engine(private_key)
    policy = PolicyIR(per_txn_cap_paise=amount, window_cap_paise=amount)
    action = Action(
        action_id="live-capture-1",
        action_type=ActionType.CAPTURE,
        order_id=AUTHORIZED_PAYMENT_ID,
        amount_paise=amount,
        category="software",
        occurred_at=NOW,
    )

    decision = propose_action(action, policy, engine, private_key)

    assert decision.allowed is True
    assert decision.razorpay_payment_id == AUTHORIZED_PAYMENT_ID
    assert decision.rail_error is None

    after = fetch_payment(AUTHORIZED_PAYMENT_ID)
    assert after["status"] == "captured"

    state = reconstruct_state(engine)
    assert state.captured[AUTHORIZED_PAYMENT_ID] == after["amount"]
    assert state.month_spend == after["amount"]
