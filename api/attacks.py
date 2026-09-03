"""Attacks surface backend (docs/PHASE7-PLAN.md, ADR-0014).

Runs a real eval/scenarios/*.json attack scenario through the real
pipeline -- real parse (cached per mandate text, see _policy_for),
real per-action Z3 verdicts via rail.interceptor.propose_action, real
hash-chained ledger writes on a fresh isolated chain -- with only the
Razorpay network call mocked, the exact substitution eval/runner.py
already makes and docs/EVAL.md already discloses (ADR-0014).

Reads eval/scenario.py and eval/scenarios/*.json; imports nothing else
from eval/. Never edits verifier/, rail/, policy/, ledger/, contracts/,
or eval/ -- import only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import patch

from pydantic import BaseModel

from contracts.models import Action, PolicyIR, VerificationResult
from eval.scenario import Scenario
from policy.parse import parse_mandate
from rail.interceptor import propose_action
from rail.razorpay_client import CaptureResult

from api.demo_state import demo_private_key, fresh_isolated_engine

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "eval" / "scenarios"

# Benign scenarios exist to measure false positives, not to demonstrate a
# block -- excluded from the picker so the panel only ever offers something
# that is actually an attack or an adversarial edge case.
_ATTACK_CLASSES = {
    "over_cap",
    "refund_exceeds_capture",
    "prompt_injection",
    "category_count_violation",
    "adversarial_vs_ours",
}


def _mock_capture(payment_id: str, amount_paise: int) -> CaptureResult:
    return CaptureResult(success=True, payment={"id": f"pay_{payment_id}", "status": "captured"})


def _mock_refund(payment_id: str, amount_paise: int) -> dict:
    return {"id": f"pay_{payment_id}_refund", "status": "refunded"}


class ScenarioSummary(BaseModel):
    scenario_id: str
    class_label: str
    mandate_text: str
    action_count: int


class AttackStep(BaseModel):
    step_index: int
    action: Action
    poisoned_text: Optional[str] = None
    allowed: bool
    verification: VerificationResult


class AttackRunResult(BaseModel):
    scenario_id: str
    mandate_text: str
    policy: PolicyIR
    steps: list[AttackStep]
    blocked_at_step: Optional[int] = None


class ScenarioNotFoundError(Exception):
    pass


_POLICY_CACHE: dict[str, PolicyIR] = {}


def list_scenarios() -> list[ScenarioSummary]:
    summaries: list[ScenarioSummary] = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        scenario = Scenario.model_validate_json(path.read_text(encoding="utf-8"))
        if scenario.class_label.value not in _ATTACK_CLASSES:
            continue
        summaries.append(
            ScenarioSummary(
                scenario_id=scenario.scenario_id,
                class_label=scenario.class_label.value,
                mandate_text=scenario.mandate_text,
                action_count=len(scenario.actions),
            )
        )
    return summaries


def _load_scenario(scenario_id: str) -> Scenario:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise ScenarioNotFoundError(scenario_id)
    return Scenario.model_validate_json(path.read_text(encoding="utf-8"))


def _policy_for(mandate_text: str) -> PolicyIR:
    """Cached per mandate text within this process. Every distinct mandate
    still goes through the real parser at least once (never hand-
    constructed); the cache exists to avoid a live Azure call -- cost,
    latency, and the ~1-in-5 field-drop flake docs/LOG.md's Phase 5 entry
    measured -- on every panel interaction against the same scenario.
    """
    if mandate_text not in _POLICY_CACHE:
        _POLICY_CACHE[mandate_text] = parse_mandate(mandate_text)
    return _POLICY_CACHE[mandate_text]


def run_scenario(scenario_id: str) -> AttackRunResult:
    scenario = _load_scenario(scenario_id)
    policy = _policy_for(scenario.mandate_text)

    engine = fresh_isolated_engine()
    private_key = demo_private_key()

    steps: list[AttackStep] = []
    blocked_at: Optional[int] = None

    with patch("rail.interceptor.attempt_capture", side_effect=_mock_capture), patch(
        "rail.interceptor.refund", side_effect=_mock_refund
    ):
        for i, spec in enumerate(scenario.actions, start=1):
            action = spec.to_action()
            decision = propose_action(action, policy, engine, private_key)
            steps.append(
                AttackStep(
                    step_index=i,
                    action=action,
                    poisoned_text=scenario.injection_context.get(spec.action_id),
                    allowed=decision.allowed,
                    verification=decision.verification,
                )
            )
            if not decision.allowed and blocked_at is None:
                blocked_at = i

    return AttackRunResult(
        scenario_id=scenario.scenario_id,
        mandate_text=scenario.mandate_text,
        policy=policy,
        steps=steps,
        blocked_at_step=blocked_at,
    )
