"""Proof surface backend (docs/PHASE7-PLAN.md).

Reruns verify_guard against a naive vs. sound guard for the same policy --
reproduces docs/DEMO.md's 1:00-2:40 beat exactly: same policy, same
solver, different guard, different verdict. NAIVE_GUARD composes the two
guard functions verifier/encode.py already keeps around only to prove
they're unsound in tests (naive_capture_guard, naive_refund_guard) --
never composed into live enforcement. SOUND_GUARD is imported from
rail.interceptor, the same constant object propose_action enforces with
-- not a second construction, so this endpoint can never silently drift
from what the live interceptor actually does (see ADR-0011).
"""

from __future__ import annotations

from typing import Literal

from contracts.models import PolicyIR, VerificationResult
from rail.interceptor import GUARD as SOUND_GUARD
from verifier.bmc import verify_guard
from verifier.encode import compose_guard, naive_capture_guard, naive_refund_guard

from api.z3_lock import Z3_LOCK

NAIVE_GUARD = compose_guard(naive_capture_guard, naive_refund_guard)

GuardName = Literal["naive", "sound"]


def verify(policy: PolicyIR, guard: GuardName, horizon: int = 8) -> VerificationResult:
    chosen = NAIVE_GUARD if guard == "naive" else SOUND_GUARD
    with Z3_LOCK:
        return verify_guard(policy, chosen, horizon=horizon)
