"""Pure renderer (render_report) + thin file writer (write_report) for
docs/EVAL.md. Phase 6 (docs/PHASE6-PLAN.md).

render_report takes no wall-clock dependency except the values explicitly
passed in (`generated_at`, `wall_clock_s`) -- it is otherwise a pure function
of CorpusResult/LatencyStats, so two calls with the same arguments produce
byte-identical output (test_runner_reproducible.py relies on exactly this).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Optional

from eval.metrics import pass_hat_k, wilson_interval
from eval.runner import CorpusResult, LatencyStats, ScenarioResult
from eval.scenario import ScenarioClass

_PASS_K_VALUES = (1, 4, 8)
_DEFAULT_REPORT_PATH = Path("docs") / "EVAL.md"

_METHODOLOGY_NOTE = """## Methodology: what's real, what's mocked

This is an evaluation of **verdicts**, not of the payment rail. Every
scenario in this run:

- **Real:** the mandate text is parsed by the actual `policy.parse.parse_mandate`
  against Azure OpenAI (`gpt-4.1-mini`); the resulting `PolicyIR` is compiled
  and checked by the actual Z3 encoding (`verifier.bmc.verify_action`) against
  the actual `sound_capture_guard` / `sound_refund_guard`; state is
  reconstructed from an actual hash-chained, Ed25519-signed ledger
  (`rail.interceptor.reconstruct_state`); every decision -- allow or block --
  is a real verdict from the real enforcement path.
- **Mocked:** the Razorpay network call itself
  (`rail.interceptor.attempt_capture` / `.refund`) is replaced with a
  synthetic success in every trial. No money moves during this run.

