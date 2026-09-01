# ADR-0003: SDK-layer gate, not an MCP proxy

- Status: Accepted
- Date: 2026-08-31
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

MASTER.md section 2 left this open deliberately: try the MCP proxy first,
fall back to an SDK-layer gate if it fights for more than a few hours,
decide for real at Phase 4. Both were live options because Phase 3 hadn't
yet settled where the actual chokepoint is.

Phase 3 settled it. `rail/razorpay_client.py` is already the sole place
every money-moving Razorpay call in this codebase goes through —
`attempt_capture`, `refund`, `fetch_payment`. `scripts/seed.py` uses
`create_order` from the same module, but order creation was moved outside
the agent's action space entirely (2026-08-31 LOG entry): a human seeds
authorized-but-uncaptured orders once, offscreen, ahead of time. The
agent's real action space — the two calls with money consequences — is
capture and refund, both already funneled through one Python module with
no ledger import and no policy import, exactly the shape a gate wraps
cleanly.

An MCP proxy would sit in front of `razorpay/razorpay-mcp-server`
(MASTER.md section 2, run locally so `create_refund` stays enabled) and
intercept JSON-RPC tool calls between an MCP client and that server. That
buys "MCP-native" framing, but this phase has no MCP client in the loop to
intercept: Phase 4's own scope boundary is explicit — no LLM, no natural
language, no agent loop. Policies are constructed as `PolicyIR` directly,
and the tests that define this phase (`test_compliant_action_executes`,
`test_violating_action_blocked`, etc.) call a Python function with a
proposed `Action`, not a tool-call JSON-RPC frame. Building the proxy now
means standing up a protocol-translation layer to gate calls nothing in
this repo currently makes that way, before the client that would make them
exists (Phase 5+).

## Decision

Enforce at the SDK layer. `rail/interceptor.py` becomes the only module
permitted to import `attempt_capture` and `refund` from
`rail/razorpay_client.py`. Every proposed action goes through
`interceptor.propose_action()`: reconstruct current state from the ledger,
verify against the compiled policy, write the ALLOW/BLOCK ledger entry,
call the rail only on ALLOW. `razorpay_client.py` itself is untouched —
it stays the boring, already-tested Phase 3 wrapper; the gate wraps it
rather than replacing it.

If Phase 5 later gives the agent an MCP-facing tool surface, that surface
is defined as *exactly one tool*: `propose_action`. The agent is never
handed `attempt_capture`/`refund` as callable tools, MCP-native or
otherwise — so there is nothing for a proxy to selectively block that the
gate doesn't already block at the one point money can move. A proxy at
that stage would duplicate the gate's decision, not add one.

## Alternatives considered

### MCP proxy in front of razorpay-mcp-server
Rejected for this phase: no MCP client exists yet to proxy, so the work
would be enforcing a call shape nothing in the repo produces. It also adds
a real dependency this project doesn't currently carry into its critical
path — a running local MCP server process, plus `fastmcp`
(`pyproject.toml` already lists `fastmcp==3.4.7` under `rail`, but nothing
imports it) — for a framing benefit ("MCP-native") the track bar doesn't
score and MASTER.md itself calls not a lesser build to skip.

### Both, to keep every option demoable
Rejected: MASTER.md is explicit — decide, do not build both. Two
enforcement paths for the same money calls is two places the guarantee
can drift apart, which is a worse story than one path honestly described,
not a better one.

## Consequences

Positive:
- The gate is a plain Python function boundary: testable synchronously,
  no server process, no protocol layer, in a five-day build.
- It is honest about scope — Phase 4 has no agent yet, so nothing is lost
  by not proxying calls that don't exist. The MCP-native framing is
  deferred to exactly the phase (5+) that would make it real, not faked
  now.
- The rail's existing Phase 3 tests (`tests/rail/test_razorpay_client_live.py`)
  keep working unmodified — they test the rail in isolation, on purpose
  (CLAUDE.md: never mock the call that's supposed to prove the rail
  works), and stay outside the gate's jurisdiction as a named exception.

Negative / accepted costs:
- "Unreachable except through the interceptor" is enforced by a static,
  CI-run test (`test_no_direct_rail_access`, AST-scanning the repo for any
  import of `attempt_capture`/`refund` from `rail.razorpay_client` outside
  the allowed callers) — not a language-level or process-level sandbox.
  Python has no true module privacy; a determined edit can still add a
  second import site, and the guarantee only holds as long as that test
  keeps running in CI. This is the same class of guarantee CLAUDE.md
  already accepts for "`verifier/` must never import `policy/parse.py`" —
  consistent with how this project enforces its other hard architectural
  rules, not a weaker standard invented for this one.
- If Phase 5 does build an MCP-facing tool surface, this ADR's claim that
  a proxy would be redundant only holds if that surface really is
  restricted to `propose_action` alone. That has to be re-checked at the
  time, not assumed from here.

## Revisit when

- Phase 5+ gives the agent a real MCP tool surface and it turns out the
  agent needs more than one Razorpay-shaped tool exposed to it (breaks
  the "nothing for a proxy to block" argument above), or
- the local `razorpay-mcp-server` process becomes part of the demo path
  for a reason unrelated to enforcement (e.g. showing MCP tool discovery
  in the video) — worth a tool-level proxy then, but as a demo surface,
  not as the enforcement mechanism.
