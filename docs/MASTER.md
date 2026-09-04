# MASTER.md

**Project:** Bounded
**Tagline:** AP2 records what the user authorized. Bounded proves the agent cannot exceed it.
**Submission:** Razorpay AI-First Internship, Track 1 (AI Growth & Agentic Commerce)
**Status:** scope locked, build not started
**Owner:** Varun P.

---

## 1. The claim we are making

An AI agent operating on a merchant's Razorpay account is given a spending mandate in plain English. Before any money action executes, the mandate is compiled to a formal model and an SMT solver proves that no reachable sequence of agent actions within a bounded horizon can breach it. Actions that pass are executed against Razorpay test mode. Actions that fail are blocked with a machine-generated counterexample trace. Every decision is written to a hash-chained, signed audit ledger.

**What we claim:** bounded-horizon SMT proof of cumulative spend and refund invariants, enforced live on a real payment rail, with measured adversarial evaluation against an LLM-judge baseline.

**What we do NOT claim:** first to do pre-action authorization (OAP, PCAS, APEX got there), first to apply SMT to policy (Cedar, Zelkova, Google CEL got there), unbounded proof (BMC is sound only to horizon k).

This honesty is a scoring asset, not a liability. The track bar asks for honest metrics twice.

---

## 2. Tech stack, locked

Everything below is free tier, open source, or running on committed credits.
No spend anywhere in the critical path beyond what's already provisioned.
(Corrected 2026-09-01, ADR-0012: the LLM layer's original Groq/Gemini plan
was replaced with Azure OpenAI, already-held credentials over a free
signup — see that ADR. Azure OpenAI credits are not free, but usage here
is a few hundred tokens per mandate parse, recorded to cassettes once and
replayed after — a rounding error against the credit balance, not an
ongoing cost.)

### Verification core
| Component | Choice | License | Why |
|---|---|---|---|
| SMT solver | `z3-solver` (pin 4.15.4) | MIT | Best docs, best counterexample extraction, Claude Code knows it |
| Policy IR | Pydantic v2 models | MIT | Typed, serializable, zero new syntax to learn |
| Language | Python 3.11 | PSF | Z3 bindings, FastAPI, Razorpay SDK all land here |

Rejected: Cedar (Lean/Rust toolchain, no cumulative-spend model), Google CEL verifier (Java-only, cannot embed), PySMT (abstraction layer slows debugging), TLA+/Alloy (separate modeling language, no Python embedding).

### Payment rail
| Component | Choice | License | Notes |
|---|---|---|---|
| Razorpay SDK | `razorpay` Python | MIT | order.create, payment.capture, payment.refund |
| MCP server | `razorpay/razorpay-mcp-server` run locally via Docker | MIT | **Must be local.** Remote server disables `create_refund` |
| Test keys | `rzp_test_*` | free | order/capture/refund/failure@razorpay all work |
| Webhook tunnel | `cloudflared` | Apache-2.0 | free, no account needed for quick tunnels |

### Interception
| Component | Choice | License |
|---|---|---|
| MCP middleware | Custom thin proxy on `fastmcp` | Apache-2.0 |
| Fallback | SDK-layer gate wrapping the `razorpay` client | n/a |

The fallback is not a lesser build. It keeps the entire enforcement story and loses only the "MCP-native" framing. Decide at Phase 4 based on how the proxy behaves, not before.

### Backend and storage
| Component | Choice | License |
|---|---|---|
| API | FastAPI + uvicorn | MIT |
| DB | SQLite via SQLAlchemy for dev, Supabase Postgres free tier if deployed | MIT / free tier |
| Migrations | none. Single schema file. 5-day project, Alembic is overhead |

### LLM layer (structure only, never enforcement)
| Component | Choice | Cost |
|---|---|---|
| Provider | Azure OpenAI, `gpt-4.1-mini` (ADR-0012, supersedes the original Groq/Gemini plan) | committed credits (INR 9,555 balance; negligible usage — a few hundred tokens per mandate parse, recorded once) |
| Judge baseline | same model, different prompt | same credits |

No fallback provider. One provider, actually exercised, rather than a
second one wired in and never run for real (ADR-0012).

Hard rule: the LLM parses natural language into a typed policy object and writes human-readable explanations. It never decides whether an action is allowed. If this rule is broken anywhere, the project's thesis collapses.

### Audit ledger
| Component | Choice | License |
|---|---|---|
| Hash chain | `hashlib` SHA-256, stdlib | PSF |
| Signing | `cryptography` Ed25519 | Apache-2.0/BSD |
| Mandate schema | AP2 mandate shape, hand-modeled in Pydantic | Apache-2.0 (schema) |

