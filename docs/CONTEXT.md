# CONTEXT

## The problem

An AI agent operating on a merchant's Razorpay account is given a spending mandate
in plain English. Before any money action executes, the mandate is compiled to a
formal model and an SMT solver proves that no reachable sequence of agent actions
within a bounded horizon can breach it. Actions that pass are executed against
Razorpay test mode. Actions that fail are blocked with a machine-generated
counterexample trace. Every decision is written to a hash-chained, signed audit
ledger.

The failure mode this targets is not a single bad action. It is a sequence: an
agent that stays under a per-transaction cap on every individual call but drains
a monthly budget over many small ones, or that issues split refunds that in
aggregate exceed what was ever captured. A per-call check catches neither. A
bounded model checker over the transition system does, because it reasons about
reachable states across steps, not about one call in isolation.

## What we claim

Bounded-horizon SMT proof of cumulative spend and refund invariants, enforced
live on a real payment rail, with measured adversarial evaluation against an
LLM-judge baseline.

## What we do NOT claim

- **First to do pre-action authorization.** OAP, PCAS, and APEX got there first.
- **First to apply SMT to policy.** Cedar, Zelkova, and Google CEL got there first.
- **Unbounded proof.** This is bounded model checking. It is sound only to the
  configured horizon `k`. A violation reachable only beyond `k` steps will not be
  caught. This is stated plainly, not buried in a footnote, because the honesty
  is the point: the track bar asks for honest metrics twice, and an inflated
  claim is a worse submission than an accurate, narrower one.

## Prior art

| Project | What it does | Where this project differs |
|---|---|---|
| Google AP2 (Agent Payments Protocol) | Defines the Intent/Cart/Payment mandate shape and records what a user authorized. | AP2 records authorization. It does not prove that a sequence of agent actions cannot exceed it. This project hand-models the AP2 mandate shape in Pydantic and adds the proof step AP2 does not attempt. |
| OAP, PCAS, APEX | Pre-action authorization protocols for agent-initiated payments. | Established the pattern of gating an action before it reaches the rail. This project narrows scope to one rail (Razorpay test mode) and adds a bounded-horizon solver in the gate rather than a rules check. |
| AWS Zelkova, Google CEL, Cedar (AWS) | Apply SMT or a policy DSL to access-control and IAM-style policy evaluation. | Proved SMT-for-policy works for access control. None model a cumulative-spend or refund-soundness invariant across a sequence of payment transitions, which is the specific shape this project targets. Cedar in particular was evaluated and rejected here (see ADR 0001) because it has no cumulative-spend model and requires a Lean/Rust toolchain this project's stack does not carry. |
| LLM-as-judge guardrails | An LLM reviews a proposed action and approves or blocks it in natural language. | This is the baseline this project measures against, not prior art to build on. The core thesis is that an LLM judging compliance is unsound in principle, not just unreliable in practice: it can be prompt-injected, it has no notion of a bounded proof, and it cannot produce a counterexample. See the one rule in `CLAUDE.md`: the LLM proposes structure, the solver decides. |

## Honest positioning, restated

This project is not the first formal-methods-for-agent-payments idea, and it is
not an unbounded guarantee. It is a bounded-horizon proof, live on a real rail,
measured against a baseline that is expected to fail in specific, demonstrable
ways (letting injection attacks through, occasionally blocking benign flows).
The evaluation in Phase 6 exists to make that comparison concrete rather than
asserted.
