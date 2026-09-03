# PHASE7-PLAN.md

**Status: planned, not started.**

Written before any Phase 7 code, per CLAUDE.md's "plan before building" rule
and standing practice on this project of committing the plan as its own
reviewable doc before implementation begins. Nothing in `web/` or `api/`
exists yet beyond `api/__init__.py` (empty).

Baseline confirmed before writing this: `pytest` -> 114 passed, 3 skipped,
0 failed (2026-09-03).

---

## Scope recap (not re-litigated here, just anchored)

Four surfaces — Mandate, Proof, Ledger, Attacks — per the task brief and
`docs/MASTER.md` section 4's Phase 7 entry. Aesthetic per `docs/DESIGN.md`.
Beat mapping per `docs/DEMO.md`. Honesty rules (bound always travels with
verdict, no fabricated numbers, LLM never in the decision path) are
non-negotiable and drive several concrete decisions below, not just a
principle to remember.

`verifier/`, `rail/`, `policy/`, `ledger/`, `contracts/`, `eval/` are not
edited. `api/` is new, thin, and only calls existing pure functions — it
introduces no new decision logic.

---

## API layer (`api/`)

FastAPI app, `api/main.py`. Every endpoint is a direct call to an existing
function; the API's job is serialization and orchestration, nothing else.

