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
    return activate_policy(policy, horizon=horizon)
