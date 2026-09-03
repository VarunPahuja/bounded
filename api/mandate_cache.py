"""Mandate surface demo cache (task brief Phase 7b, item 1). The Mandate
surface must render a real parsed-and-activated policy the instant it
mounts, with no live Azure call in that path -- Phase 5 measured the parser
at roughly 1-in-5 flake on a live call (docs/LOG.md), and a network call on
every page load is also just slow. This module computes the real
parse_mandate + activate_policy result for the exact docs/DEMO.md recording
mandate once, then persists it to disk -- "cache the parse result at build
time or on first run" per the brief. Every value in the cached response is
a real pipeline output, recorded once; nothing here is hand-typed.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from contracts.models import PolicyIR, VerificationResult
from policy.activate import activate_policy
from policy.parse import parse_mandate

from api.z3_lock import Z3_LOCK

# The exact string docs/DEMO.md's 0:25-1:00 beat rehearses and
# MandateSurface.tsx defaults to -- kept identical on purpose so the cached
# response always describes what the Mandate surface actually shows.
RECORDING_MANDATE = (
    "This agent may spend up to ₹15,000 this month, no single payment above ₹5,000, "
    "groceries and utilities only, and it can never refund more than it charged."
)

_CACHE_PATH = Path(__file__).resolve().parent / "demo_mandate_cache.json"


class DemoMandateResponse(BaseModel):
    mandate_text: str
    policy: PolicyIR
    activation: VerificationResult


def get_demo_mandate() -> DemoMandateResponse:
    if _CACHE_PATH.exists():
        return DemoMandateResponse.model_validate_json(_CACHE_PATH.read_text(encoding="utf-8"))

    policy = parse_mandate(RECORDING_MANDATE)
    with Z3_LOCK:
        activation = activate_policy(policy, horizon=8)
    response = DemoMandateResponse(mandate_text=RECORDING_MANDATE, policy=policy, activation=activation)
    _CACHE_PATH.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return response