| Endpoint | Calls | Notes |
|---|---|---|
| `POST /api/mandate/parse` | `policy.parse.parse_mandate` | `{text}` -> `{status: "ok", policy}` or `{status: "ambiguous"|"error", message}` on `MandateParseError`. Never guesses past what the parser returns. |
| `POST /api/mandate/activate` | `policy.activate.activate_policy` | `{policy}` -> `VerificationResult`, horizon included by construction (the type has no other shape). |
| `POST /api/proof/verify` | `verifier.bmc.verify_guard` | `{policy, guard: "naive"|"sound"}` -> `VerificationResult`. `"naive"` composes `verifier.encode.naive_capture_guard`/`naive_refund_guard` (already exist, used today only to prove they're unsound in tests); `"sound"` uses the same `GUARD` constant `rail.interceptor` hard-codes, imported from there — never a second construction. This is what lets the Proof surface reproduce DEMO.md's 1:00-2:40 beat (naive fails, sound passes, same policy). |
| `GET /api/ledger/entries` | `ledger.store.load_all` | Full entry list from a dashboard-owned SQLite file (see "Demo state" below). |
| `GET /api/ledger/verify` | `ledger.chain.verify_chain` | `{broken_at_index: int \| null}`. |
| `POST /api/ledger/tamper-preview` | `ledger.chain.verify_chain` over an in-memory mutated copy | `{index, field, value}` -> `{broken_at_index}`. Never writes to the real store — `ledger/store.py`'s own triggers reject a real UPDATE, and this endpoint doesn't attempt one; it loads entries, mutates a `model_copy` in Python, and re-verifies the copy. This is the "control that mutates an entry and shows the chain breaking" the task brief calls out, built without touching the append-only guarantee it's demonstrating. |
| `POST /api/attack/run` | `rail.interceptor.propose_action`, seeded from an `eval/scenarios/*.json` file | See open decision below — this is the one endpoint with a real design choice attached to it. |
| `GET /api/eval/summary` | Parses the committed `docs/EVAL.md` | Static parse of the actual file, not a live recomputation and not a hand-typed constant. Only built if the Numbers beat gets a dashboard surface — not one of the four required panels, so lowest priority. |

### Demo state

The dashboard needs its own ledger (SQLite file, e.g. `api/demo_ledger.db`),
separate from any test database, so the Ledger surface has something
real and persistent to show across restarts, and so the Attacks surface
can run scenarios against a known-clean chain. Seeded once via a small
script that appends genesis + a few real `propose_action` calls (using
existing scenario fixtures already in `eval/scenarios/`), not hand-built
`LedgerEntry` JSON.

### Open decision: `/api/attack/run`'s rail call

This is the one place a real judgment call is needed before building.

The Attacks surface needs to run a poisoned scenario (e.g.
`eval/scenarios/inj-001-poisoned-product-page-refund.json`) through the
real pipeline — real parse (if the scenario has mandate text), real Z3
verdict, real ledger write — and show the block. `docs/EVAL.md`'s own
methodology already establishes that mocking only the Razorpay network
call, while keeping the verdict pipeline real, is a legitimate and
already-disclosed way to measure this system: "every decision — allow or
block — is a real verdict from the real enforcement path... the Razorpay
network call itself is replaced with a synthetic success."

Two options:

**(a) Reuse that exact methodology for the dashboard.** `/api/attack/run`
calls the real `propose_action` with a mocked rail call (same pattern
`eval/runner.py` already uses, same disclosure `docs/EVAL.md` already
carries). Fast to build, already-vetted honesty story, and matches what
this task actually needs to prove (a judge reading a trace, per the task
brief's own framing of this screen). The BLOCKED half of DEMO.md's
2:40-3:40 beat is fully real on this option. The compliant-path half
(3:40-4:05, a genuine `payment.captured` from Razorpay) would need to be
demonstrated separately, e.g. live in the terminal or a second seeded
flow, not necessarily inside this same panel.

**(b) Wire a real seeded Razorpay test-mode order into the dashboard**, so
the Attacks surface's compliant path shows an actual payment id returned
live. More faithful to DEMO.md's exact beat inside one screen, but costs
setup time now (a fresh seeded order via `scripts/seed.py`, checked well
before recording per `docs/DEMO.md`'s "24-48h before recording" rule)
and re-introduces live Razorpay dependency into the dashboard's uptime
during rehearsal.

Recommendation: **(a)** now, given the two-day runway and that Phase 3/4
already proved the rail live once without the dashboard's help. Revisit
(b) only if Phase 7 finishes with time to spare before recording. This is
flagged as an open decision rather than assumed because it changes what
"real" means on that specific screen, which the honesty rules make load-
bearing.

---

## Frontend (`web/`)

Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui — locked stack,
nothing added.

```
web/
  app/
    layout.tsx              # ambient SAFE/VIOLATION background, keyboard listener
    page.tsx                 # single-page spatial layout, four regions
  components/
    surfaces/
      MandateSurface.tsx
      ProofSurface.tsx
      LedgerSurface.tsx
      AttacksSurface.tsx
    trace/
      CounterexampleTrace.tsx   # monospace, max-contrast, both states, non-negotiable per DESIGN.md
    chain/
      LedgerEntryRow.tsx
      ChainStatusBadge.tsx
      TamperControl.tsx
    proof/
      VerdictBadge.tsx           # props: {verdict, horizon} -- no verdict-only variant exists in the type
      PropertiesList.tsx          # renders qualified entries (e.g. P2[window=month,...]) verbatim
    ambient/
      ProofStateBackground.tsx   # drift (SAFE) vs rigid grid (VIOLATION)
  lib/
    api.ts                 # typed fetch wrappers, hand-mirrored to contracts/models.py shapes
    keybindings.ts
  styles/
    tokens.css              # SAFE / VIOLATION palettes as CSS custom properties
```

Proposed keyboard shortcuts: `1` Mandate, `2` Proof, `3` Ledger, `4`
Attacks — matches build order, easy to narrate ("hitting 4 for the
attack view") on camera. Open to changing if you'd rather mnemonic
letters (`m`/`p`/`l`/`a`).

## Honesty rules as concrete constraints, not just principle

- `VerdictBadge`'s TypeScript props type has no verdict-only variant —
  `horizon` is required wherever `verdict` appears, so a screen that
  drops the bound fails to compile, not just fails review.
- No component holds a literal number. Every figure comes from an API
  call backed by a real function call or a parse of `docs/EVAL.md`.
- `parse_mandate` (the only LLM call in this repo) is only ever invoked
  from `/api/mandate/parse`, server-side. No client code holds an API
  key or calls a model directly.

## Build order (unchanged from the task brief, restated for the commit record)

1. Attacks surface + `/api/attack/run` + `CounterexampleTrace`.
2. Proof surface + `/api/proof/verify` + `/api/mandate/activate`.
3. Ledger surface + `/api/ledger/*` incl. tamper-preview.
4. Mandate surface + `/api/mandate/parse`.
5. Spatial nav, ambient background, drift/rupture transition, keyboard
   shortcuts, palette tuning.

Each step should be independently demoable before the next starts.

## Testing

Manual per MASTER.md's own Phase 7 definition — no automated UI suite is
in scope. `pytest` re-run before and after any `api/` work to confirm the
114/3 baseline holds; `api/` imports enforcement modules but adds no new
ones, so a passing baseline plus a diff scoped to `api/`/`web/` is the
check.

## ADRs anticipated

One ADR once the `/api/attack/run` rail-mocking decision above is
confirmed — it's a real design decision (what the dashboard is honestly
allowed to claim is "real" on screen), not incidental UI code.

## LOG.md

Entry written at the close of Phase 7, not before, and not backfilled
into a later phase's entry.
