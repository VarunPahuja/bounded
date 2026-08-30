# ADR-0005: The LLM proposes structure; only the solver decides

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

The project's entire thesis is that a bounded-horizon SMT proof is a
sounder gate on agent money actions than an LLM reviewing a proposed
action and judging whether it complies. That thesis only holds if the
architecture actually keeps the LLM out of the decision. An LLM in the
enforcement path — even one only "double-checking" a solver verdict — is
exactly the failure mode this project measures against as the baseline
(`docs/CONTEXT.md`, "LLM-as-judge guardrails"), and it reintroduces
prompt injection as a live attack surface on the thing that is supposed
to be immune to it.

## Decision

The LLM has exactly two jobs, both structural, neither about compliance:
parse natural-language mandates into a typed `PolicyIR` (`policy/parse.py`),
and write human-readable explanations of solver output. It never
evaluates whether a money action is allowed. Compliance is decided solely
by `encode(policy_ir) -> z3.Solver` (`verifier/`) and its `check()` /
`model()` result.

This is enforced architecturally, not just by convention: `verifier/`
must never import from `policy/parse.py` or any LLM client. A test
(`test_parse_is_not_in_enforcement_path`, Phase 5) asserts this by
inspecting imports. If satisfying a test or a feature ever requires
crossing that boundary, the correct response is to stop and say so, not
to add the import.

## Alternatives considered

### LLM as a second opinion after the solver
Rejected: any path where an LLM verdict can override, veto, or gate an
already-SAT/UNSAT solver result reintroduces a natural-language attack
surface into the enforcement decision. "Advisory only" degrades to
"load-bearing" the first time someone wires its output into a condition.

### LLM validates the parsed IR against the mandate text before compiling
Rejected: this asks the model to judge whether a policy correctly
reflects intent, which is a compliance judgment wearing a parsing
costume. The IR either validates against `contracts/models.py`'s
Pydantic constraints or it doesn't; that check is deterministic and
belongs to `policy/ir.py`, not a second LLM call.

### Single LLM call that both parses and explains inline during
verification
Rejected: couples the enforcement path's timing and failure modes to an
LLM API call (rate limits, latency, malformed JSON) at the moment a money
action is being gated. Parsing happens once, at mandate-creation time,
fully separated from the per-action verification loop.

## Consequences

Positive:
- The core claim — proof, not judgment, gates money actions — is true of
  the code, not just the pitch.
- Prompt injection against the LLM layer (Phase 6, class 3 scenarios) can
  at worst produce a malformed or rejected `PolicyIR`, which fails closed
  via Pydantic validation; it cannot forge a SAT verdict.
- The eval harness's LLM-as-judge baseline is a genuinely different
  architecture from the project's own gate, not a strawman.

Negative / accepted costs:
- A correctly-parsed policy still has to be reviewed by a human before
  it's live (the confirmation step in Phase 5) — the system does not
  get to skip that step by trusting the LLM's parse.
- Every new policy field needs both a Pydantic constraint and a Z3
  encoding; the LLM can't paper over a gap in either with judgment calls.

## Revisit when

- A future phase considers any form of LLM-assisted anomaly detection or
  triage — that is allowed only as a signal that *routes to* the solver
  or a human, never as something that can itself allow or block an
  action.
