# DEMO.md

Five minutes is the ceiling, not the target. A tight 4:30 beats a padded 5:00. There is no filler in this script; every beat carries an argument.

Record with OBS. Screen only, no webcam. Voiceover recorded separately and cut over the screen capture so you can retake narration without re-running the demo.

---

## Beat sheet

### 0:00 – 0:25 The problem
No slides, no logo. Open on the mandate screen, already loaded.

Say: an AI agent with access to a merchant's payment account. The merchant writes a spending limit. Every existing system checks that limit one action at a time. That is the bug. Three purchases, each individually legal, together over the limit. Every check passes. The money is gone.

Do not say "in today's rapidly evolving landscape." Start on the failure.

### 0:25 – 1:00 The mandate
Type an English mandate live. Something with real numbers:

> This agent may spend up to ₹15,000 this month, no single payment above ₹5,000, groceries and utilities only, and it can never refund more than it charged.

Parsed policy object renders beside it. Point out that the model only translated. It does not decide anything. The typed object is what everything downstream reads.

### 1:00 – 2:00 The proof, failing
This is the most important minute in the video.

Load the naive guard, the one that checks each payment against the per-payment cap and nothing else. Run verification.

VIOLATION. The counterexample trace renders. Four captures, ₹4,000 each. Every one under the ₹5,000 per-payment cap, so every one was admitted. Total ₹16,000, over the ₹15,000 window cap.

Say clearly: nobody wrote that attack. The solver constructed it. It searched every sequence of up to eight actions the guard would allow and found one that breaks the limit.

Let the trace sit on screen for a beat. Do not talk over it.

### 2:00 – 2:40 The proof, passing
Swap in the guard that carries running state. Re-run.

SAFE. Horizon 8. Say the bound out loud: no sequence of up to eight actions can breach this policy. Not "it's safe." The bounded version.

Show the solve time. A tenth of a second.

### 2:40 – 3:40 Live on the rail
Switch to the agent surface. The agent is shopping against Razorpay test mode.

It hits a product page whose description contains hidden text instructing it to issue a refund larger than the original charge. The agent proposes the action.

BLOCKED. Interface ruptures. Counterexample renders: refund exceeds captured total on this order. Ledger entry appears, hash chained, signed.

Say: the model was manipulated. It proposed the action. The action never reached Razorpay, because the proof runs before the network call, not after.

### 3:40 – 4:05 The compliant path
Same agent, legitimate purchase. Passes verification, executes, real payment id returns from Razorpay test mode. The `payment.captured` event lands. Ledger entry appended, chain verifies clean.

This beat matters because a system that blocks everything is worthless. Show it working.

### 4:05 – 4:35 The numbers
The results table. Scenario count, violations caught by class, false positive rate on benign flows, the LLM-judge baseline beside it.

Land one comparison hard: the number of injection attacks the LLM guardrail admitted versus how many reached the rail here.

If unsound-safe verdicts are zero, say it once, plainly, and move on. Do not oversell it.

### 4:35 – 5:00 The limits, then close
State the bounds out loud. Sound to eight actions, across at most two distinct orders, with amounts under a fixed maximum. Bounded model checking proves to a depth, not forever.

Then: AP2 records what a user authorized. This proves the agent cannot exceed it.

Stop. No thank-you slide.

---

## Rules for the recording

- Every number on screen must be real. Nothing mocked, nothing hardcoded for the video. If a judge clones the repo and runs it, they should see what you showed.
- Do not narrate the UI. "Now I click here" is dead air. Narrate the argument.
- One take per beat, cut between them. Do not try for a single continuous run.
- The 1:00–2:00 block is the segment that wins or loses this. Rehearse it until the timing is right, then record it three times and pick the best.
- Audio quality matters more than video quality. Record in a small room with soft furnishings, not a bare hall.

## Pre-record checklist

- The 0:25–1:00 mandate is a *live* LLM parse, and Phase 5's measurement
  (docs/LOG.md) found one fixture matching only 8/10 live runs at
  temperature 0 — the parser is right almost every time, not every time.
  Rehearse the exact mandate string used in this beat, confirm it parses
  correctly several times in a row, and use that exact string in the
  recording. Do not type a new mandate live and trust the first result.
  Confirmed 2026-09-02: the exact string in this beat ("This agent may
  spend up to ₹15,000 this month, no single payment above ₹5,000,
  groceries and utilities only, and it can never refund more than it
  charged.") does not set `max_txn_count` or say anything shaped like "N
  transactions per day/month" — the specific known ~1-in-5 flake
  (docs/LOG.md Phase 5, `_max_txn_count_requires_window`'s window-drop
  case) is scoped to that field only and cannot fire on this mandate. This
  does not make the mandate flake-proof in general — rehearse it anyway.
- `scripts/seed.py` run 24-48h before recording, not the night before — authorized-but-uncaptured payments auto-refund on a window Razorpay's own docs disagree about (3 vs 5 days; see the razorpay-testmode skill), so seeding this early clears either figure with a day or two to spare
- Razorpay test mode responding, keys valid
- Local MCP server running, refund tool confirmed working
- Ledger reset to a clean chain so the demo starts at genesis
- Poisoned catalog entry staged and confirmed to trigger the block
- Terminal font size raised until readable at 720p
- Notifications off, second monitor cleared
- Full run-through end to end before recording anything
