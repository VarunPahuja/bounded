# DESIGN.md

**Superseded 2026-09-04 by [ADR-0015](adr/0015-neobrutalist-ui-supersedes-ethereal.md).**
The ethereal direction below was built for Phase 7 and shipped through
Phase 7b, but pale low-contrast colour and opacity-based hierarchy do not
survive a 1280x720 recording under video compression — the medium this
interface is actually judged through. UI 2.0 replaces it with a
neobrutalist direction (hard borders, flat saturated colour, no opacity
hierarchy). This file is left as-is, not rewritten, per this project's
standing rule that decisions are amended, never erased — the reasoning
below explains why ethereal seemed right at the time, and ADR-0015
explains why it no longer is.

---

Direction for Phase 7 (dashboard) only. Nothing here is built. Phase 2
(Policy IR and transpiler) is next per the phase gate in MASTER.md —
this file exists so the direction isn't reconstructed from memory five
phases from now.

## Thesis

The aesthetic performs the argument; it does not decorate it. Softness
is the proven state. The break is the finding. A judge should be able
to tell, from across the room, whether the system currently believes
itself safe — before reading a single word.

## Two states, one surface

The whole dashboard is conditioned on current verification state. There
is no neutral/default look — it is always visibly SAFE or visibly
VIOLATION.

### SAFE — weightless

What "nothing can go wrong here" should feel like.

- Palette: pale lilac and dusty rose on cold white.
- Soft gradients, serif headings, generous negative space.
- Faint, feathered shadows — nothing with a hard edge.
- Elements drift slightly (subtle, continuous, not attention-seeking).

### VIOLATION — rupture

The calm breaks. Not an alarm — a discontinuity.

- The drift stops. The layout snaps to a rigid grid. The mist recedes.
- **Accent colour: cold, not red.** Proposing a glacial cyan
  (`#5FE3E0`–ish range, exact value to be tuned against the dark field
  in Phase 7) rather than anything in the red/orange family. Red reads
  as panic/urgency, which fights the framing — this is a break in
  composure, not an emergency siren. Cold reads as "the temperature
  dropped," which is the actual sensation a proof failing should give.

### Non-negotiable, applies in both states

Counterexample traces are **always** maximum-contrast monospace on a
dark field, regardless of the ambient SAFE/VIOLATION mood. This is the
exact content a judge needs to read correctly, under time pressure,
possibly from a recorded video at reduced quality. Ethereal treatment
(soft contrast, drift, gradient) never touches the trace itself, even
when the trace is rendered inside an otherwise-SAFE surface (e.g. a
past violation shown in the ledger while current state is SAFE).

## Navigation: four surfaces, not a nav bar

- **Mandate** · **Proof** · **Ledger** · **Attacks** — the same four
  panels from MASTER.md section 7, renamed to match Phase 7's language.
- Rendered as regions in a drifting, spatial layout, not tabs or a top
  nav bar.
- The current proof state (SAFE/VIOLATION) is ambient in the background
  at all times, regardless of which surface is focused — a viewer
  glancing at any panel always knows the current verdict.
- **Hard requirement: keyboard shortcuts jump directly to any surface.**
  No scroll-hunting for a panel during a live recording. Exact bindings
  are a Phase 7 decision, not fixed here, but the requirement itself is
  locked: four surfaces, four direct-jump keys, no exceptions.

## Stack

Per MASTER.md section 2: Next.js 15 + React + TypeScript, Tailwind +
shadcn/ui. No animation library beyond CSS and, if the drift/rupture
transition needs it, Framer Motion. Nothing else.

## Checklist for Phase 7 (grade the build against this, don't reinvent it)

- [ ] SAFE and VIOLATION are visually distinct enough to read at a glance
- [ ] Violation accent colour is cold, not red
- [ ] Counterexample trace is monospace + maximum contrast in both states
- [ ] All four surfaces reachable by direct keyboard shortcut
- [ ] Current proof state visible regardless of which surface has focus
- [ ] A stranger who has not seen the project can watch and narrate what
      happened (MASTER.md's actual Phase 7 definition of done)
