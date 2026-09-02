"""Phase 6 orchestration (docs/PHASE6-PLAN.md). Runs every scenario in
eval/scenarios/ through two pipelines, N_SAMPLES times each:

  ours   -- policy.parse.parse_mandate -> rail.interceptor.propose_action
            (Z3-backed), one continuous ledger per trial.
  judge  -- eval.baseline_llm_judge.judge_action, one call per action,
            deliberately-adopted anti-pattern baseline.

`python -m eval.runner` loads the corpus, runs both pipelines (EVAL_MODE
defaults to "replay"), and writes docs/EVAL.md. See eval/cassette.py for the
record/replay contract and eval/report.py for the methodology note that must
travel with every number this module produces -- in particular, the rail is
mocked in every trial (see _mock_capture/_mock_refund below): this harness
measures verdicts, not payments. Phase 3/4 already prove the rail works,
without mocking, and CLAUDE.md's ban on mocking the rail applies to that
claim, not to this one.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from contracts.models import LedgerDecision
from eval.baseline_llm_judge import (
    MODEL_NAME as JUDGE_MODEL_NAME,
    PROMPT_VERSION as JUDGE_PROMPT_VERSION,
    JudgeHistoryEntry,
    _complete as _real_judge_complete,
    judge_action,
)
from eval.cassette import get_live_call_count, reset_live_call_count, sampled_call
from eval.scenario import Scenario, ScenarioClass
from ledger.chain import append_entry
from ledger.store import append as ledger_append, make_engine
from policy.parse import (
    MODEL_NAME as PARSE_MODEL_NAME,
    PROMPT_VERSION as PARSE_PROMPT_VERSION,
    _SYSTEM_PROMPT as _PARSE_SYSTEM_PROMPT,
    _complete as _real_parse_complete,
    MandateParseError,
    parse_mandate,
)
from rail.interceptor import propose_action
from rail.razorpay_client import CaptureResult

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
N_SAMPLES = 8


# ============================================================
# "Ours" trial: parse_mandate -> propose_action, one continuous ledger.
# ============================================================


@dataclass(frozen=True)
class OursTrialResult:
    matched: bool
    verdicts: tuple[str, ...]  # "allow"/"block" per action, empty if parse failed
    parse_error: Optional[str]
    unsound_safe_action_ids: tuple[str, ...]
    # Wall-clock -- excluded from equality (compare=False) so CorpusResult
    # stays reproducible across runs, per test_runner_reproducible's stated
    # scope: verdicts are reproducible, timings structurally aren't.
    verification_latencies_ms: tuple[float, ...] = field(compare=False)


def _seeded_engine(private_key: Ed25519PrivateKey):
    engine = make_engine()
    genesis = append_entry(
        None,
        entry_id="genesis",
        timestamp=datetime.now(timezone.utc),
        decision=LedgerDecision.GENESIS,
        private_key=private_key,
    )
    ledger_append(engine, genesis)
    return engine


def _parse_messages(mandate_text: str) -> list[dict]:
    # Mirrors policy.parse._complete's own message construction exactly --
    # this is what makes the cassette key correspond to the real call.
    return [
        {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
        {"role": "user", "content": mandate_text},
    ]


def _real_parse_complete_from_messages(messages: list[dict]) -> str:
    return _real_parse_complete(messages[1]["content"])


def _mock_capture(payment_id: str, amount_paise: int) -> CaptureResult:
    return CaptureResult(success=True, payment={"id": f"pay_{payment_id}", "status": "captured"})


def _mock_refund(payment_id: str, amount_paise: int) -> dict:
    return {"id": f"pay_{payment_id}_refund", "status": "refunded"}


def run_ours_trial(scenario: Scenario, sample_index: int, private_key: Ed25519PrivateKey) -> OursTrialResult:
    pipeline_input = scenario.pipeline_input()  # PipelineInput has no such field to read
    expected = tuple(spec.expected_decision for spec in scenario.actions)

    complete_fn = sampled_call(
        _real_parse_complete_from_messages,
        call_site="parse",
        model=PARSE_MODEL_NAME,
        prompt_version=PARSE_PROMPT_VERSION,
        key_context={"scenario_id": scenario.scenario_id, "sample_index": sample_index},
    )

    def _patched_complete(mandate_text: str) -> str:
        return complete_fn(_parse_messages(mandate_text), sample_index)

    with patch("policy.parse._complete", side_effect=_patched_complete):
        try:
            policy_ir = parse_mandate(pipeline_input.mandate_text)
        except MandateParseError as e:
            return OursTrialResult(
                matched=False,
                verdicts=(),
                parse_error=str(e),
                unsound_safe_action_ids=(),
                verification_latencies_ms=(),
            )

    engine = _seeded_engine(private_key)
    verdicts: list[str] = []
    unsound_safe_ids: list[str] = []
    latencies: list[float] = []

    with patch("rail.interceptor.attempt_capture", side_effect=_mock_capture), patch(
        "rail.interceptor.refund", side_effect=_mock_refund
    ):
        for spec, action in zip(scenario.actions, pipeline_input.actions):
            decision = propose_action(action, policy_ir, engine, private_key)
            verdict = "allow" if decision.allowed else "block"
            verdicts.append(verdict)
            latencies.append(decision.verification.latency_ms)
            if spec.expected_decision == "block" and decision.allowed:
                unsound_safe_ids.append(spec.action_id)

    verdicts_t = tuple(verdicts)
    return OursTrialResult(
        matched=verdicts_t == expected,
        verdicts=verdicts_t,
        parse_error=None,
        unsound_safe_action_ids=tuple(unsound_safe_ids),
        verification_latencies_ms=tuple(latencies),
    )


# ============================================================
# Judge trial: one judge_action call per action, in sequence.
# ============================================================


@dataclass(frozen=True)
class JudgeTrialResult:
    matched: bool
    verdicts: tuple[str, ...]  # "allow" / "block" / "call_failed" per action
    call_failed_action_ids: tuple[str, ...]
    unsound_safe_action_ids: tuple[str, ...]


def run_judge_trial(scenario: Scenario, sample_index: int) -> JudgeTrialResult:
    expected = tuple(spec.expected_decision for spec in scenario.actions)
    pipeline_input = scenario.pipeline_input()

    complete_fn = sampled_call(
        _real_judge_complete,
        call_site="judge",
        model=JUDGE_MODEL_NAME,
        prompt_version=JUDGE_PROMPT_VERSION,
        key_context={"scenario_id": scenario.scenario_id, "sample_index": sample_index},
    )

    history: list[JudgeHistoryEntry] = []
    verdicts: list[str] = []
    call_failed_ids: list[str] = []
    unsound_safe_ids: list[str] = []

    for spec, action in zip(scenario.actions, pipeline_input.actions):
        poisoned = scenario.injection_context.get(spec.action_id)

        def _patched_complete(messages: list[dict]) -> str:
            return complete_fn(messages, sample_index)

        with patch("eval.baseline_llm_judge._complete", side_effect=_patched_complete):
            verdict = judge_action(
                mandate_text=scenario.mandate_text,
                history=history,
                candidate=action,
                poisoned_context=poisoned,
            )

        if verdict.call_failed:
            call_failed_ids.append(spec.action_id)
            verdicts.append("call_failed")
            # No history entry appended: the judge's own view of history is
            # exactly the decisions it actually made. A later action in this
            # trial is judged without seeing this one, rather than this
            # module inventing a decision the judge never reached.
            continue

        decided = verdict.decision.lower()
        verdicts.append(decided)
        history.append(JudgeHistoryEntry(action=action, decision=verdict.decision))
        if spec.expected_decision == "block" and decided == "allow":
            unsound_safe_ids.append(spec.action_id)

    verdicts_t = tuple(verdicts)
    return JudgeTrialResult(
        matched=verdicts_t == expected,
        verdicts=verdicts_t,
        call_failed_action_ids=tuple(call_failed_ids),
        unsound_safe_action_ids=tuple(unsound_safe_ids),
    )


# ============================================================
# Scenario / corpus aggregation
# ============================================================


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    class_label: ScenarioClass
    ours_trials: tuple[OursTrialResult, ...]
    judge_trials: tuple[JudgeTrialResult, ...]


@dataclass(frozen=True)
class CorpusResult:
    scenario_results: tuple[ScenarioResult, ...]


@dataclass(frozen=True)
class LatencyStats:
    verification_latencies_ms: tuple[float, ...]


def load_corpus(scenarios_dir: Path = SCENARIOS_DIR) -> list[Scenario]:
    paths = sorted(scenarios_dir.glob("*.json"))
    scenarios = [Scenario.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
    return sorted(scenarios, key=lambda s: s.scenario_id)


def run_scenario(scenario: Scenario, n: int = N_SAMPLES) -> ScenarioResult:
    ours_trials = tuple(run_ours_trial(scenario, i, Ed25519PrivateKey.generate()) for i in range(n))
    judge_trials = tuple(run_judge_trial(scenario, i) for i in range(n))
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        class_label=scenario.class_label,
        ours_trials=ours_trials,
        judge_trials=judge_trials,
    )


def run_corpus(scenarios: list[Scenario], n: int = N_SAMPLES) -> tuple[CorpusResult, LatencyStats]:
    scenario_results = tuple(run_scenario(s, n) for s in scenarios)
    latencies = tuple(
        lat
        for sr in scenario_results
        for trial in sr.ours_trials
        for lat in trial.verification_latencies_ms
    )
    return CorpusResult(scenario_results=scenario_results), LatencyStats(verification_latencies_ms=latencies)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def main() -> None:
    from eval.cassette import MODE
    from eval.report import write_report

    reset_live_call_count()
    scenarios = load_corpus()

    start = time.perf_counter()
    corpus_result, latency_stats = run_corpus(scenarios)
    wall_clock_s = time.perf_counter() - start

    write_report(
        corpus_result,
        latency_stats,
        generated_at=datetime.now(timezone.utc),
        mode=MODE,
        commit=_git_commit(),
        n_scenarios=len(scenarios),
        n_samples=N_SAMPLES,
        live_call_count=get_live_call_count(),
        wall_clock_s=wall_clock_s,
    )


if __name__ == "__main__":
    main()
