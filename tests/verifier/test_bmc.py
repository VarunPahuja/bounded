"""Phase 1 spec (MASTER.md section 4, Phase 1, as corrected mid-phase)
plus Phase 2 (Phase 2, the typed IR transpiler). PolicyIR is now the
only policy type — HandPolicy is gone (Phase 2 design decision: a
converter would just reintroduce the drift risk test_agreement.py
exists to catch, one layer up).

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

from z3 import Int

from contracts.models import Action, ActionType, Counterexample, PolicyIR, Verdict, Window
from verifier.bmc import replay_trace, verify_guard
from verifier.encode import (
    admit_everything,
    compose_guard,
    encode,
    invariant_holds,
    naive_capture_guard,
    naive_refund_guard,
    sound_capture_guard,
    sound_refund_guard,
)
from verifier.model import State, StepVars

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
    policy = PolicyIR(per_txn_cap_paise=5000)
    scenario = [_capture("order-1", 6000)]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert result.violated_property == "P1"
    assert result.violation_step_index == 1


# --- P2: window (monthly) cap ---


def test_p2_multi_step():
    policy = PolicyIR(window_cap_paise=15000, window=Window.MONTH)
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
    policy = PolicyIR(window_cap_paise=15000, window=Window.MONTH)
    scenario = [
        _capture("order-1", 6000),
        _capture("order-2", 6000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert result is None


# --- P3: refund soundness ---


def test_p3_refund_exceeds_capture():
    policy = PolicyIR()
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
    policy = PolicyIR()
    scenario = [
        _capture("order-1", 5000),
        _refund("order-1", 2000),
        _refund("order-1", 3000),
    ]

    result = replay_trace(policy, scenario, horizon=8)

    assert result is None


# --- P4: category restriction (not in MASTER's seven; added per Definition of Done) ---


def test_p4_category_violation():
    policy = PolicyIR(allowed_categories=["groceries"])
    scenario = [_capture("order-1", 1000, category="electronics")]

    result = replay_trace(policy, scenario, horizon=8)

    assert isinstance(result, Counterexample)
    assert result.violated_property == "P4"
    assert result.violation_step_index == 1


# --- Counterexample readability ---


def test_counterexample_readable():
    policy = PolicyIR(window_cap_paise=15000, window=Window.MONTH)
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
    policy = PolicyIR()
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
    policy = PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000, window=Window.MONTH)
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
    policy = PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000, window=Window.MONTH)
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
    policy = PolicyIR()
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
    policy = PolicyIR(window_cap_paise=1)
    guard = compose_guard(admit_everything, admit_everything)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION


def test_soundness_is_horizon_bounded():
    # UNSAT/SAFE from verify_guard means "no violation in any admissible
    # trace of at most `horizon` steps" — nothing about traces longer
    # than that. The bound must be a structured field on the result, not
    # a string, so no caller can report the verdict without it attached.
    policy = PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000, window=Window.MONTH)
    guard = compose_guard(naive_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION
    assert result.horizon == 8


def test_naive_guard_is_unsound_on_category():
    # Symmetric to test_naive_guard_is_unsound, for P4 (ADR-0009).
    # naive_capture_guard never considers category at all, so a guard
    # built from it alone always admits every category — a single
    # capture in a disallowed category needs no sequence to find.
    policy = PolicyIR(allowed_categories=["groceries"])
    guard = compose_guard(naive_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.VIOLATION
    cx = result.counterexample
    assert cx.violated_property == "P4"
    assert cx.violation_step_index == 1
    assert cx.trace[0].category != "groceries"


def test_sound_capture_guard_is_p4_sound():
    # sound_capture_guard enforces category admissibility (ADR-0009).
    # No admissible capture can ever land outside allowed_categories.
    policy = PolicyIR(allowed_categories=["groceries"])
    guard = compose_guard(sound_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.SAFE


# ============================================================
# Phase 2: transpiler determinism, IR field coverage, permissiveness
# ============================================================


def test_transpiler_deterministic():
    # encoding the same IR twice must produce identical constraints —
    # compare the solver's assertion strings, not object identity.
    policy = PolicyIR(
        per_txn_cap_paise=5000,
        window_cap_paise=15000,
        window=Window.MONTH,
        allowed_categories=["electronics", "groceries"],
    )

    solver_a = encode(policy, horizon=8)
    solver_b = encode(policy, horizon=8)

    assert [str(assertion) for assertion in solver_a.assertions()] == [
        str(assertion) for assertion in solver_b.assertions()
    ]


# Every PolicyIR field must be accounted for here, either because
# encode.py/bmc.py actually build a constraint from it, or because it's
# deliberately deferred with a stated reason. New field, forgotten here:
# this test fails, per MASTER.md's Phase 2 spec.
_ENCODED_FIELDS = {
    "per_txn_cap_paise",  # P1, verifier/bmc.py:_check_p1
    "window_cap_paise",  # P2, verifier/encode.py:invariant_holds
    "window",  # P2 qualifier only, ADR-0010 — read, reported, not calendar-enforced
    "allowed_categories",  # P4, verifier/bmc.py:_check_p4
    "blocked_categories",  # P4, verifier/bmc.py:_check_p4
    "refund_bounded_by_capture",  # P3, always on, verifier/encode.py:invariant_holds
}
_DEFERRED_FIELDS = {
    "max_txn_count": "no txn_count state and no property number defined yet; out of Phase 2 scope",
    "require_human_above_paise": "an escalation trigger, not a solver-decidable invariant in this "
    "model — belongs to the interceptor (Phase 4), not the verifier",
}


def test_every_ir_field_encoded():
    accounted = _ENCODED_FIELDS | set(_DEFERRED_FIELDS)
    actual = set(PolicyIR.model_fields)

    missing = actual - accounted
    assert not missing, f"PolicyIR field(s) {missing} are neither encoded nor deliberately deferred with a reason"


def _probe_step_and_state() -> tuple[StepVars, State]:
    """A fixed, policy-independent StepVars/State pair, reused across a
    differential check's two policies so the only thing that can change
    in the resulting constraint string is the policy value itself.
    """
    return (
        StepVars(
            action_type=Int("probe_action_type"),
            order_idx=Int("probe_order_idx"),
            amount_paise=Int("probe_amount_paise"),
            category_idx=Int("probe_category_idx"),
        ),
        State(
            month_spend=Int("probe_month_spend"),
            captured=[Int("probe_captured_0"), Int("probe_captured_1")],
            refunded=[Int("probe_refunded_0"), Int("probe_refunded_1")],
        ),
    )


def _capture_guard_probe(policy: PolicyIR) -> str:
    sv, s0 = _probe_step_and_state()
    return str(sound_capture_guard(policy, sv, s0, 0))


def _invariant_probe(policy: PolicyIR) -> str:
    _, s0 = _probe_step_and_state()
    return str(invariant_holds(policy, s0))


def _encode_probe(policy: PolicyIR) -> str:
    return str(encode(policy, horizon=1).assertions())


# Field -> (policy_a, policy_b, probe). policy_a and policy_b differ in
# ONLY the named field; probe is whichever function actually consumes
# that field — not always encode() itself. per_txn_cap_paise and
# window_cap_paise never reach encode() (see verifier/encode.py's
# module docstring): they're consumed by sound_capture_guard and
# invariant_holds respectively, only when verify_guard runs a real
# check. Only the category fields change encode()'s own output, by
# resizing category_idx's bound.
_DIFFERENTIAL_CASES = {
    "per_txn_cap_paise": (
        PolicyIR(per_txn_cap_paise=5000),
        PolicyIR(per_txn_cap_paise=6000),
        _capture_guard_probe,
    ),
    "window_cap_paise": (
        PolicyIR(window_cap_paise=15000),
        PolicyIR(window_cap_paise=20000),
        _invariant_probe,
    ),
    "allowed_categories": (
        PolicyIR(allowed_categories=["groceries"]),
        PolicyIR(allowed_categories=["groceries", "electronics"]),
        _encode_probe,
    ),
    "blocked_categories": (
        PolicyIR(blocked_categories=["weapons"]),
        PolicyIR(blocked_categories=["weapons", "alcohol"]),
        _encode_probe,
    ),
}

# _ENCODED_FIELDS this mechanism structurally cannot cover, and why —
# the residual weakness, stated rather than hidden.
_EXEMPT_FROM_DIFFERENTIAL = {
    "window": (
        "ADR-0010: window only ever changes properties_checked's P2 "
        "qualifier, never a Z3 constraint. Locked down separately by "
        "test_window_semantics_are_reported, which diffs the result, "
        "not a constraint string."
    ),
    "refund_bounded_by_capture": (
        "Literal[True] — pydantic refuses to construct a PolicyIR with "
        "any other value, so there is no second variant to differ "
        "against. Always-on-ness is the property being encoded."
    ),
}


def test_encoded_fields_actually_change_constraints():
    """Stronger than test_every_ir_field_encoded: being *listed* in
    _ENCODED_FIELDS is not proof of anything by itself — a field could
    sit there with a plausible comment and reach no constraint at all.
    For every field this can mechanically drive, changing only that
    field, with everything else fixed, must change the resulting Z3
    constraint string.

    Residual weakness, stated rather than hidden: this proves a changed
    field changes *something*, not that it changes the *correct* thing —
    a field wired to the wrong constraint would still pass. And the two
    _EXEMPT_FROM_DIFFERENTIAL fields aren't covered by this mechanism at
    all, for the structural reasons stated next to each.
    """
    covered = set(_DIFFERENTIAL_CASES) | set(_EXEMPT_FROM_DIFFERENTIAL)
    assert covered == _ENCODED_FIELDS, (
        f"_DIFFERENTIAL_CASES/_EXEMPT_FROM_DIFFERENTIAL drifted from _ENCODED_FIELDS: "
        f"{_ENCODED_FIELDS ^ covered}"
    )

    for field, (policy_a, policy_b, probe) in _DIFFERENTIAL_CASES.items():
        assert probe(policy_a) != probe(policy_b), f"{field} does not change the constraint {probe.__name__} produces"


def test_empty_policy_is_permissive():
    # No caps (P1/P2/P4) configured means nothing about caps can be
    # violated. P3 (refund soundness) is structurally always on
    # (PolicyIR.refund_bounded_by_capture is Literal[True]) regardless
    # of policy content, so the guard under test still has to be
    # refund-sound for this to hold — that's not a cap, it's a given.
    # sound_capture_guard degenerates to admit-everything when no caps
    # are set, so this is the maximally permissive guard this claim can
    # honestly be checked against.
    policy = PolicyIR()
    guard = compose_guard(sound_capture_guard, sound_refund_guard)

    result = verify_guard(policy, guard, horizon=8)

    assert result.verdict == Verdict.SAFE
    assert result.properties_checked == ["P3"]


def test_window_semantics_are_reported():
    # ADR-0010: window changes what window_cap_paise is supposed to
    # mean but has no effect on the encoding. If it were silently
    # ignored, a DAY policy and a MONTH policy would be indistinguishable
    # on the result. They must not be.
    policy_day = PolicyIR(window_cap_paise=15000, window=Window.DAY)
    policy_month = PolicyIR(window_cap_paise=15000, window=Window.MONTH)
    guard = compose_guard(admit_everything, sound_refund_guard)

    result_day = verify_guard(policy_day, guard, horizon=8)
    result_month = verify_guard(policy_month, guard, horizon=8)

    assert result_day.properties_checked != result_month.properties_checked
