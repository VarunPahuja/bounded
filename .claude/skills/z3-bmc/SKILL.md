---
name: z3-bmc
description: Bounded model checking with Z3. Use for invariants on permission ladders, approval flows, and transition tables, or when asked to prove a bad state is unreachable and produce a counterexample.
---

# Z3 Bounded Model Checking

Tests sample the input space. BMC exhausts it up to a horizon. For a state machine with 4 rungs, 5 boolean inputs per tick and 10 ticks, there are 32^10 event orderings. You will not write those tests. Z3 checks all of them in under a second, and when a rule breaks it hands back the exact trace.

Use this for logic that is small, discrete, and consequential. It is the wrong tool for anything with real arithmetic over large domains, unbounded loops, or floating point.

## The method

1. Pick the horizon `K` (number of transitions to unroll).
2. Declare one variable per state field per time index `0..K`.
3. Constrain the initial state.
4. Assert the transition relation between `t` and `t+1`, for every `t < K`.
5. Assert the **negation** of the property.
6. `check()`. `unsat` means the property holds for all traces of length K. `sat` means Z3 found a counterexample and `model()` is the trace.

Step 5 is the part people get backwards. You are asking Z3 to find a violation. Failing to find one is the proof.

## Setup

```bash
pip install z3-solver
```

No system Z3 needed, the wheel bundles it.

## Worked model: an autonomy ladder

This is the shape of most "earned permission" systems. An agent starts at the lowest limit, climbs a rung when evidence and a human both allow it, and drops on degradation.

```python
# verification/model.py
from z3 import Int, Bool, And, Or, Not, Implies, If, Solver, sat, unsat

RUNGS = [500, 1000, 2500, 5000]   # currency units, index 0..3
MAX_RUNG = len(RUNGS) - 1
COOLDOWN = 3                      # ticks of freeze after any rung change
K = 10                            # horizon


def build(seed_bug: bool = False):
    s = Solver()
    s.set("timeout", 30_000)

    rung = [Int(f"rung_{t}") for t in range(K + 1)]
    cool = [Int(f"cool_{t}") for t in range(K + 1)]

    # free inputs: Z3 picks the worst possible sequence
    recommend = [Bool(f"recommend_{t}") for t in range(K)]  # agent says "raise"
    approve   = [Bool(f"approve_{t}") for t in range(K)]    # human clicks approve
    evidence  = [Bool(f"evidence_{t}") for t in range(K)]   # Wilson LB over threshold
    drift     = [Bool(f"drift_{t}") for t in range(K)]      # drift detector fired

    for t in range(K + 1):
        s.add(rung[t] >= 0, rung[t] <= MAX_RUNG)
        s.add(cool[t] >= 0, cool[t] <= COOLDOWN)

    s.add(rung[0] == 0, cool[0] == 0)

    for t in range(K):
        promote = And(recommend[t], approve[t], evidence[t],
                      cool[t] == 0, rung[t] < MAX_RUNG)
        clawback = drift[t]

        if seed_bug:
            # promotion evaluated before clawback
            nxt = If(promote, rung[t] + 1, If(clawback, 0, rung[t]))
        else:
            # clawback wins, always
            nxt = If(clawback, 0, If(promote, rung[t] + 1, rung[t]))

        s.add(rung[t + 1] == nxt)
        s.add(cool[t + 1] == If(Or(clawback, promote), COOLDOWN,
                             If(cool[t] > 0, cool[t] - 1, 0)))

    return s, dict(rung=rung, cool=cool, recommend=recommend,
                   approve=approve, evidence=evidence, drift=drift)
```

## Properties

Write each one as "for every tick, this holds". Name them after the sentence you would say in a review.

```python
# verification/properties.py
from z3 import And, Implies, Or, Not
from model import K


def properties(v):
    rung, cool = v["rung"], v["cool"]
    approve, evidence, drift = v["approve"], v["evidence"], v["drift"]

    return {
        "no_promotion_without_human":
            And([Implies(rung[t + 1] > rung[t], approve[t]) for t in range(K)]),

        "no_promotion_without_evidence":
            And([Implies(rung[t + 1] > rung[t], evidence[t]) for t in range(K)]),

        "at_most_one_rung_per_tick":
            And([rung[t + 1] <= rung[t] + 1 for t in range(K)]),

        "cooldown_blocks_promotion":
            And([Implies(cool[t] > 0, rung[t + 1] <= rung[t]) for t in range(K)]),

        "drift_forces_floor":
            And([Implies(drift[t], rung[t + 1] == 0) for t in range(K)]),

        "no_silent_change":
            And([Implies(rung[t + 1] != rung[t], Or(approve[t], drift[t]))
                 for t in range(K)]),
    }
```

## Runner and counterexample decoding

A `sat` result is worthless if you print raw model output. Decode it into a trace a human can read in the PR.

