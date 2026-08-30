"""Phase 1 spec: MASTER.md section 4, Phase 1, as corrected mid-phase.

Two entry points, not to be confused:

  replay_trace(policy, scenario, horizon) -> Counterexample | None
      Concrete-scenario replay. No search, no proof. For the eval
      harness and demo explanation only. Never called verification.

  verify_guard(policy, guard, horizon) -> VerificationResult
      True BMC. Symbolic actions and amounts, admitted only by `guard`.
      VIOLATION means a sequence of individually-admissible actions
      collectively breaches an invariant. SAFE means no such sequence
      exists up to `horizon` steps — sound to that depth, and only to
      that depth. This is the proof the project's claim rests on.
"""

import time
from datetime import datetime, timezone

import pytest

from contracts.models import Action, ActionType, Counterexample, Verdict
from verifier.bmc import replay_trace, verify_guard
from verifier.encode import (
    admit_everything,
    compose_guard,
    naive_capture_guard,
    naive_refund_guard,
    sound_capture_guard,
    sound_refund_guard,
)
from verifier.model import HandPolicy

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _action(action_type: ActionType, order_id: str, amount_paise: int, **overrides) -> Action:
    fields = dict(
        action_id=f"{order_id}-{action_type.value}",
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


# ============================================================
# replay_trace: concrete-scenario replay (MASTER's seven, plus P4)
# ============================================================


# --- P1: per-transaction cap ---


def test_p1_violation_found():
    policy = HandPolicy(per_txn_cap_paise=5000)
    scenario = [_capture("order-1", 6000)]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert result.violated_property == "P1"
    assert result.violation_step_index == 1


# --- P2: window (monthly) cap ---


def test_p2_multi_step():
    policy = HandPolicy(window_cap_paise=15000)
    scenario = [
        _capture("order-1", 6000),
        _capture("order-2", 6000),
        _capture("order-3", 6000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert result.violated_property == "P2"
    assert result.violation_step_index == 3


def test_p2_safe():
    policy = HandPolicy(window_cap_paise=15000)
    scenario = [
        _capture("order-1", 6000),
        _capture("order-2", 6000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert result is None


# --- P3: refund soundness ---


def test_p3_refund_exceeds_capture():
    policy = HandPolicy()
    scenario = [
        _capture("order-1", 5000),
        _refund("order-1", 3000),
        _refund("order-1", 3000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert result.violated_property == "P3"
    assert result.violation_step_index == 3


def test_p3_split_refunds_ok():
    policy = HandPolicy()
    scenario = [
        _capture("order-1", 5000),
        _refund("order-1", 2000),
        _refund("order-1", 3000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert result is None


# --- P4: category restriction (not in MASTER's seven; added per Definition of Done) ---


def test_p4_category_violation():
    policy = HandPolicy(allowed_categories=["groceries"])
    scenario = [_capture("order-1", 1000, category="electronics")]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert result.violated_property == "P4"
    assert result.violation_step_index == 1


# --- Counterexample readability ---


def test_counterexample_readable():
    policy = HandPolicy(window_cap_paise=15000)
    scenario = [
        _capture("order-1", 6000),
        _capture("order-2", 6000),
        _capture("order-3", 6000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert len(result.trace) == result.violation_step_index
    for expected_step, step in enumerate(result.trace, start=1):
        assert step.step_index == expected_step
        assert step.action_type == ActionType.CAPTURE
        assert step.amount_paise == 6000
    assert result.explanation is not None
    assert "P2" in result.explanation
    assert "3" in result.explanation


# --- Performance ---


def test_solver_terminates():
    policy = HandPolicy()
    scenario = [_capture(f"order-{i}", 1000) for i in range(8)]

    start = time.perf_counter()
    result = replay_trace(policy, scenario, horizon=8)
    elapsed = time.perf_counter() - start

    assert result is None
    assert elapsed < 2.0


# ============================================================
# verify_guard: true BMC over symbolic actions, admitted by a guard
# ============================================================


def test_naive_guard_is_unsound():
    # Guard correctly enforces per_txn_cap (5000) and nothing else.
    # window_cap (15000) is real, but the guard has no notion of it.
    # No single admitted capture can breach the window on its own —
    # only a sequence can. If this test passes with a 1-step trace,
    # the guard checked nothing and the test is a false positive.
    policy = HandPolicy(per_txn_cap_paise=5000, window_cap_paise=15000)
    guard = compose_guard(naive_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION
    assert result.horizon == 8
    cx = result.counterexample
    assert len(cx.trace) >= 2
    captures = [step.amount_paise for step in cx.trace if step.action_type == ActionType.CAPTURE]
    assert all(amount <= 5000 for amount in captures)
    assert sum(captures) > 15000


def test_cumulative_guard_is_sound():
    # Same policy. The guard now also checks running window spend
    # before admitting a capture, so no admissible sequence — of any
    # length up to the horizon — can push month_spend past the cap.
    policy = HandPolicy(per_txn_cap_paise=5000, window_cap_paise=15000)
    guard = compose_guard(sound_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.SAFE
    assert result.counterexample is None
    assert result.horizon == 8


def test_naive_refund_guard_is_unsound():
    # Guard correctly enforces "this refund <= captured total for the
    # order" per action, so a single refund can never breach P3 alone.
    # It never checks refunded-so-far, so a split-refund sequence —
    # each refund individually within the captured total — still
    # escapes. A 1-step trace here would mean the guard checked
    # nothing about the refund amount at all.
    policy = HandPolicy()
    guard = compose_guard(sound_capture_guard, naive_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION
    cx = result.counterexample
    assert len(cx.trace) >= 2
    refunds = [step.amount_paise for step in cx.trace if step.action_type == ActionType.REFUND]
    captures = [step.amount_paise for step in cx.trace if step.action_type == ActionType.CAPTURE]
    assert sum(refunds) > sum(captures)


def test_search_space_is_non_empty():
    # Liveness check. test_cumulative_guard_is_sound asserts SAFE, but a
    # transition relation that's accidentally unsatisfiable — a bad
    # bound, a contradictory initial-state constraint, anything
    # unrelated to the policy — would also return SAFE, vacuously, for
    # every guard. A guard that admits everything, checked against a
    # cap no real trace could avoid breaching, must find a violation.
    # If it doesn't, the search space itself is broken, not the guard.
    policy = HandPolicy(window_cap_paise=1)
    guard = compose_guard(admit_everything, admit_everything)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION


def test_soundness_is_horizon_bounded():
    # UNSAT/SAFE from verify_guard means "no violation in any admissible
    # trace of at most `horizon` steps" — nothing about traces longer
    # than that. The bound must be a structured field on the result, not
    # a string, so no caller can report the verdict without it attached.
    policy = HandPolicy(per_txn_cap_paise=5000, window_cap_paise=15000)
    guard = compose_guard(naive_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION
    assert result.horizon == 8