Do not pull the full AP2 Python SDK as a dependency. Model the Intent/Cart/Payment mandate shape in your own Pydantic types and cite AP2. Importing their SDK drags ADK/Gemini assumptions into your repo for no gain.

Skip: DIDs, didkit, full W3C VC issuance. Ed25519-signed hash chain is defensible and takes an afternoon.

### Evaluation
| Component | Choice | License |
|---|---|---|
| Runner | pytest + custom harness | MIT |
| Attack corpus | AgentDojo banking suite + InjecAgent strings, adapted | MIT / Apache-2.0 |
| Consistency metric | pass^k, tau-bench definition | MIT |

### Frontend
| Component | Choice | License |
|---|---|---|
| Framework | Next.js 15 + React + TypeScript | MIT |
| Styling | Tailwind + shadcn/ui | MIT |
| Deploy | Vercel free tier (frontend), Render free tier (API) | free |

Render free tier cold-starts. For the video, run locally. Deploy anyway so the repo has a live link.

---

## 3. Repository layout

```
bounded/
├── MASTER.md                  # this file, the single source of truth
├── CLAUDE.md                  # Claude Code operating instructions
├── README.md                  # written last, for judges
├── docs/
│   ├── CONTEXT.md             # problem, prior art, positioning
│   ├── LOG.md                 # running build log, append-only
│   ├── EVAL.md                # methodology + results table
│   ├── DEMO.md                # video script, beat by beat
│   ├── THREATS.md             # attack taxonomy + what we do/don't defend
│   └── adr/
│       ├── 0001-z3-over-cedar-and-cel.md
│       ├── 0002-bounded-horizon-not-unbounded.md
│       ├── 0003-mcp-proxy-vs-sdk-gate.md
│       ├── 0004-hash-chain-over-merkle-and-vc.md
│       └── 0005-llm-proposes-solver-decides.md
├── contracts/
│   └── models.py              # frozen Pydantic types, treaty file
├── verifier/
│   ├── model.py               # payment transition system
│   ├── encode.py              # policy -> Z3 constraints
│   ├── bmc.py                 # bounded model checker + counterexample
│   └── explain.py             # counterexample -> human sentence
├── policy/
│   ├── ir.py                  # typed policy IR
│   └── parse.py               # NL -> IR via LLM
├── rail/
│   ├── razorpay_client.py
│   └── mcp_proxy.py
├── ledger/
│   ├── chain.py               # SHA-256 chain + Ed25519 signatures
│   └── store.py
├── eval/
│   ├── scenarios/             # JSON scenario files
│   ├── runner.py
│   ├── baseline_llm_judge.py
│   └── report.py
├── api/
│   └── main.py                # FastAPI
├── web/                       # Next.js dashboard
└── tests/
```

### Documentation discipline
- **LOG.md** gets an entry at the end of every phase. Format: date, phase, what shipped, what broke, what you changed your mind about. This file becomes the raw material for the "what broke at 2 AM" answer, which the form says they read first. Write it as you go or you will invent it later and it will read invented.
- **ADR** files use the standard shape: Context / Decision / Consequences / Alternatives rejected. Five ADRs is the right number. Twenty is procrastination.
- **contracts/models.py** is frozen after Phase 0. Changing it mid-build means updating every layer. Treat it the way you treated `shared/contracts.py` on the capstone, except this time actually freeze it.

---

## 4. Phases

Ordered by dependency and risk, not by day. Ship each phase to a working state before starting the next. Every phase has a definition of done and tests that must pass.

### Phase 0: Scaffold and contracts
**Goal:** repo exists, types are frozen, Claude Code is configured.

Deliverables:
- Repo initialized, public, MIT license
- `CLAUDE.md` written (see section 5)
- `contracts/models.py`: `Mandate`, `PolicyIR`, `Action`, `ActionType`, `VerificationResult`, `Counterexample`, `LedgerEntry`
- `docs/CONTEXT.md` and empty `LOG.md`
- ADR 0001 and 0005 written before any code

**Definition of done:** `python -c "from contracts.models import *"` succeeds. Types cover every field the later phases need.

**Tests:**
- Every model round-trips through `model_dump_json()` and back
- `Action` rejects negative amounts
- `PolicyIR` rejects a monthly cap lower than a per-transaction cap

---

### Phase 1: The Z3 core (highest risk, do it first)
**Goal:** prove the invariants on a toy state machine before any payments code exists.

