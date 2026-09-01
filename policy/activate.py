"""Whether a successfully parsed PolicyIR is provably servable (ADR-0011's
"Revisit when": Phase 5+ should have verify_guard(policy, GUARD) gate
activation). Deliberately a separate module from policy/parse.py: parsing
text into a PolicyIR and deciding whether that PolicyIR is enforceable are
different concerns, and only this one needs Z3 -- policy/parse.py must never
import verifier/ (test_parse_is_not_in_enforcement_path,
tests/test_architecture.py).

Imports rail.interceptor.GUARD rather than reconstructing
compose_guard(sound_capture_guard, sound_refund_guard) locally: ADR-0011's
soundness argument holds only as long as every caller checks the exact same
guard object the live interceptor enforces with. A second construction of
"the same" guard is exactly the kind of thing that drifts silently.
"""

from __future__ import annotations

from contracts.models import PolicyIR, VerificationResult
from rail.interceptor import GUARD
from verifier.bmc import verify_guard


def activate_policy(policy: PolicyIR, horizon: int = 8) -> VerificationResult:
    """SAFE iff no sequence of guard-admitted actions, up to `horizon` steps,
    can breach `policy` when enforced with the interceptor's actual guard.
    A caller should treat anything other than SAFE (VIOLATION or ERROR) as
    not servable -- fail closed, same as everywhere else in this repo.
    """
    return verify_guard(policy, GUARD, horizon=horizon)
