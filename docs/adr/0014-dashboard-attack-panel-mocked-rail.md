# ADR-0014: the Attacks panel's rail call is mocked, same disclosed methodology as EVAL.md

- Status: Accepted
- Date: 2026-09-03
- Deciders: Varun P.
- Supersedes: -
- Superseded by: -

## Context

The dashboard's Attacks surface (`docs/PHASE7-PLAN.md`) has to run a
poisoned scenario through the real pipeline and show the block: real
mandate/policy, real Z3 verdict via `verify_action`, real hash-chained
ledger write. `docs/DEMO.md`'s 2:40-4:05 beat additionally shows a
compliant leg on the same agent surface returning a genuine Razorpay
payment id.

Two ways to build the panel's rail call:

1. Mock it, reusing the exact methodology `eval/runner.py` already uses
   and `docs/EVAL.md` already discloses: everything upstream of the
   network call is real, the Razorpay call itself is a synthetic success.
2. Wire a real seeded Razorpay test-mode order into the dashboard so the
   panel's compliant leg shows an actual payment id live.

This needed a decision before building, not an assumption, because it
changes what the panel is honestly allowed to claim is "real" on screen —
exactly the kind of thing the task brief's honesty rules single out.

## Decision

Mock the rail call. `/api/attack/run` calls the real `propose_action`
against a real reconstructed ledger state and a real Z3 verdict; the
Razorpay network call inside it is replaced with a synthetic success, the
same substitution `eval/runner.py` makes and `docs/EVAL.md`'s
"Methodology: what's real, what's mocked" section already discloses in
the exact same words this ADR would otherwise repeat.

Presented as an explicit choice to the project owner (not decided
unilaterally) given the timeline: two days remain before the 5 September
deadline, with Phase 8 (video, README, written answer) still ahead.
Confirmed 2026-09-03.

## Alternatives considered

### Wire a real seeded Razorpay order into the dashboard
Rejected for now. Would make the compliant-path beat's payment id genuine
inside this one panel, more faithful to DEMO.md's single-screen framing,
but costs setup time this session doesn't have to spend: a fresh
`scripts/seed.py` order specifically for the dashboard, checked in well
before the "24-48h before recording" window DEMO.md's own checklist
requires, plus a live-Razorpay dependency the dashboard would need
working through every rehearsal. Phase 3 and Phase 4 already proved the
rail live once, without the dashboard's help — that claim doesn't need
re-proving here, matching the reasoning `docs/EVAL.md` itself already
gives for why its own harness mocks the same call.

## Consequences

Positive:
- No new live-Razorpay dependency inside the dashboard's build or
  rehearsal loop.
- The panel's honesty claim is identical to `docs/EVAL.md`'s, already
  written, already reviewed, already disclosed — no new disclosure
  language to get right under time pressure.
- Faster to build: `/api/attack/run` needs no seeded order, no
  `manual_expiry_period` timing, no card-OTP browser step.

Negative / accepted costs:
- DEMO.md's compliant-path beat (a genuine `payment.captured` id on
  screen) is not demonstrated inside the Attacks panel. If the video
  wants that beat, it has to come from somewhere else — a terminal
  run of `scripts/seed.py`'s flow, or a live capture shown separately —
  not from this dashboard screen. This is a real gap against DEMO.md's
  exact staging, accepted deliberately rather than solved by assuming a
  mocked payment id would pass as genuine.
- If time remains after Phase 7's four panels are working, wiring a real
  order in is still open (see "Revisit when").

## Revisit when

- Phase 7's four required panels are built and demoable, and time
  remains before recording. At that point, seeding one real order for
  the dashboard specifically (not reusing a test-suite payment id) and
  wiring the compliant leg to it becomes a scoped, optional upgrade
  rather than a blocking decision.
