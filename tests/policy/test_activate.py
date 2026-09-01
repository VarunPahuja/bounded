from contracts.models import PolicyIR, Verdict, Window
from policy.activate import GUARD as ACTIVATE_GUARD
from policy.activate import activate_policy
from rail.interceptor import GUARD as INTERCEPTOR_GUARD


def test_activate_policy_checks_the_same_guard_the_interceptor_enforces_with():
    # ADR-0011's soundness argument holds only if this module and the live
    # interceptor check the exact same guard object -- not two separately
    # constructed guards that happen to look identical today.
    assert ACTIVATE_GUARD is INTERCEPTOR_GUARD


def test_activate_policy_safe_for_an_ordinary_mandate():
    policy = PolicyIR(per_txn_cap_paise=5000, window_cap_paise=15000, window=Window.MONTH)

    result = activate_policy(policy)

    assert result.verdict == Verdict.SAFE
    assert result.counterexample is None
