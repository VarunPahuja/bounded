"""MASTER.md Phase 6: `python -m eval.runner` must be reproducible from a
clean clone in replay mode. Scope, stated precisely (docs/PHASE6-PLAN.md):

  - Two run_corpus() calls against the same committed cassettes, in replay
    mode, produce CorpusResult-equal output for both pipelines.
  - render_report() called twice with the same fixed, hand-built inputs
    produces byte-identical strings.

This does NOT claim LatencyStats is reproducible (wall-clock, structurally
can't be), that live/record runs are reproducible, or that main()'s actual
written file is byte-identical run to run (it stamps a live timestamp) --
that last piece is exercised at the pure-render layer here instead, with a
fixed `generated_at` passed in directly.
"""

from datetime import datetime, timezone

import eval.cassette
from eval.report import render_report
from eval.runner import (
    CorpusResult,
    JudgeTrialResult,
    LatencyStats,
    OursTrialResult,
    ScenarioResult,
    load_corpus,
    run_corpus,
)
from eval.scenario import ScenarioClass


def test_run_corpus_reproducible_in_replay_mode(monkeypatch):
    monkeypatch.setattr(eval.cassette, "MODE", "replay")
    scenarios = load_corpus()

    result_1, _ = run_corpus(scenarios)
    result_2, _ = run_corpus(scenarios)

    assert result_1 == result_2


def _fixed_corpus_result() -> tuple[CorpusResult, LatencyStats]:
    def ours(matched: bool) -> OursTrialResult:
        return OursTrialResult(
            matched=matched,
            verdicts=("allow",) if matched else ("block",),
            parse_error=None,
            unsound_safe_action_ids=(),
            verification_latencies_ms=(1.5,),
        )

    def judge(matched: bool) -> JudgeTrialResult:
        return JudgeTrialResult(
            matched=matched,
            verdicts=("allow",) if matched else ("block",),
            call_failed_action_ids=(),
            unsound_safe_action_ids=(),
        )

    scenario_results = (
        ScenarioResult(
            scenario_id="fixed-001",
            class_label=ScenarioClass.OVER_CAP,
            ours_trials=tuple(ours(i < 5) for i in range(8)),
            judge_trials=tuple(judge(i < 2) for i in range(8)),
        ),
        ScenarioResult(
            scenario_id="fixed-002",
            class_label=ScenarioClass.BENIGN,
            ours_trials=tuple(ours(True) for _ in range(8)),
            judge_trials=tuple(judge(True) for _ in range(8)),
        ),
    )
    corpus_result = CorpusResult(scenario_results=scenario_results)
    latency_stats = LatencyStats(verification_latencies_ms=tuple(1.5 for _ in range(16)))
    return corpus_result, latency_stats


def test_render_report_is_byte_identical_for_fixed_inputs():
    corpus_result, latency_stats = _fixed_corpus_result()
    generated_at = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    report_1 = render_report(
        corpus_result,
        latency_stats,
        generated_at=generated_at,
        mode="replay",
        commit="deadbeef",
        n_scenarios=2,
        n_samples=8,
        live_call_count=0,
        wall_clock_s=2.5,
    )
    report_2 = render_report(
        corpus_result,
        latency_stats,
        generated_at=generated_at,
        mode="replay",
        commit="deadbeef",
        n_scenarios=2,
        n_samples=8,
        live_call_count=0,
        wall_clock_s=2.5,
    )

    assert report_1 == report_2
