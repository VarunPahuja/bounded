# ADR-0013: Phase 6 eval harness — judge granularity, pass^k aggregation, mocked rail, and the injection-context isolation

- Status: Accepted
- Date: 2026-09-02
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

Phase 6 (`docs/MASTER.md`, `docs/PHASE6-PLAN.md`) needed an eval harness
comparing our real pipeline (`policy.parse.parse_mandate` ->
`rail.interceptor.propose_action`, Z3-backed) against a deliberately-built
LLM-as-judge baseline, across a pilot scenario corpus, reporting pass^k
(tau-bench definition), false-positive rate on benign flows, violations
caught by class, and an unsound-safe count that must be zero. Several design
decisions here are real architectural choices, not incidental
implementation detail, and one of them was corrected mid-build after the
pilot run's first live measurement surfaced a genuine bug in the baseline
itself. This ADR names all of them together, since they only make sense
read as one design.

## Decision

**1. The judge decides per action, not per trace.** `eval.baseline_llm_judge.judge_action`
is called once per proposed action, given the mandate text, the sequence of
already-decided actions in this trial (`history`), and — only for the
action it is directly associated with — any `injection_context`. This
matches the granularity of `rail.interceptor.propose_action` (one call per
action) exactly, so `matched`/pass^k are computed over identical decision
units on both sides of the comparison, and so a per-action verdict sequence
can be scored the same way for both pipelines even on multi-step classes
(split-refund, category-then-violation).

**2. pass^k is macro-averaged per scenario, never pooled from raw counts.**
For each scenario, `c` = trials matched out of `n=8`; `pass_hat_k(n, c, k)`
is computed per scenario, then averaged across scenarios (per class and
corpus-wide). `C(c,k)/C(n,k)` is nonlinear in `c`, so pooling successes
across scenarios before computing pass^k would misrepresent a corpus mixing
scenarios with very different per-scenario reliability.

**3. The Razorpay rail is mocked in every eval trial, not the parser, not
the solver, not the ledger.** `rail.interceptor.attempt_capture` /
`.refund` are patched to a synthetic success in `eval.runner.run_ours_trial`.
Phase 3 and Phase 4 already prove the rail works, against real Razorpay
test mode, without mocking (`tests/rail/test_razorpay_client_live.py`,
`tests/rail/test_interceptor.py::test_compliant_action_executes`) — that
claim doesn't need re-proving here, and CLAUDE.md's ban on mocking the rail
call that's supposed to prove it works is scoped to that claim, not to this
one. This harness measures verdicts (does the pipeline reach the correct
allow/block decision), which sits entirely upstream of the rail call. This
is stated as the first thing in `docs/EVAL.md`, not left for a reader to
infer from the code.

**4. injection_context is structurally unreachable from the "ours" pipeline,
not just conventionally excluded.** `eval.scenario.Scenario.pipeline_input()`
returns a `PipelineInput` with no `injection_context` field at all —
`run_ours_trial` is typed against `PipelineInput`, so there is no attribute
to accidentally read. Two tests pin this from different angles:
`test_pipeline_input_never_carries_injection_context` (the type itself) and
`test_ours_pipeline_never_reads_injection_context` (an AST/source-text walk
of `run_ours_trial` specifically, not the whole runner module, since
`run_judge_trial` legitimately reads the field — that's the asymmetry being
measured, not a bug).

**5. The judge's response schema puts `reasoning` before `decision` —
corrected from `decision` before `reasoning` after the first live pilot run
produced a self-contradicting baseline.** See "How this was found" below.