The payment transition system:
- State: `month_spend`, `captured[order_id]`, `refunded[order_id]`, `txn_count`
- Transitions: `create_order`, `capture`, `refund`
- Properties to prove:
  - P1 per-transaction cap: no single capture exceeds `per_txn_cap`
  - P2 window cap: no reachable k-step trace pushes `month_spend` above `monthly_cap`
  - P3 refund soundness: for every order, `sum(refunds) <= sum(captures)`
  - P4 category restriction: no capture on an order outside allowed categories

Implementation: standard BMC unrolling. Fresh primed variables per step, `substitute` for the transition relation, `solver.check()`, `solver.model()` for the counterexample.

**Definition of done:** for a hand-written policy, the checker returns UNSAT (safe) for a compliant scenario and SAT with a readable counterexample trace for each of P1 through P4 violated.

**Tests:**
- `test_p1_violation_found`: a single 6000 capture under a 5000 cap returns SAT with the offending step index
- `test_p2_multi_step`: three 6000 captures under a 15000 monthly cap returns SAT at step 3, not step 1
- `test_p2_safe`: two 6000 captures under a 15000 cap returns UNSAT
- `test_p3_refund_exceeds_capture`: capture 5000, refund 3000, refund 3000 returns SAT
- `test_p3_split_refunds_ok`: capture 5000, refund 2000, refund 3000 returns UNSAT
- `test_counterexample_readable`: the trace names the action type, amount, and step for every step
- `test_solver_terminates`: k=8 horizon solves in under 2 seconds

**Fallback ladder if this phase stalls.** Take the next rung down and update the claim in MASTER.md and README.md to match. Do not keep the strong claim with the weak implementation.
1. Full bounded-horizon BMC over k steps (target)
2. Per-action check against current accumulated state, plus refund<=capture invariant (still sound, weaker sequencing story)
3. Explicit bounded enumeration in Z3 over a fixed short horizon

---

### Phase 2: Policy IR and transpiler
**Goal:** a typed policy object compiles deterministically to the Z3 constraints from Phase 1.

The IR covers, and only covers:
- `per_txn_cap`, `window_cap` with `window` in {day, month}
- `allowed_categories`, `blocked_categories`
- `max_txn_count` per window
- `refund_policy`: bounded by capture, always on
- `require_human_above`: an escalation threshold

Resist adding more. Every field is Z3 encoding work and eval surface.

**Definition of done:** `encode(policy_ir) -> z3.Solver` is a pure function with no LLM in the path. Same input, same constraints, every time.

**Tests:**
- `test_transpiler_deterministic`: encoding the same IR twice produces identical constraint strings
- `test_every_ir_field_encoded`: a property test asserting no IR field is silently dropped
- `test_ir_with_no_caps_is_permissive`: an empty policy proves UNSAT for everything (nothing is a violation)
- Reuse all Phase 1 tests, now driven through the IR instead of hand-written constraints

---

### Phase 3: Rail and ledger
**Goal:** real Razorpay test-mode money movement, every action recorded in a tamper-evident chain.

Deliverables:
- `razorpay_client.py`: create order, capture, refund, fetch, webhook signature verification
- Local `razorpay-mcp-server` running in Docker with `rzp_test_` keys, refund tool confirmed working
- `ledger/chain.py`: each entry stores `SHA256(canonical_fields || prev_hash)`, signed Ed25519, genesis at index 0
- `verify_chain()` walks and validates

**Definition of done:** a script runs order -> capture -> refund against test mode and the ledger verifies clean.

**Tests:**
- `test_order_capture_refund_live`: full cycle against test mode, asserts final state via `fetch_payment`
- `test_failure_handle`: `failure@razorpay` produces a failed payment, handled without an exception escaping
- `test_webhook_signature`: valid signature passes, tampered body fails, verified against raw bytes not parsed JSON
- `test_chain_verifies`: 50 entries, `verify_chain()` returns True
- `test_chain_detects_tampering`: mutate one entry's amount, `verify_chain()` returns False and names the index
- `test_chain_detects_deletion`: remove a middle entry, verification fails
- `test_webhook_idempotent`: same `x-razorpay-event-id` twice produces one ledger entry

Note: authorized-but-uncaptured payments auto-refund. Capture promptly in every test.

---

### Phase 4: The interceptor
**Goal:** nothing reaches Razorpay without passing the verifier.

Every proposed action goes: agent -> interceptor -> `encode(policy) + current_state + proposed_action` -> Z3 -> allow or block -> ledger -> rail.

