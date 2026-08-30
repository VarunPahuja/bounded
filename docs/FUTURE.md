# FUTURE.md

## Gate

**Nothing in this file is started until Phases 0 through 8 are closed.**

Closed means: every phase's tests pass, `docs/LOG.md` has an entry for each phase, the README is written, the video is recorded, and the submission is in a state where it could be sent today. Not "nearly there." Sent-today ready.

The reason for the gate is that everything below is optional and everything in MASTER.md is not. A submission with all phases complete and none of this beats a submission with k-induction and no eval numbers. If the deadline arrives and this file is untouched, nothing has gone wrong.

Work the list top down. Do not start item 2 before item 1 is finished or abandoned.

---

## 1. k-induction: remove the horizon bound

**Value: high. Risk: real. Do this one first or not at all.**

The current claim is soundness to depth k. k-induction can make it unbounded: show the invariant holds over the first k steps from the initial state (base case), then show that if it holds across any k consecutive states it holds in the next (inductive step). If both discharge, the invariant holds for traces of any length.

This changes the central claim from "no admissible sequence of up to 8 actions can breach the policy" to "no admissible sequence can breach the policy." One line in the video, a materially different result.

**Why it might not work:** the invariant may not be inductive. `month_spend <= window_cap` alone is likely too weak, because the inductive step gets to assume an arbitrary state satisfying the invariant, including states unreachable in practice. Strengthening usually means conjoining auxiliary facts (per-order refunded totals bounded by captured totals, non-negativity of every accumulator, action-type well-formedness) until the step discharges.

**How to attempt it:**
1. Implement the base case first. It is the existing BMC run.
2. Implement the inductive step as a separate solver: free state satisfying `Inv`, one admissible transition, assert `Not(Inv')`.
3. If SAT, read the model. It is a state that satisfies the invariant but steps outside it. That state tells you what fact is missing.
4. Add the missing fact to the invariant. Re-run. Iterate.
5. Stop after three strengthening attempts. If it has not discharged by then, write it up as below.

**The honest failure is also valuable.** If k-induction does not discharge, write `docs/adr/00XX-k-induction-attempted.md` recording: what was tried, the counterexample-to-induction that blocked it, and what strengthening would be required. Then state in the README that soundness is bounded and that the unbounded proof was attempted, not overlooked. A judge reading that learns more about you than a feature would tell them.

**Test to add:** `test_invariant_is_inductive`, asserting the inductive step is UNSAT. This test failing is informative, not embarrassing, and should be committed either way.

---

## 2. Widen the evaluation

**Value: high. Risk: none. The safest way to spend spare time.**

- Grow the corpus from ~100 to 250+ scenarios.
- Add attack classes not currently covered: cross-session state confusion, ordering attacks where the same action set breaches in one order and not another, boundary amounts exactly at and one paise either side of every cap, refund-before-capture sequencing, category boundary cases once P4 is symbolic.
- Run the LLM-judge baseline against three models, not one. A single badly-prompted model is a weak comparison and a judge will notice. Give the baseline a genuinely good prompt. Beating a strawman proves nothing.
- Report per-class breakdown rather than a single aggregate number.

Update `docs/EVAL.md`. The table is what gets quoted.

---

## 3. Two-minute clone-to-running

**Value: moderate. Risk: none. Disproportionate return for boring work.**

A judge who clones the repo and sees it working in two minutes evaluates it differently from one who fights setup for twenty.

- `make demo` or a single script: install, run the local MCP server, seed the ledger, execute the full scenario, print results.
- README setup section verified from a clean clone on a machine that has never seen the project.
- Pin every dependency version. No "should work with recent Python."
- Fail loudly and usefully if test keys are missing. A clear "set RAZORPAY_KEY_ID" beats a stack trace.

---

## 4. Adversarial self-review

**Value: moderate. Risk: none.**

Spend an hour trying to break the system, then write `docs/THREATS.md`:

- What this defends against, precisely.
- What it does not. Compromised keys, a malicious merchant, attacks below the modeling granularity, anything outside the bounded horizon and order-slot limits.
- Where the trust boundary sits, and what happens on each side of it.
- Known unmodeled surface: timing, concurrency, replay of valid actions.

Every limitation named here before a judge finds it converts from a weakness into evidence of rigor. Every one they find first makes them wonder what else is unstated.

---

## Explicitly out of scope

Not "later." Not at all, for this submission.

- **Features from other tracks.** Voice recovery, dunning, reconciliation. Bolting on a second track's idea dilutes the one thing this project does well.
- **UI polish past legibility.** Once the counterexample trace is readable and the four surfaces work, stop. Nobody is hired for a gradient.
- **Real deployment or live-mode keys.** Test mode is correct, sufficient, and stated plainly. Live money adds risk and proves nothing.
- **A landing page, a second video, a Devpost writeup, a blog post.** The form asks for a repo, a video, and two written answers.
- **Refactoring for its own sake.** Working code with an honest LOG.md beats clean code with no submission.

---

## The tradeoff worth naming

This window overlaps with other commitments. If all phases close early, spending the spare day on this project is a choice, not an obligation. One serious attempt at k-induction is worth more than a day of small additions, and a day spent elsewhere may be worth more than either.

Decide deliberately. Do not default into it because the repo is open.
