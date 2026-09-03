# EVAL.md

**PILOT RUN -- 46 scenarios.** This is a pilot corpus for measuring cost and call count before authoring the full 60-100 scenario corpus (docs/MASTER.md Phase 6). These are not the submission's final numbers.

generated: 2026-09-03T05:30:59.513697+00:00 | mode: replay | commit: c27a7742b46be86a5e080d93b519f49e5f6d8c87 | scenarios: 46 | samples/scenario: 8


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

## adversarial_vs_ours: findings and what the 100% means

The pre-verification work that produced this class surfaced two real findings.
They are stated here, ahead of the percentage, because they are what the work
actually produced.

**Finding 1 — MAX_AMOUNT_PAISE is mislabeled on block (see docs/THREATS.md).**
An action whose amount exceeds `MAX_AMOUNT_PAISE` (10,000,000 paise / Rs 100,000)
is correctly blocked even when the merchant's stated `per_txn_cap_paise` is higher
still. Fail-closed holds. But `Counterexample.violated_property` reports `"P1"` --
a per-transaction-cap violation that never occurred. The decision is right; the
audit explanation is wrong. Confirmed live (Phase 6a, adv-013): cap = 20,000,000,
action amount = 10,000,100 => `Verdict.VIOLATION`, `violated_property == "P1"`.

**Finding 2 — ADR-0007's NUM_ORDER_SLOTS=2 does not bound the runtime interceptor.**
The offline `verify_guard` proof uses a fixed-size 2-slot symbolic array for order
tracking; `rail.interceptor.reconstruct_state` tracks captured and refunded totals
in an unbounded Python dict keyed by real order-id strings. The two mechanisms are
structurally independent. Confirmed with three genuinely distinct orders: captures
on A, B, and C allowed independently; a compliant refund on A allowed; an
over-captured refund on C blocked with zero cross-contamination. The offline
proof's 2-order scope limit does not carry over to the live system. See ADR-0013.

**What the 100% figure measures -- and does not measure.**
Each `expected_decision` in this class was determined by running `verify_action` /
`propose_action` locally first and recording the observed result. ADR-0013
decision #7 states this explicitly: "each `expected_decision` reflects observed,
not guessed, behavior." This means the class cannot fail by design: the system
was run, its output was written down as the correct answer, and the corpus then
measures whether repeated samples reproduce that same answer. 100% is true by
construction as a correctness claim. It is 16 recordings of behaviour at
boundaries, not 16 independent tests of it.

Correctness at those boundaries was established by the local verification itself
and by the two findings above -- not by this percentage.

**What the 100% does earn: reproducibility across a non-deterministic parse path.**
Every one of the 16 scenarios returned identical verdicts on all 8 samples, with
a non-deterministic LLM in the parse path. Phase 5 measured that same parser at
8/10 on one fixture at temperature 0 (docs/LOG.md Phase 5,
`_max_txn_count_requires_window` finding). Consistent end-to-end verdicts despite
a component measured to be inconsistent is a real, non-trivial result: the
deterministic solver layer absorbs parse variance at the decision boundary.
That is the claim this class earns.

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

Within adversarial_vs_ours, the judge scores 0/8 on every scenario requiring it to track state across more than one proposed action -- order-sensitivity, refund-before-any-capture, and horizon-boundary scenarios -- while matching the single-action boundary scenarios in the same class near-perfectly. Ours scores 8/8 on all 16. For what that 100% means and does not mean, see the 'adversarial_vs_ours: findings and what the 100% means' section above.

## Median verification latency (ours, Z3 only)

5.042 ms (n=808 verify_action calls).

## Pilot run details

- scenarios: 46
- samples per scenario: 8
- live LLM calls made during this run: 0
- wall clock: 8.5s
- cost: Azure OpenAI `gpt-4.1-mini` calls only, drawn against the already-committed credit balance named in docs/MASTER.md section 2 -- not separately metered here.