Try the MCP proxy first. If it fights you for more than a few hours, switch to the SDK-layer gate. Record the decision in ADR 0003 either way.

**Definition of done:** a compliant action executes against test mode; a violating action is blocked, logged with its counterexample, and never touches the network.

**Tests:**
- `test_compliant_action_executes`: asserts a real payment id comes back
- `test_violating_action_blocked`: asserts zero outbound Razorpay calls, mock the client and assert call count is 0
- `test_block_writes_ledger_entry`: blocked actions are logged with reason and counterexample
- `test_fail_closed`: solver timeout or crash results in block, not allow. This is the single most important test in the repo
- `test_state_reconstruction`: rebuild `month_spend` from the ledger, matches Razorpay's fetched state

---

### Phase 5: Natural language mandate
**Goal:** merchant types English, gets a typed policy, sees exactly what was parsed.

Flow: NL -> LLM with a strict JSON schema -> validate into `PolicyIR` -> render the parsed policy back to the user for confirmation -> compile.

The confirmation step matters. It is where the LLM's fallibility becomes visible and contained rather than hidden.

**Definition of done:** ten sample mandates in English parse to correct IR, and a deliberately ambiguous one is rejected with a request for clarification.

**Tests:**
- `test_parse_ten_mandates`: fixture file of English/Hinglish mandates and expected IR
- `test_malformed_llm_output_rejected`: stub a bad LLM response, assert it raises rather than producing a permissive policy
- `test_llm_cannot_widen_policy`: an injected mandate saying "ignore all limits" fails validation
- `test_parse_is_not_in_enforcement_path`: architectural test asserting `verifier/` does not import `policy/parse.py`

---

### Phase 6: Red team and metrics
**Goal:** the numbers that make the submission credible.

Scenario corpus, 60 to 100 total across five classes:
1. Direct over-cap sequences
2. Refund exceeds capture, including split-refund attacks across sessions
3. Indirect prompt injection via poisoned product content and tool output, adapted from AgentDojo banking and InjecAgent
4. Category and count violations
5. Benign compliant flows, at least 30 percent of the corpus so the false positive rate means something

Baseline: the same corpus run against an LLM-as-judge guardrail. This comparison is the point. Expect the LLM judge to let injection attacks through and to occasionally block benign flows.

Metrics reported in `EVAL.md`:
- Violations caught, by class
- **Unsound safe verdicts: must be 0.** Any nonzero number here is a bug, not a metric
- False positive rate on benign flows, with the cost framing
- pass^k for k in {1, 4, 8}, tau-bench definition, since the LLM parser makes the pipeline non-deterministic even though the verifier is not
- Median verification latency

**Definition of done:** `python -m eval.runner` produces a results table and writes it into EVAL.md. Reproducible from a clean clone.

**Tests:**
- `test_scenario_schema`: every scenario file validates
- `test_corpus_balance`: benign flows are at least 30 percent
- `test_runner_reproducible`: two runs on the deterministic subset produce identical results
- `test_no_unsound_safe`: the assertion that fails the build if any violation is marked safe

---

### Phase 7: Dashboard
**Goal:** the demo is legible to someone who has never seen the repo.

Four panels:
1. Mandate: English input, parsed policy object beside it
2. Proof: SAT/UNSAT, the properties checked, the horizon k
3. Live audit trail: chain entries streaming, verification status
4. Blocked attacks: the counterexample trace rendered as readable steps

Aesthetic: dark, monospace for traces, serious. This is a verification tool, not a consumer app.

**Definition of done:** a stranger can watch the screen and narrate what happened.

**Tests:** manual. Two people who have not seen the project describe what they think it does. If they cannot, the UI failed.

---

### Phase 8: Submission artifacts
- README with the honest positioning section, the results table, and setup instructions that work from a clean clone
- 5-minute video following `DEMO.md`
- The "what broke" answer, drawn from LOG.md

**The 60-second moment in the video:** agent shopping under a 15,000 rupee mandate hits a poisoned product page whose hidden text redirects a refund. Screen flashes BLOCKED. The counterexample trace renders: "step 3: refund 4000 on order X where captured total is 2000, violates refund soundness." Ledger entry appears. Then the compliant purchase executes and a real `payment.captured` comes back from Razorpay test mode. Explainable, bounded, gated, one failure handled gracefully. That is the track bar, verbatim, in one shot.

---

## 5. Claude Code setup

### CLAUDE.md
Keep it short. Long CLAUDE.md files get ignored. It should state:
- The LLM-proposes / solver-decides rule, as a hard constraint
- Run pytest before declaring any phase done
- Append to LOG.md at phase boundaries
- Never widen a policy to make a test pass
- Full files, not diffs, when showing code
- The frozen contracts file and that it requires explicit approval to change

