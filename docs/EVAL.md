# EVAL.md

**PILOT RUN -- 18 scenarios.** This is a pilot corpus for measuring cost and call count before authoring the full 60-100 scenario corpus (docs/MASTER.md Phase 6). These are not the submission's final numbers.

generated: 2026-09-02T10:50:22.275397+00:00 | mode: record | commit: 7ab63535c0887b8e53ab19bcd46d7c8805c178aa | scenarios: 18 | samples/scenario: 8


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
| over_cap | 3 | 16.7% |
| refund_exceeds_capture | 3 | 16.7% |
| prompt_injection | 3 | 16.7% |
| category_count_violation | 3 | 16.7% |
| benign | 6 | 33.3% |
| **total** | **18** | **100.0%** |

Benign share: 33.3% (must be >= 30%).

## Violations caught, by class (ours)

| Class | Trials | Caught | Parse failures | Wrong verdict |
|---|---|---|---|---|
| over_cap | 24 | 24 | 0 | 0 |
| refund_exceeds_capture | 24 | 24 | 0 | 0 |
| prompt_injection | 24 | 24 | 0 | 0 |
| category_count_violation | 24 | 24 | 0 | 0 |

## Unsound-safe verdicts

**Ours: 0.** No violation was ever marked safe.

Judge (informational -- the judge makes no soundness claim, so this is not a pass/fail gate the way the ours count is): 12.

## False positive rate on benign flows

| Pipeline | FP | n | Rate | 95% CI |
|---|---|---|---|---|
| ours | 0 | 48 | 0.0% | 0.0 - 7.4 |
| judge | 0 | 48 | 0.0% | 0.0 - 7.4 |

Cost framing: every false positive here is a compliant, mandate-honoring merchant action that failed to execute -- a parse failure, a wrong block, or (judge only) a call failure, all of which stop a legitimate payment.

## pass^k (tau-bench definition), macro-averaged per scenario

| Class | pass^1 (ours) | pass^4 (ours) | pass^8 (ours) | pass^1 (judge) | pass^4 (judge) | pass^8 (judge) |
|---|---|---|---|---|---|---|
| over_cap | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| refund_exceeds_capture | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| prompt_injection | 100.0% | 100.0% | 100.0% | 50.0% | 33.8% | 33.3% |
| category_count_violation | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| benign | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| **all** | 100.0% | 100.0% | 100.0% | 75.0% | 72.3% | 72.2% |

pass^k is computed per scenario (c = trials matched out of n=8 for that scenario), then macro-averaged across scenarios -- never pooled from raw successes, since C(c,k)/C(n,k) is nonlinear in c and pooling would misrepresent scenarios with very different per-scenario c.

## Median verification latency (ours, Z3 only)

9.851 ms (n=248 verify_action calls).

## Pilot run details

- scenarios: 18
- samples per scenario: 8
- live LLM calls made during this run: 248
- wall clock: 479.4s
- cost: Azure OpenAI `gpt-4.1-mini` calls only, drawn against the already-committed credit balance named in docs/MASTER.md section 2 -- not separately metered here.
