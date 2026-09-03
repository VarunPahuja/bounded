# ADR-0015: neobrutalist UI 2.0 supersedes DESIGN.md's ethereal direction

- Status: Accepted
- Date: 2026-09-04
- Deciders: Varun P.
- Supersedes: DESIGN.md's SAFE/VIOLATION ethereal direction (drift, pale
  lilac/rose, opacity-based hierarchy)
- Superseded by: -

## Context

`docs/DESIGN.md` set the aesthetic direction for Phase 7: soft gradients,
pale lilac/rose on cold white, drift, feathered shadows, opacity-based
text hierarchy. Phase 7 and 7b built to that direction faithfully, and it
worked on a desktop monitor in a well-lit room.

It does not survive the medium this interface actually has to be seen
through. Two things converge:

1. **Phase 7b's own screenshot verification already surfaced the
   legibility failure mode this palette produces.** Building the status
   strip and auto-loaded surfaces required raising `opacity-70` text to
   `opacity-85` and above across every surface specifically because low-
   contrast secondary text was judged unlikely to survive video
   compression — a real fix applied under the old palette, not a
   hypothetical concern.
2. **The submission is judged from a recorded video at 1280x720, not a
   live desktop session.** `docs/DEMO.md`'s entire beat sheet assumes a
   viewer reading rendered pixels through video compression, at a
   resolution smaller than most development monitors. Pale lilac at low
   contrast, soft feathered shadows, and opacity-based hierarchy are
   exactly the properties video compression degrades first: subtle hue
   differences flatten, soft edges smear, and low-opacity text loses
   separation from its background before a viewer can read it.

This is a legibility argument, not a taste change. The ethereal direction
was internally coherent and the "SAFE is weightless, VIOLATION is
rupture" thesis was sound in principle — it just assumed a viewing
condition the actual submission does not provide.

## Decision

Supersede `docs/DESIGN.md`'s ethereal direction with a neobrutalist
direction: 3-4px solid black borders on every card/button/input/panel,
hard offset shadows (6-10px, zero blur, pure black, never soft), flat
saturated colour with **no opacity-based hierarchy** (contrast comes from
colour and weight only), oversized black-weight type (headings
80-140px), monospace for every technical value, and dense edge-to-edge
layouts instead of a centred column with empty margins.

Palette: bone/off-white base with near-black text, pure black structural
lines, electric blue (`#0033FF`) for SAFE, electric cyan (`#00E5FF`) for
VIOLATION. The VIOLATION accent deliberately keeps DESIGN.md's one
non-negotiable constraint — cold, never red — carried forward as the one
piece of the old direction that survives: red still reads as alarm/panic,
which still fights the "a proof failed" framing this project wants. Every
other DESIGN.md choice (drift, softness, serif, opacity) is dropped, not
reconciled.

Counterexample traces stay pure-black-field maximum-contrast monospace in
both ambient states — this was already DESIGN.md's one non-negotiable
rule for traces specifically, and neobrutalism makes it the *default*
treatment for every panel rather than an exception carved out for one
component.

`docs/DESIGN.md` is not deleted or rewritten. A superseded-by note is
added at its top per this project's standing rule (CLAUDE.md: "Deleting
or rewriting an ADR" is never acceptable; the same discipline applies to
a superseded design doc). The reasoning it recorded — why ethereal seemed
right for Phase 7 — stays legible as history.

## Alternatives considered

### Keep DESIGN.md's palette, just raise every opacity value further
Rejected. Phase 7b already tried the incremental version of this (raising
`opacity-70` to `opacity-85`) and it was a real improvement but not a
fix — the underlying mechanism (contrast via transparency over a pale
gradient background) is the wrong tool for a compressed 720p video
regardless of how far the opacity values get pushed. The brief for this
round states this as a rule now: "No opacity-based hierarchy — that
produced a real legibility bug last build."

### A middle-ground palette (higher contrast, keep softness/drift)
Rejected as explicitly out of scope by the task brief ("do not try to
reconcile the two, do not blend them") and, independently, because
drift/softness and hard legibility at small compressed resolution are in
tension by construction — motion blur and softened edges are exactly
what a viewer's eye has the least margin to resolve at 720p.

## Consequences

Positive:
- Every screenshot and every second of video gets maximum legibility by
  default, not as a special case for traces.
- No opacity arithmetic to get right under time pressure — a solid colour
  either has enough contrast or it doesn't, checkable at a glance rather
  than by computing a blend against whatever sits behind it.
- The "cold, never red" constraint — the one part of DESIGN.md's
  reasoning that was never about ambient viewing conditions — survives
  intact, so the project's semantic argument (a proof failing is a
  discontinuity, not an alarm) is unchanged even though its visual
  vocabulary is.

Negative / accepted costs:
- `docs/DESIGN.md`'s drift/softness work (Phase 7 step 5: ambient
  background animation, feathered shadows) is fully discarded, not
  adapted — real build time from Phase 7 that does not carry forward.
- Two aesthetic directions now exist in the repo's history
  (`docs/DESIGN.md`, this ADR) rather than one continuous line — accepted
  as the honest record of what happened rather than smoothed into a
  single retroactive narrative.

## Revisit when

- If a future surface is ever meant to be read live, on a desktop, rather
  than through a recorded and compressed video — the opacity-based
  argument above does not apply to that viewing condition, and DESIGN.md's
  reasoning could be legitimately reconsidered rather than treated as
  permanently closed.