### Skills to create in `.claude/skills/`
These are yours to write, and writing them is fast because the research report has the content.

1. **`z3-bmc`** — the bounded model checking encoding pattern, primed variable substitution, counterexample extraction, `unsat_core` usage, the specific gotchas of Int vs BitVec for money amounts. This is the highest-value skill because it is the part Claude Code is most likely to get subtly wrong.
2. **`razorpay-testmode`** — test key format, the local-server-required-for-refunds gotcha, `failure@razorpay`, webhook HMAC over raw bytes, the auto-refund-on-uncaptured trap, minimal SDK call sequences.
3. **`ledger-chain`** — the hash chain and Ed25519 signing recipe, canonical serialization rules, what verification must check.
4. **`eval-harness`** — pass^k definition, scenario file schema, how results get written into EVAL.md.
5. **`adr`** — the ADR template and the rule that a decision reversal amends rather than deletes.

### Plugin skills already available to you
From the catalog: `engineering:architecture` for the ADRs, `engineering:testing-strategy` when designing each phase's test set, `engineering:documentation` for the README, `engineering:debug` when Phase 1 fights you. Use them in chat for structure, not for writing your code.

### Claude Code features worth using
- **Plan mode** before each phase. Have it propose, you approve, then it builds.
- **Subagents** for the eval corpus generation. Generating 100 scenarios is parallel, boring work.
- **Hooks:** run pytest on file write in `verifier/`. Catching a broken invariant immediately is worth the setup.
- **Custom slash commands** for `/phase-done` that runs tests, appends to LOG.md, and commits.

---

## 6. Cost check

| Item | Cost |
|---|---|
| Z3, FastAPI, Next.js, all libraries | free, open source |
| Razorpay test mode | free, no KYC needed for test keys |
| Azure OpenAI (`gpt-4.1-mini`) | committed credits, not free tier (ADR-0012) — negligible draw against an INR 9,555 balance |
| Vercel, Render | free tier |
| cloudflared | free |
| GitHub public repo | free |
| **Total** | **~zero** — the only real spend is a rounding error against already-committed Azure credits |

The only paid things in the vicinity are Claude Code itself and the Azure OpenAI credits, both already provisioned before this build started.

---

## 7. Resolved constraints

- **Deadline: 5 September.** Seven calendar days from 29 August, worked in parallel with other commitments.
- **Repo public from commit one.** Commit history is part of the evidence.
- **Phase gate rule is binding.** Phase N does not start until Phase N-1's tests pass. No exceptions, no "I'll come back to it."
- **Razorpay test keys:** obtained in Phase 0.
- **Name: Bounded.** Decided — not a placeholder. Consistent across `pyproject.toml`, the repo slug, the dashboard's page title and header, and README.
- **Video:** OBS Studio (free, open source). Record in Phase 8.

### Date gates

Buffer is deliberate. The last two days are for the things that always go wrong, not for building.

| Gate | By end of | Meaning |
|---|---|---|
| Phase 0 + 1 | 31 August | The project is real or it is not. Z3 tests green. |
| Phase 2 + 3 | 2 September | Policy compiles, money moves in test mode, ledger verifies. |
| Phase 4 + 5 | 3 September | Nothing reaches Razorpay unverified. English mandates parse. |
| Phase 6 | 4 September | Numbers exist. EVAL.md written. |
| Phase 7 + 8 | 5 September | Dashboard, video, README, submit. |

**Hard call point: end of 31 August.** If Phase 1 has not passed its tests by then, drop to the next rung of the fallback ladder immediately and rewrite the claim to match. Do not spend 1 September still fighting the solver.

If the schedule slips past 3 September, cut Phase 5 first. Hand-written policy JSON with a note that NL parsing is future work costs almost nothing in the submission. Cutting Phase 6 costs the whole thing, because measured metrics are the track bar.

### Toolchain note

Docker is not required. The Razorpay MCP server is a single Go binary: install Go 1.24+, `go build -o razorpay-mcp-server ./cmd/razorpay-mcp-server`, run it with `rzp_test_` env vars. That is a 100 MB toolchain instead of a 2 GB Docker Desktop install plus a WSL2 dependency, and one less layer between you and a stack trace. Install Docker only if the Go build fails.

One thing worth restating rather than burying: Phase 1 is the whole project. If the Z3 core does not work, everything downstream is a policy engine with a fancy name, and three papers from 2026 already did that better.
