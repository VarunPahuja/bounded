# LOG

Append-only. One entry per phase: date, what shipped, what broke, what changed my mind.

## 2026-08-30 — Phase 0: Scaffold and contracts

**Shipped:** repo public on GitHub (`VarunPahuja/bounded-`), MIT license, `CLAUDE.md`
and `docs/MASTER.md` in place, `contracts/models.py` frozen with all required
types (`Mandate`, `PolicyIR`, `Action`, `ActionType`, `VerificationResult`,
`Counterexample`, `LedgerEntry`, plus `CounterexampleStep` and the supporting
enums). `docs/CONTEXT.md` written. ADR-0001 (Z3 over Cedar/CEL) and ADR-0005
(LLM proposes, solver decides) written and accepted. All 14 Phase 0 tests
green: round-trip through `model_dump_json()`, `Action` rejects
non-positive amounts, `PolicyIR` rejects a monthly cap below the per-txn cap.

**Broke:** nothing — Phase 0 is scaffolding and types, low-risk by design.
The gap wasn't a bug, it was sequencing: the models and tests landed before
the ADRs and LOG.md did, which inverts MASTER.md's own instruction to write
ADR-0001 and 0005 *before* any code. Caught on a manual phase check rather
than a hook, since nothing currently enforces "ADR exists" before "test
passes."

**Changed my mind:** nothing on scope or design. Confirmed the ADR-writing
step needs to happen at the start of a phase checklist, not the end, given
it slipped once already.

