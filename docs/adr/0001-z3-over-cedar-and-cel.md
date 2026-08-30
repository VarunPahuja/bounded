# ADR-0001: Z3 as the verification core, not Cedar or Google CEL

- Status: Accepted
- Date: 2026-08-30
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

The project's claim depends on proving that no reachable sequence of agent
actions within a bounded horizon can breach a spending mandate. That proof
has to reason about cumulative state across steps — running `month_spend`,
per-order `captured`/`refunded` totals — not just evaluate a single action
against a static rule. The verification core has to be embeddable directly
in a Python service (FastAPI, five-day build, no separate toolchain to
stand up), and it has to produce a counterexample trace when a proof fails,
because "blocked" without a reason is not a demoable, or defensible, result.

## Decision

Use `z3-solver` (pinned 4.15.4, MIT license) as the sole verification
engine. The payment transition system — state, transitions, properties
P1–P4 — is encoded directly as Z3 constraints over `Int` (never `Real`,
since all amounts are integer paise). Bounded model checking unrolls the
transition relation for `k` steps; `solver.check()` returns UNSAT (safe)
or SAT with `solver.model()` as the counterexample. This lives in
`verifier/` and never imports the LLM layer.

## Alternatives considered

### Cedar (AWS)
Rejected: Cedar's policy language has no cumulative-spend or
running-window model — it evaluates one request against one policy at a
time, which is exactly the per-call check that misses split-transaction
and split-refund attacks. Embedding it also means adding a Rust/Lean
toolchain to a Python stack for a five-day build, for a capability
(access-control style allow/deny) the project doesn't need.

### Google CEL (Common Expression Language)
Rejected: the reference verifier tooling is Java-only. There is no
Python-native embedding path that doesn't mean shelling out to a JVM
process from FastAPI, which adds a runtime dependency and a process
boundary purely for policy evaluation, and CEL still evaluates
expressions statelessly — it has no built-in notion of a transition
system or a reachability proof across steps.

### PySMT
Rejected: PySMT is an abstraction layer over multiple SMT backends
(including Z3). It buys backend portability the project doesn't need and
adds a layer of indirection between the encoding and the actual solver
calls, which slows debugging precisely where debugging matters most —
Phase 1, the highest-risk phase of the whole build.

### TLA+ / Alloy
Rejected: both require a separate modeling language and toolchain outside
Python, with no way to embed the model or drive it from the FastAPI
service. They're built for exhaustive specification and model checking
of a system description, not for being called synchronously inside a
request path to gate a live action.

## Consequences

Positive:
- Verification logic and Python application code live in the same
  process and language; no IPC boundary between the interceptor and the
  solver.
- Z3's `unsat_core` and `model()` give counterexample extraction for
  free, which the dashboard and eval harness both depend on.
- MIT license, no paid tier, matches the zero-cost constraint in
  MASTER.md section 6.

Negative / accepted costs:
- Z3 encoding correctness is entirely on us — no policy-DSL layer catches
  a malformed constraint before it reaches the solver.
- Bounded model checking is sound only to horizon `k`; a violation
  reachable beyond `k` steps is not caught. Stated explicitly in
  `docs/CONTEXT.md`, not hidden.

## Revisit when

- A property needs unbounded (not bounded-horizon) proof, which Z3's BMC
  approach cannot give without a separate inductive-invariant argument, or
- verification latency at the target horizon exceeds what the interceptor
  can afford in the request path (see Phase 1 test `test_solver_terminates`,
  k=8 under 2 seconds).
