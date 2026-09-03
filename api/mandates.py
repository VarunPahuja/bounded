"""Mandate parsing + activation backend (docs/PHASE7-PLAN.md). Thin
wrapper over policy.parse.parse_mandate and policy.activate.activate_policy
-- no new decision logic, just serialization for the API layer. Shared by
the Proof surface (needs a PolicyIR to hand to verify_guard) and the
Mandate surface.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from contracts.models import PolicyIR, VerificationResult
from policy.activate import activate_policy
from policy.parse import MandateParseError, parse_mandate

from api.mandate_cache import DemoMandateResponse, get_demo_mandate
from api.z3_lock import Z3_LOCK


class ParseResponse(BaseModel):
    status: str  # "ok" | "ambiguous"
    policy: Optional[PolicyIR] = None
    message: Optional[str] = None


def parse(text: str) -> ParseResponse:
    try:
        policy = parse_mandate(text)
    except MandateParseError as e:
        # parse_mandate raises the same exception type whether the model
        # itself flagged the mandate ambiguous or its output was malformed
        # -- both mean "cannot produce a policy without guessing," and the
        # dashboard doesn't need a finer split than the parser itself makes.
        return ParseResponse(status="ambiguous", message=str(e))
    return ParseResponse(status="ok", policy=policy)


def activate(policy: PolicyIR, horizon: int = 8) -> VerificationResult:
    with Z3_LOCK:
        return activate_policy(policy, horizon=horizon)


def demo() -> DemoMandateResponse:
    """The cached, pre-parsed-and-activated recording mandate (task brief
    Phase 7b, item 1) -- no live Azure call on this path.
    """
    return get_demo_mandate()