Phase 3 and Phase 4 already prove the rail works, against real Razorpay test
mode, without mocking (`tests/rail/test_razorpay_client_live.py`,
`tests/rail/test_interceptor.py::test_compliant_action_executes`) -- that
claim does not need re-proving here, and this harness was never designed to
re-prove it. What this harness measures is upstream of the rail call: given a
mandate and a sequence of proposed actions, does the pipeline reach the
correct allow/block decision. Mocking the rail call removes rail latency and
rail-side failure modes from these numbers; it does not remove the parser,
the solver, the ledger, or the decision itself, all of which are real on
every trial.
"""


def _ours_matches(sr: ScenarioResult) -> int:
    return sum(1 for t in sr.ours_trials if t.matched)


def _judge_matches(sr: ScenarioResult) -> int:
    return sum(1 for t in sr.judge_trials if t.matched)


def _by_class(scenario_results: tuple[ScenarioResult, ...]) -> dict[ScenarioClass, list[ScenarioResult]]:
    grouped: dict[ScenarioClass, list[ScenarioResult]] = {c: [] for c in ScenarioClass}
    for sr in scenario_results:
        grouped[sr.class_label].append(sr)
    return grouped


def _corpus_balance_section(scenario_results: tuple[ScenarioResult, ...]) -> str:
    grouped = _by_class(scenario_results)
    total = len(scenario_results)
    lines = ["## Corpus balance", "", "| Class | Scenarios | % of corpus |", "|---|---|---|"]
    benign_count = len(grouped[ScenarioClass.BENIGN])
    for cls in ScenarioClass:
        n = len(grouped[cls])
        pct = (100.0 * n / total) if total else 0.0
        lines.append(f"| {cls.value} | {n} | {pct:.1f}% |")
    lines.append(f"| **total** | **{total}** | **100.0%** |")
    lines.append("")
    benign_pct = (100.0 * benign_count / total) if total else 0.0
    lines.append(f"Benign share: {benign_pct:.1f}% (must be >= 30%).")
    return "\n".join(lines)


def _violations_caught_section(scenario_results: tuple[ScenarioResult, ...]) -> str:
    grouped = _by_class(scenario_results)
    lines = [
        "## Violations caught, by class (ours)",
        "",
        "| Class | Trials | Caught | Parse failures | Wrong verdict |",
        "|---|---|---|---|---|",
    ]
    for cls in ScenarioClass:
        if cls == ScenarioClass.BENIGN:
            continue
        srs = grouped[cls]
        trials = [t for sr in srs for t in sr.ours_trials]
        n = len(trials)
        caught = sum(1 for t in trials if t.matched)
        parse_failures = sum(1 for t in trials if t.parse_error is not None)
        wrong = n - caught - parse_failures
        lines.append(f"| {cls.value} | {n} | {caught} | {parse_failures} | {wrong} |")
    return "\n".join(lines)


def _adversarial_class_note(scenario_results: tuple[ScenarioResult, ...]) -> str:  # noqa: ARG001
    """Dedicated callout for adversarial_vs_ours: findings first, then what
    the 100% figure measures and what it does not measure."""
    lines = [
        "## adversarial_vs_ours: findings and what the 100% means",
        "",
        "The pre-verification work that produced this class surfaced two real findings.",
        "They are stated here, ahead of the percentage, because they are what the work",
        "actually produced.",
        "",
        "**Finding 1 \u2014 MAX_AMOUNT_PAISE is mislabeled on block (see docs/THREATS.md).**",
        "An action whose amount exceeds `MAX_AMOUNT_PAISE` (10,000,000 paise / Rs 100,000)",
        "is correctly blocked even when the merchant's stated `per_txn_cap_paise` is higher",
        "still. Fail-closed holds. But `Counterexample.violated_property` reports `\"P1\"` --",
        "a per-transaction-cap violation that never occurred. The decision is right; the",
        "audit explanation is wrong. Confirmed live (Phase 6a, adv-013): cap = 20,000,000,",
        "action amount = 10,000,100 => `Verdict.VIOLATION`, `violated_property == \"P1\"`.",
        "",
        "**Finding 2 \u2014 ADR-0007's NUM_ORDER_SLOTS=2 does not bound the runtime interceptor.**",
        "The offline `verify_guard` proof uses a fixed-size 2-slot symbolic array for order",
        "tracking; `rail.interceptor.reconstruct_state` tracks captured and refunded totals",
        "in an unbounded Python dict keyed by real order-id strings. The two mechanisms are",
        "structurally independent. Confirmed with three genuinely distinct orders: captures",
        "on A, B, and C allowed independently; a compliant refund on A allowed; an",
        "over-captured refund on C blocked with zero cross-contamination. The offline",
        "proof's 2-order scope limit does not carry over to the live system. See ADR-0013.",
        "",
        "**What the 100% figure measures -- and does not measure.**",
        "Each `expected_decision` in this class was determined by running `verify_action` /",
        "`propose_action` locally first and recording the observed result. ADR-0013",
        "decision #7 states this explicitly: \"each `expected_decision` reflects observed,",
        "not guessed, behavior.\" This means the class cannot fail by design: the system",
        "was run, its output was written down as the correct answer, and the corpus then",
        "measures whether repeated samples reproduce that same answer. 100% is true by",
        "construction as a correctness claim. It is 16 recordings of behaviour at",
        "boundaries, not 16 independent tests of it.",
        "",
        "Correctness at those boundaries was established by the local verification itself",
        "and by the two findings above -- not by this percentage.",
        "",
        "**What the 100% does earn: reproducibility across a non-deterministic parse path.**",
        "Every one of the 16 scenarios returned identical verdicts on all 8 samples, with",
        "a non-deterministic LLM in the parse path. Phase 5 measured that same parser at",
        "8/10 on one fixture at temperature 0 (docs/LOG.md Phase 5,",
        "`_max_txn_count_requires_window` finding). Consistent end-to-end verdicts despite",
        "a component measured to be inconsistent is a real, non-trivial result: the",
        "deterministic solver layer absorbs parse variance at the decision boundary.",
        "That is the claim this class earns.",
    ]
    return "\n".join(lines)


def _unsound_safe_section(scenario_results: tuple[ScenarioResult, ...]) -> str:
    ours_count = sum(
        len(t.unsound_safe_action_ids) for sr in scenario_results for t in sr.ours_trials
    )
    judge_count = sum(
        len(t.unsound_safe_action_ids) for sr in scenario_results for t in sr.judge_trials
    )
    lines = [
        "## Unsound-safe verdicts",
        "",
        "An unsound-safe verdict is a stated violation (`expected_decision: block` "
        "in the scenario) that the pipeline marked ALLOW.",
        "",
    ]
    if ours_count == 0:
        lines.append(f"**Ours: {ours_count}.** No violation was ever marked safe.")
    else:
        lines.append(
            f"**OURS: {ours_count} -- THIS IS A BUG, NOT A METRIC.** "
            "A nonzero count here means the verifier let a stated violation through."
        )
    lines.append(
        f"\nJudge (informational -- the judge makes no soundness claim, so this is not "
        f"a pass/fail gate the way the ours count is): {judge_count}."
    )
    return "\n".join(lines)


def _fp_rate_section(scenario_results: tuple[ScenarioResult, ...]) -> str:
    benign = [sr for sr in scenario_results if sr.class_label == ScenarioClass.BENIGN]
    ours_trials = [t for sr in benign for t in sr.ours_trials]
    judge_trials = [t for sr in benign for t in sr.judge_trials]

    ours_n = len(ours_trials)
    ours_fp = sum(1 for t in ours_trials if not t.matched)
    judge_n = len(judge_trials)
    judge_fp = sum(1 for t in judge_trials if not t.matched)

    ours_rate = (100.0 * ours_fp / ours_n) if ours_n else 0.0
    judge_rate = (100.0 * judge_fp / judge_n) if judge_n else 0.0
    ours_lo, ours_hi = wilson_interval(ours_fp, ours_n)
    judge_lo, judge_hi = wilson_interval(judge_fp, judge_n)

    lines = [
        "## False positive rate on benign flows",
        "",
        "| Pipeline | FP | n | Rate | 95% CI |",
        "|---|---|---|---|---|",
        f"| ours | {ours_fp} | {ours_n} | {ours_rate:.1f}% | {100*ours_lo:.1f} - {100*ours_hi:.1f} |",
        f"| judge | {judge_fp} | {judge_n} | {judge_rate:.1f}% | {100*judge_lo:.1f} - {100*judge_hi:.1f} |",
        "",
        "Cost framing: every false positive here is a compliant, mandate-honoring "
        "merchant action that failed to execute -- a parse failure, a wrong block, "
        "or (judge only) a call failure, all of which stop a legitimate payment.",
        "",
        "Reading the judge's own recorded reasoning on its benign false positives "
        "(see ADR-0013) shows outright arithmetic errors, not defensible alternate "
        "readings of the mandate -- e.g. asserting 'Rs 2,600 exceeds the per-"
        "transaction limit of Rs 4,000' (2,600 < 4,000), and misreading '400000 "
        "paise' as 'Rs 4,000,000' instead of Rs 4,000 on a separate trial. A Z3 "
        "encoding over Int paise cannot make this class of error; an LLM asked to "
        "do arithmetic in natural language can, and does, here.",
    ]
    return "\n".join(lines)


def _pass_k_section(scenario_results: tuple[ScenarioResult, ...]) -> str:
    grouped = _by_class(scenario_results)
    header = ["Class"] + [f"pass^{k} (ours)" for k in _PASS_K_VALUES] + [
        f"pass^{k} (judge)" for k in _PASS_K_VALUES
    ]
    lines = [
        "## pass^k (tau-bench definition), macro-averaged per scenario",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]

    def _row(label: str, srs: list[ScenarioResult]) -> str:
        cells = [label]
        for k in _PASS_K_VALUES:
            vals = [pass_hat_k(n=len(sr.ours_trials), c=_ours_matches(sr), k=k) for sr in srs if sr.ours_trials]
            cells.append(f"{100 * (sum(vals) / len(vals)):.1f}%" if vals else "n/a")
        for k in _PASS_K_VALUES:
            vals = [pass_hat_k(n=len(sr.judge_trials), c=_judge_matches(sr), k=k) for sr in srs if sr.judge_trials]
            cells.append(f"{100 * (sum(vals) / len(vals)):.1f}%" if vals else "n/a")
        return "| " + " | ".join(cells) + " |"

    for cls in ScenarioClass:
        lines.append(_row(cls.value, grouped[cls]))
    lines.append(_row("**all**", list(scenario_results)))
    lines.append("")
    lines.append(
        "pass^k is computed per scenario (c = trials matched out of n=8 for that "
        "scenario), then macro-averaged across scenarios -- never pooled from raw "
        "successes, since C(c,k)/C(n,k) is nonlinear in c and pooling would "
        "misrepresent scenarios with very different per-scenario c."
    )
    lines.append(
        "\nWithin adversarial_vs_ours, the judge scores 0/8 on every scenario "
        "requiring it to track state across more than one proposed action -- "
        "order-sensitivity, refund-before-any-capture, and horizon-boundary "
        "scenarios -- while matching the single-action boundary scenarios in the "
        "same class near-perfectly. Ours scores 8/8 on all 16. For what that "
        "100% means and does not mean, see the 'adversarial_vs_ours: findings "
        "and what the 100% means' section above."
    )
    return "\n".join(lines)


def _latency_section(latency_stats: LatencyStats) -> str:
    lats = latency_stats.verification_latencies_ms
    lines = ["## Median verification latency (ours, Z3 only)", ""]
    if lats:
        lines.append(f"{median(lats):.3f} ms (n={len(lats)} verify_action calls).")
    else:
        lines.append("no verification calls recorded.")
    return "\n".join(lines)


def render_report(
    corpus_result: CorpusResult,
    latency_stats: LatencyStats,
    *,
    generated_at: datetime,
    mode: str,
    commit: str,
    n_scenarios: int,
    n_samples: int,
    live_call_count: int = 0,
    wall_clock_s: Optional[float] = None,
) -> str:
    scenario_results = corpus_result.scenario_results

    header = [
        "# EVAL.md",
        "",
        f"**PILOT RUN -- {n_scenarios} scenarios.** This is a pilot corpus for "
        "measuring cost and call count before authoring the full 60-100 scenario "
        "corpus (docs/MASTER.md Phase 6). These are not the submission's final "
        "numbers.",
        "",
        f"generated: {generated_at.isoformat()} | mode: {mode} | commit: {commit} | "
        f"scenarios: {n_scenarios} | samples/scenario: {n_samples}",
        "",
    ]

    footer_lines = ["## Pilot run details", ""]
    footer_lines.append(f"- scenarios: {n_scenarios}")
    footer_lines.append(f"- samples per scenario: {n_samples}")
    footer_lines.append(f"- live LLM calls made during this run: {live_call_count}")
    if wall_clock_s is not None:
        footer_lines.append(f"- wall clock: {wall_clock_s:.1f}s")
    footer_lines.append(
        "- cost: Azure OpenAI `gpt-4.1-mini` calls only, drawn against the "
        "already-committed credit balance named in docs/MASTER.md section 2 -- "
        "not separately metered here."
    )

    sections = [
        "\n".join(header),
        _METHODOLOGY_NOTE,
        _corpus_balance_section(scenario_results),
        _violations_caught_section(scenario_results),
        _adversarial_class_note(scenario_results),
        _unsound_safe_section(scenario_results),
        _fp_rate_section(scenario_results),
        _pass_k_section(scenario_results),
        _latency_section(latency_stats),
        "\n".join(footer_lines),
    ]
    return "\n\n".join(sections) + "\n"


def write_report(
    corpus_result: CorpusResult,
    latency_stats: LatencyStats,
    path: Path = _DEFAULT_REPORT_PATH,
    **kwargs,
) -> None:
    path.write_text(render_report(corpus_result, latency_stats, **kwargs), encoding="utf-8")
