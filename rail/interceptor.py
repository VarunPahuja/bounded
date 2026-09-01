"""The interceptor: the only module permitted to call rail/razorpay_client's
money-moving functions (ADR-0003). Every proposed action goes:

    agent -> propose_action -> reconstruct_state (ledger) -> verify_action
    (Z3) -> ledger entry (ALLOW/BLOCK, written before the rail call) ->
    rail (only on ALLOW) -> ledger entry (outcome, only on ALLOW)

test_no_direct_rail_access (tests/test_architecture.py) statically enforces
that `attempt_capture`/`refund` are imported nowhere else in the repo
except here and rail/razorpay_client.py itself (which defines them) and
Phase 3's live rail test (which tests the rail in isolation, on purpose --
CLAUDE.md: never mock the call that's supposed to prove the rail works).

PAYMENT_ID SIMPLIFICATION: contracts.models.Action carries only order_id,
not a separate Razorpay payment_id -- there is no order_id -> payment_id
mapping anywhere in this repo, and scripts/seed.py's flow is one order to
one payment. This module treats action.order_id as the payment_id passed
to attempt_capture/refund. A real multi-payment-per-order merchant
integration would need a mapping layer this project doesn't build.

STATE RECONSTRUCTION counts an entry toward accumulated spend iff
decision == ALLOW, action is not None, and razorpay_payment_id is not
None -- see reconstruct_state's docstring for why this one predicate
correctly distinguishes blocked, allowed-but-failed-at-rail, and
genuinely-executed actions using only fields contracts.models.LedgerEntry
already has.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from razorpay.errors import BadRequestError
from sqlalchemy.engine import Engine

from contracts.models import (
    Action,
    ActionType,
    LedgerDecision,
    LedgerEntry,
    PolicyIR,
    Verdict,
    VerificationResult,
)
from ledger.chain import append_entry
from ledger.store import append as ledger_append, get_tip, load_all
from rail.razorpay_client import attempt_capture, refund
from verifier.bmc import verify_action
from verifier.encode import compose_guard, sound_capture_guard, sound_refund_guard

# The one guard the interceptor is allowed to enforce with: the sound one.
# naive_capture_guard/naive_refund_guard exist only so tests can prove they
# are unsound (tests/verifier/test_bmc.py) -- never composed into live
# enforcement. Hard-coding this constant (rather than accepting a
# caller-supplied guard) is what keeps ADR-0011's inductive soundness
# argument from drifting: verify_action must always be asked about the
# same guard verify_guard was asked to certify.
GUARD = compose_guard(sound_capture_guard, sound_refund_guard)

# Order creation is outside the agent's action space (Phase 3, 2026-08-31
# LOG entry): a human seeds authorized-but-uncaptured orders offscreen,
# ahead of time. propose_action fails closed on it rather than silently
# routing it somewhere undefined.
_UNSUPPORTED_ACTION_TYPES = {ActionType.CREATE_ORDER}


@dataclass(frozen=True)
class AccountState:
    month_spend: int
    captured: dict[str, int]
    refunded: dict[str, int]


def reconstruct_state(engine: Engine) -> AccountState:
    """Rebuild month_spend and per-order captured/refunded totals from the
    ledger alone -- never from Razorpay (test_state_reconstruction checks
    the two agree, but the verifier's input is always the ledger: it's
    what we control and can prove untampered).

    Only entries with decision == ALLOW, action set, AND razorpay_payment_id
    set count. That predicate resolves all three cases a real interceptor
    run can produce:

      - BLOCK: action is set, razorpay_payment_id never was -- excluded.
      - ALLOW, decision entry (written before the rail call) or a rail call
        that failed: action is set, razorpay_payment_id is None -- excluded
        either way. A crash between the decision and outcome writes leaves
        exactly this shape: a record of intent, not a confirmed execution,
        correctly excluded rather than double-counted or silently lost.
      - ALLOW, outcome entry, Razorpay confirmed: both fields set --
        included, per ADR-0006 (refunds are gross, not net: a refund never
        reduces month_spend, only captures add to it).

    This also composes for free with Phase 3's webhook path
    (rail/webhook.py): webhook-recorded entries carry razorpay_payment_id
    but never an Action (there was none to attach), so they're structurally
    invisible to this sum -- a webhook echo of a capture the interceptor
    already recorded as an outcome entry can never be double-counted.
    """
    month_spend = 0
    captured: dict[str, int] = {}
    refunded: dict[str, int] = {}

    for entry in load_all(engine):
        if entry.decision != LedgerDecision.ALLOW:
            continue
        if entry.action is None or entry.razorpay_payment_id is None:
            continue

        action = entry.action
        if action.action_type == ActionType.CAPTURE:
            month_spend += action.amount_paise
            captured[action.order_id] = captured.get(action.order_id, 0) + action.amount_paise
        elif action.action_type == ActionType.REFUND:
            refunded[action.order_id] = refunded.get(action.order_id, 0) + action.amount_paise

    return AccountState(month_spend=month_spend, captured=captured, refunded=refunded)


@dataclass(frozen=True)
class InterceptorDecision:
    allowed: bool
    verification: VerificationResult
    decision_entry: LedgerEntry
    outcome_entry: Optional[LedgerEntry]
    razorpay_payment_id: Optional[str]
    rail_error: Optional[str]


def _error_result(message: str, start: float) -> VerificationResult:
    return VerificationResult(
        verdict=Verdict.ERROR,
        properties_checked=[],
        horizon=1,
        counterexample=None,
        latency_ms=(time.perf_counter() - start) * 1000,
        error_message=message,
    )


def _verify(action: Action, policy: PolicyIR, engine: Engine) -> VerificationResult:
    """Fail closed: any failure to reconstruct state, or any failure inside
    verify_action itself (Z3 exception, or a solver timeout reported as
    Verdict.ERROR -- see verify_action's docstring), produces a BLOCK-
    worthy VerificationResult rather than propagating. This is the single
    most load-bearing branch in the interceptor (CLAUDE.md, MASTER.md
    Phase 4: "the single most important test in the repo").
    """
    start = time.perf_counter()

    if action.action_type in _UNSUPPORTED_ACTION_TYPES:
        return _error_result(
            f"{action.action_type.value} is not in the agent's action space "
            "(Phase 3: order creation happens outside the agent's path) -- failing closed",
            start,
        )

    try:
        state = reconstruct_state(engine)
    except Exception as e:
        return _error_result(f"state reconstruction failed: {e}", start)

    try:
        return verify_action(
            policy,
            GUARD,
            action,
            month_spend=state.month_spend,
            captured_for_order=state.captured.get(action.order_id, 0),
            refunded_for_order=state.refunded.get(action.order_id, 0),
        )
    except Exception as e:
        return _error_result(f"verification failed: {e}", start)


def _execute(action: Action) -> tuple[Optional[str], Optional[str]]:
    """Call the rail for an ALLOWed action. Returns (payment_id, error) --
    exactly one is non-None. Never lets a rail exception escape uncaught,
    but never swallows one silently either: a caught failure is returned
    to the caller and written to the outcome ledger entry, not discarded.
    """
    if action.action_type == ActionType.CAPTURE:
        result = attempt_capture(action.order_id, action.amount_paise)
        if result.success:
            return result.payment["id"], None
        return None, result.error

    if action.action_type == ActionType.REFUND:
        try:
            payment = refund(action.order_id, action.amount_paise)
            return payment["id"], None
        except BadRequestError as e:
            return None, str(e)

    raise AssertionError(f"_execute called with unsupported action type {action.action_type!r}")


def propose_action(
    action: Action,
    policy: PolicyIR,
    engine: Engine,
    private_key: Ed25519PrivateKey,
) -> InterceptorDecision:
    """The single entry point. Nothing else in this repo (outside
    rail/razorpay_client.py and Phase 3's live rail test) is allowed to
    call attempt_capture or refund -- see test_no_direct_rail_access.
    """
    verification = _verify(action, policy, engine)
    allowed = verification.verdict == Verdict.SAFE

    tip = get_tip(engine)
    decision_entry = append_entry(
        tip,
        entry_id=f"{action.action_id}:decision",
        timestamp=datetime.now(timezone.utc),
        decision=LedgerDecision.ALLOW if allowed else LedgerDecision.BLOCK,
        private_key=private_key,
        action=action,
        verification_result=verification,
        razorpay_payment_id=None,
    )
    ledger_append(engine, decision_entry)

    if not allowed:
        return InterceptorDecision(
            allowed=False,
            verification=verification,
            decision_entry=decision_entry,
            outcome_entry=None,
            razorpay_payment_id=None,
            rail_error=None,
        )

    payment_id, rail_error = _execute(action)

    outcome_entry = append_entry(
        decision_entry,
        entry_id=f"{action.action_id}:outcome",
        timestamp=datetime.now(timezone.utc),
        decision=LedgerDecision.ALLOW,
        private_key=private_key,
        action=action,
        verification_result=None,
        razorpay_payment_id=payment_id,
    )
    ledger_append(engine, outcome_entry)

    return InterceptorDecision(
        allowed=True,
        verification=verification,
        decision_entry=decision_entry,
        outcome_entry=outcome_entry,
        razorpay_payment_id=payment_id,
        rail_error=rail_error,
    )