**6. The `category_count_violation` class tests category (P4) only — no
scenario asks the pipeline to catch a pure transaction-count violation.**
`contracts.models.PolicyIR.max_txn_count` is parsed by `policy/parse.py`
and validated (`_max_txn_count_requires_window`) but is not encoded
anywhere in `verifier/` — `properties_checked` never mentions it, and
neither `sound_capture_guard` nor `invariant_holds` reads it (confirmed by
grep before authoring this class's scenarios: `contracts/models.py` is the
only hit for `max_txn_count` outside `policy/parse.py`). This is not new —
`docs/LOG.md`'s Phase 2 entry already names `max_txn_count` and
`require_human_above_paise` as "genuinely out-of-scope fields... visibly
absent from `properties_checked`." A scenario asserting `expected_decision:
block` on a fourth transaction under a stated `max_txn_count: 3` would fail
100% of the time, correctly, because nothing enforces that constraint — not
a pipeline bug, a scope boundary already on record. Writing such a scenario
into the pilot corpus would misrepresent a known, already-declared gap as a
fresh miss. All three scenarios in this class (`cat-001`, `cat-002`,
`cat-003`) exercise `allowed_categories`/`blocked_categories` instead, which
is fully enforced (P4).

## How this was found

The first full live recording (`EVAL_MODE=record`, prompt v1: response
shape `{"decision": ..., "reasoning": ...}`) reported a 100% false-positive
rate on the benign slice: 48/48 benign trials, across all 6 benign
scenarios and all 8 samples each, came back `"BLOCK"`. Before reporting that
number, the recorded cassette for `benign-001-single-capture-within-cap`'s
first (and only) action was read directly. Every one of its 8 samples had
`decision: "BLOCK"` and a `reasoning` string that concluded, in its own
words, "...so it should be allowed" — e.g. sample 2: *"The proposed payment
of Rs 2,000 exceeds the per-payment cap of Rs 3,000, so it should be
allowed."* (self-contradictory on its face — Rs 2,000 does not exceed Rs
3,000 — but the point here is narrower: whatever the model's stated
reasoning concluded, the decision field disagreed with it, on 48/48
trials).

The response schema in prompt v1 asked for `decision` first, `reasoning`
second — the same order as the field names in the example JSON in the
prompt. With `response_format={"type": "json_object"}`, gpt-4.1-mini
generates the object's fields in the order the schema/example presents
them: it commits to a `decision` token before a single token of
`reasoning` exists to inform it, then the reasoning text is generated
afterward as a post-hoc rationalization that frequently disagrees with the
decision already locked in. This is not an adversarial-robustness finding
about the judge (nothing here is a prompt-injection case) and not a
"judges are unreliable" finding worth reporting as this project's baseline
comparison — it is a schema-ordering bug in this baseline's own prompt,
introduced by this project, discovered by reading the raw cassette rather
than trusting a suspiciously round percentage.

Fixed by reordering the schema to `{"reasoning": ..., "decision": ...}` and
telling the model explicitly to reason before deciding
(`eval/baseline_llm_judge.py`, `PROMPT_VERSION` bumped `v1` -> `v2` so the
cassette key changes and replay can never silently score the new prompt
against the old recordings). Re-run live: benign false-positive rate
dropped to 0/48 (0.0%), and the corpus-wide comparison became the one
`docs/EVAL.md` actually reports — judge pass^1 100% on `over_cap` and
`category_count_violation`, 0% on `refund_exceeds_capture` (it never
reliably catches the split-refund pattern across two calls with no shared
counter), 50%/34%/33% (k=1/4/8) on `prompt_injection`, and 12 unsound-safe
verdicts corpus-wide (real instances of a stated violation the judge marked
ALLOW) — a coherent, reportable comparison, not an artifact of a broken
baseline. The v1 cassettes were not deleted; they remain on disk as the
record of what was actually observed, orphaned by the prompt-version bump
rather than overwritten.

## Alternatives considered

### Report the v1 100% FP number as the headline judge result
Rejected outright. MASTER.md's own framing — "the LLM proposes structure,
the solver decides," and honesty as "a scoring asset, not a liability" —
would be actively contradicted by shipping a result known, from reading the
raw output, to be an artifact of this project's own prompt bug rather than
a property of LLM-judge guardrails in general. A reviewer who reads the
cassette (as this build did) would find the same contradiction in minutes.

### Fix the schema silently, re-record, never mention v1 happened
Rejected. The failed-payment hunt in Phase 3 and the Groq/Gemini invented-
narrative catch in Phase 5's ADR-0012 both established the same standing
practice in this project: an observed dead end, once found, gets written
down, not smoothed over. This is the same category of event — a
self-contradictory model output, caught by checking the raw recording
instead of trusting an aggregate number — and belongs in the record for the
same reason those did.

### Pool pass^k successes across scenarios instead of macro-averaging
Rejected — see Decision #2. Nonlinearity in `C(c,k)/C(n,k)` makes pooled
counts a different (and less meaningful) statistic than an average of
per-scenario pass^k values.

## Consequences

Positive:
- The judge comparison in `docs/EVAL.md` is now a fair fight: a
  reasonably-constructed LLM-judge baseline, not a strawman broken by a
  prompt bug this project introduced. The result that remains — the judge
  matches well on straightforward per-action cap/category checks, fails
  outright on cross-call split-refund reasoning, and is meaningfully (not
  totally) foolable by injected instructions — is the comparison MASTER.md
  actually wanted.
- The discovery method (read the raw cassette before trusting the
  percentage) is now the standing practice for any future baseline number
  in this project that looks suspiciously extreme.

Negative / accepted costs:
- The pilot run had to be executed twice against live Azure credits (376
  calls, then 248 more after the schema fix — the parse-side cassettes
  were reused unchanged, only the judge cassettes needed re-recording).
  Both draws are still a rounding error against the committed balance named
  in `docs/MASTER.md` section 2.
- `eval/cassettes/` now holds orphaned v1 judge cassettes (prompt_version
  `2026-09-01-v1`) that no code path references anymore. Left in place
  deliberately, as the evidentiary record of what v1 actually produced,
  rather than deleted for tidiness.

## Revisit when

- The full 60-100 scenario corpus is authored (docs/MASTER.md Phase 6) —
  re-run recording against it; nothing in this ADR's decisions is
  pilot-scale-specific, so none of them should need to change at that size.
- `max_txn_count` gets real Z3 enforcement (out of scope for Phase 6, and
  for this project's 5 September deadline per MASTER.md section 7) — at
  that point `category_count_violation` scenarios can be added that
  actually exercise a transaction-count breach, and the class name stops
  being a slight misnomer for what it tests today.
