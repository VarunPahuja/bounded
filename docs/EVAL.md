# EVAL.md

**PILOT RUN -- 46 scenarios.** This is a pilot corpus for measuring cost and call count before authoring the full 60-100 scenario corpus (docs/MASTER.md Phase 6). These are not the submission's final numbers.

generated: 2026-09-02T17:42:05.611305+00:00 | mode: replay | commit: c0e6fda754cf479dd4909254282c98316b3dc089 | scenarios: 46 | samples/scenario: 8


## Methodology: what's real, what's mocked

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


## Corpus balance

| Class | Scenarios | % of corpus |
|---|---|---|
| over_cap | 3 | 6.5% |
| refund_exceeds_capture | 3 | 6.5% |
| prompt_injection | 3 | 6.5% |
| category_count_violation | 3 | 6.5% |
| adversarial_vs_ours | 16 | 34.8% |
| benign | 18 | 39.1% |
| **total** | **46** | **100.0%** |

Benign share: 39.1% (must be >= 30%).

## Violations caught, by class (ours)

| Class | Trials | Caught | Parse failures | Wrong verdict |
|---|---|---|---|---|
| over_cap | 24 | 24 | 0 | 0 |
| refund_exceeds_capture | 24 | 24 | 0 | 0 |
| prompt_injection | 24 | 24 | 0 | 0 |
| category_count_violation | 24 | 24 | 0 | 0 |
| adversarial_vs_ours | 128 | 128 | 0 | 0 |

## Unsound-safe verdicts

An unsound-safe verdict is a stated violation (`expected_decision: block` in the scenario) that the pipeline marked ALLOW.

**Ours: 0.** No violation was ever marked safe.

Judge (informational -- the judge makes no soundness claim, so this is not a pass/fail gate the way the ours count is): 48.

## False positive rate on benign flows

| Pipeline | FP | n | Rate | 95% CI |
|---|---|---|---|---|
| ours | 0 | 144 | 0.0% | 0.0 - 2.6 |
| judge | 14 | 144 | 9.7% | 5.9 - 15.7 |

Cost framing: every false positive here is a compliant, mandate-honoring merchant action that failed to execute -- a parse failure, a wrong block, or (judge only) a call failure, all of which stop a legitimate payment.

Reading the judge's own recorded reasoning on its benign false positives (see ADR-0013) shows outright arithmetic errors, not defensible alternate readings of the mandate -- e.g. asserting 'Rs 2,600 exceeds the per-transaction limit of Rs 4,000' (2,600 < 4,000), and misreading '400000 paise' as 'Rs 4,000,000' instead of Rs 4,000 on a separate trial. A Z3 encoding over Int paise cannot make this class of error; an LLM asked to do arithmetic in natural language can, and does, here.

## pass^k (tau-bench definition), macro-averaged per scenario

| Class | pass^1 (ours) | pass^4 (ours) | pass^8 (ours) | pass^1 (judge) | pass^4 (judge) | pass^8 (judge) |
|---|---|---|---|---|---|---|
| over_cap | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| refund_exceeds_capture | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| prompt_injection | 100.0% | 100.0% | 100.0% | 50.0% | 33.8% | 33.3% |
| category_count_violation | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| adversarial_vs_ours | 100.0% | 100.0% | 100.0% | 64.8% | 59.5% | 56.2% |
| benign | 100.0% | 100.0% | 100.0% | 90.3% | 83.8% | 83.3% |
| **all** | 100.0% | 100.0% | 100.0% | 74.2% | 68.7% | 67.4% |

pass^k is computed per scenario (c = trials matched out of n=8 for that scenario), then macro-averaged across scenarios -- never pooled from raw successes, since C(c,k)/C(n,k) is nonlinear in c and pooling would misrepresent scenarios with very different per-scenario c.

Within adversarial_vs_ours, the judge scores 0/8 on every scenario requiring it to track state across more than one proposed action -- order-sensitivity, refund-before-any-capture, and horizon-boundary scenarios -- while matching the single-action boundary scenarios in the same class near-perfectly. Ours scores 8/8 on all 16. See ADR-0013.

## Median verification latency (ours, Z3 only)

4.714 ms (n=808 verify_action calls).

## Pilot run details

- scenarios: 46
- samples per scenario: 8
- live LLM calls made during this run: 0
- wall clock: 9.0s
- cost: Azure OpenAI `gpt-4.1-mini` calls only, drawn against the already-committed credit balance named in docs/MASTER.md section 2 -- not separately metered here.
