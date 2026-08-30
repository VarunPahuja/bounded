# CLAUDE.md

Read `docs/MASTER.md` before doing anything. It is the source of truth for scope, stack, and phases. This file is how you operate.

## The one rule that cannot be broken

**The LLM proposes structure. The solver decides.**

An LLM parses natural language into a typed policy object and writes human-readable explanations. It never decides whether a money action is allowed. If you ever find yourself writing a prompt that asks a model to judge compliance, stop and say so. That inversion is the entire thesis of this project and breaking it makes the work worthless.

Architectural consequence: `verifier/` must never import from `policy/parse.py` or any LLM client. There is a test asserting this.

## Phase discipline

Phases are gated. Phase N does not begin until every test in Phase N-1 passes. When I ask you to start a phase, first run the previous phase's tests and tell me if anything is red.

At the end of each phase, append to `docs/LOG.md`: date, phase, what shipped, what broke, what changed my mind. Write what actually happened including the dead ends. This file is source material for the submission, and invented struggle reads as invented.

## Working style

- Plan before building. For anything larger than a single function, propose the approach and wait for approval.
- Show full files, not diffs.
- Run `pytest` before claiming anything is done. "Should work" is not done.
- Do not add dependencies without asking. The stack is locked in MASTER.md section 2.
- Do not add scope. If you think a feature is missing, say so, do not build it.
- Keep comments minimal. Explain why, never what.

## Things that are never acceptable

- Widening a policy, loosening a constraint, or lowering a bound to make a test pass. If a test fails, either the implementation is wrong or the test encodes a wrong expectation. Say which one you think it is and stop.
- Marking a violating action as safe under any circumstance. Solver timeout, exception, malformed input, missing state: all of these block. Fail closed, always.
- Mocking away the Razorpay call in a test that claims to prove the rail works.
- Editing `contracts/models.py` without explicit approval. It is frozen after Phase 0. Every layer depends on it.
- Deleting or rewriting an ADR. Decisions get amended with a new entry, not erased.
- Silently catching an exception in the enforcement path.

## Money handling

All amounts are integer paise, never floats, never rupees. Razorpay's API is paise. The Z3 encoding uses `Int`, not `Real`. A float anywhere in the money path is a bug.

## Commands

```
pytest                      # all tests
pytest tests/verifier -v    # Z3 core only
python -m eval.runner       # red team harness, writes docs/EVAL.md
```

## Repo map

```
docs/MASTER.md      scope, stack, phases, tests
docs/LOG.md         append-only build log
docs/adr/           architecture decisions
contracts/models.py frozen types, treaty file
verifier/           Z3 encoding and bounded model checker
policy/             typed IR and NL parser
rail/               Razorpay client and interceptor
ledger/             hash chain and signatures
eval/               scenarios, runner, baseline
web/                Next.js dashboard
```

## Deadline

5 September. Phase 1 must be green by 31 August or we drop to the fallback ladder in MASTER.md section 4. If we are behind, tell me plainly rather than optimistically.