```python
# verification/run.py
from z3 import Not, sat, unsat
from model import build, K, RUNGS
from properties import properties


def trace(m, v):
    rows = []
    for t in range(K):
        flags = [k for k in ("recommend", "approve", "evidence", "drift")
                 if m.eval(v[k][t], model_completion=True)]
        rows.append(
            f"  t={t:>2}  rung={RUNGS[m.eval(v['rung'][t], True).as_long()]:>5}"
            f"  cool={m.eval(v['cool'][t], True)}"
            f"  [{', '.join(flags) or '-'}]"
            f"  ->  rung={RUNGS[m.eval(v['rung'][t+1], True).as_long()]}"
        )
    return "\n".join(rows)


def main(seed_bug=False):
    failures = 0
    for name, prop in properties(build(seed_bug)[1]).items():
        s, v = build(seed_bug)             # fresh solver per property
        p = properties(v)[name]
        s.add(Not(p))
        r = s.check()
        if r == unsat:
            print(f"HOLDS   {name}  (all traces, K={K})")
        elif r == sat:
            failures += 1
            print(f"VIOLATED {name}\n{trace(s.model(), v)}")
        else:
            failures += 1
            print(f"UNKNOWN {name}  ({s.reason_unknown()})")

    # liveness sanity: the ladder must actually be climbable
    s, v = build(seed_bug)
    s.add(v["rung"][K] == 3)
    if s.check() != sat:
        failures += 1
        print("UNKNOWN reachability: no trace reaches the top rung. "
              "The model is probably over-constrained and every safety "
              "property above is vacuously true.")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
```

Run `python run.py` and everything holds. Run with `seed_bug=True` and `drift_forces_floor` fails with a trace where drift and a pending approval land on the same tick and the raise wins. That is the class of bug this catches: not arithmetic, **precedence**.

## The vacuity trap

An over-constrained model proves everything and means nothing. If the guards are contradictory, no trace exists, every safety property is `unsat`, and the report is a wall of green.

Always pair safety checks with at least one reachability check that must be `sat`:

- the top rung is reachable
- a clawback is reachable
- a promotion followed by a clawback followed by a recovery is reachable

If a reachability check comes back `unsat`, stop and fix the model before trusting anything else.

## Keeping the model honest

The model is a second implementation. If it drifts from the real code, you are verifying fiction.

- **Single source for constants.** Import `RUNGS` and `COOLDOWN` from the same module the runtime uses. Never retype them.
- **Transcribe precedence, do not clean it up.** If the real engine checks clawback after promotion, model it that way. The whole point is to find out what the real order allows.
- **Differential test.** Generate random input sequences, run them through the production transition function and through a plain-Python mirror of the Z3 transition, assert the rung sequences match. This is the only thing that stops silent divergence.

```python
# tests/test_model_parity.py
import random
from app.policy.engine import step as prod_step   # your real code
from verification.mirror import step as model_step

def test_parity():
    rng = random.Random(0)
    for _ in range(2000):
        st = {"rung": 0, "cool": 0}
        a, b = dict(st), dict(st)
        for _ in range(20):
            ev = {k: rng.random() < 0.4
                  for k in ("recommend", "approve", "evidence", "drift")}
            a, b = prod_step(a, ev), model_step(b, ev)
            assert a == b, (ev, a, b)
```

## Choosing K

Start at K = 2 x (longest interesting sequence). For a ladder with 4 rungs and a 3 tick cooldown, a full climb takes 12 ticks, so K = 12 to 16.

Sweep it: run K = 4, 8, 12, 16 and watch the runtime. If every property still holds at 16 and solve time is flat, you are fine. If solve time explodes, your encoding has an unbounded integer or a real somewhere. Bound every variable explicitly.

BMC proves nothing beyond K. Say so in the report. For an unbounded proof you need k-induction, which is a much bigger commitment and rarely worth it for a 4 rung ladder.

## Encoding gotchas

- **Bound every integer.** An unbounded `Int` makes the search space infinite and turns `unsat` into `unknown`.
- **No floats.** Use `Real` with rational literals (`RealVal("0.85")`, never `0.85`), or scale to integers. A float threshold silently becomes a binary approximation and off-by-epsilon counterexamples waste an afternoon.
- **`model_completion=True`** when evaluating, or unconstrained variables come back as `None` and your trace printer crashes.
- **Fresh solver per property.** Reusing one solver with `push`/`pop` works, but a stray `add` outside a `push` poisons every later check. Rebuilding is cheap.
- **Set a timeout.** Default is infinite. `s.set("timeout", 30_000)` in ms.
- **`unknown` is not `unsat`.** Print `s.reason_unknown()` and treat it as a failure.

## Report format

Write `verification/REPORT.md` and regenerate it in CI:

```markdown
# BMC report
Horizon K=12 | z3 4.x | generated <date> | commit <sha>

| Property | Result | Time |
|---|---|---|
| no_promotion_without_human | HOLDS | 0.08s |
| drift_forces_floor | HOLDS | 0.11s |

Reachability: top rung SAT, clawback SAT, recover-after-clawback SAT.
Scope: proves no violation in any trace of <=12 transitions from the
initial state. Says nothing about longer traces or about code paths
not represented in verification/model.py.
```

That last paragraph is what stops a reviewer from over-reading the result. Include it every time.

## CI

```yaml
- run: pip install z3-solver
- run: python verification/run.py
- run: pytest tests/test_model_parity.py
```

Non-zero exit on any violation, unknown, or unreachable target. The parity test is not optional, without it the BMC job is decorative.
