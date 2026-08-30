---
name: adr
description: Architecture Decision Records: one-page template, numbering, supersession, generated index, CI check on shared contracts. Use when deciding, reviewing, or asked why something was built this way.
---

# Architecture Decision Records

An ADR captures one decision, the forces that shaped it, the options that lost, and what you agreed to live with. One page. Numbered. Never edited after acceptance, only superseded.

The value shows up in three places: a reviewer asks "why not X" and you have an answer with a date on it, a teammate stops re-opening a settled question, and six weeks later you can tell whether the reason for a choice still holds.

## Template

Use this exact structure. Consistency is what makes them skimmable in bulk.

```markdown
# ADR-0007: Hash-chained audit ledger instead of a Merkle tree

- Status: Accepted
- Date: 2026-09-02
- Deciders: <names>
- Supersedes: -
- Superseded by: -

## Context

What is true right now that forces a choice. Constraints, deadlines, team
size, existing commitments, the thing that broke. Facts, not opinions.
If a reader disagrees with the decision, this is the section that should
change their mind, or reveal that you were solving a different problem.

## Decision

One sentence in the active voice, stating what will be done.
Then the specifics: what gets built, where it lives, who owns it.

## Alternatives considered

### Merkle tree over the audit log
Rejected: buys O(log n) inclusion proofs, and no consumer has asked for
proofs. Roughly 3x the code for a property nobody consumes yet.

### Append-only table, no hashing
Rejected: a DB trigger stops accidental writes but leaves no evidence
against a privileged edit, which is the threat the demo has to answer.

## Consequences

Positive:
- Verification is a linear pass, ~40 lines, testable offline.

Negative / accepted costs:
- Full-chain verification is O(n) and gets slow past ~1M rows.
- No third-party inclusion proofs without a rewrite.

## Revisit when

- A consumer asks for inclusion proofs, or
- the ledger passes 1M rows, or
- an external auditor is added to the system.
```

The "Revisit when" section is what most templates leave out and what makes an ADR useful a year later. A decision without a trip-wire either gets defended past its expiry or thrown out on a whim.

## Rules

**Numbering.** `ADR-0001`, zero padded, never reused. Filename `docs/adr/0001-short-kebab-title.md`. The number is the identifier people cite in PRs and reviews.

**Immutable after Accepted.** Fix typos, nothing else. A decision that changes gets a new ADR with `Supersedes: ADR-0007`, and the old one is edited only to set `Status: Superseded by ADR-0019`. The trail of reversed decisions is one of the most useful things in the repo.

**Status is one of:** `Proposed`, `Accepted`, `Rejected`, `Superseded by ADR-XXXX`, `Deprecated`. Proposed ADRs are how you have the argument in writing before the code exists.

**One decision per record.** If the title needs an "and", split it.

**Present tense, active voice.** "We store money as integer paise", not "it was decided that money would be stored".

**Write the losers properly.** An "Alternatives" section that lists options with one dismissive line each is worse than none: it looks like diligence and provides none. Each rejected option needs the specific reason it lost under your constraints. That is the only part a future reader cannot reconstruct.

**One page.** If it needs more, the extra belongs in a design doc that the ADR links to.

## When to write one

Write an ADR when the decision:

- changes an interface, contract, or schema that more than one person depends on
- adds a dependency or a service
- is expensive to reverse (data migrations, wire formats, auth model)
- cuts scope deliberately, so nobody later reads the gap as an oversight
- was argued about for more than about twenty minutes
- you would have to explain from scratch in a review

Do not write one for: naming, formatting, minor version bumps, anything reversible in an afternoon, or a choice with no realistic alternative. Ceremony on trivia is how teams learn to ignore the ADR folder.

A useful trigger on a shared-ownership repo: **any change to shared contracts requires an accepted ADR before merge.** It converts "who changed the enum" arguments into a reviewable artifact, and it forces the change to be described before it is written.

## Index

Keep `docs/adr/README.md` generated, not hand-maintained.

```python
# scripts/adr_index.py
import re, pathlib

rows = []
for p in sorted(pathlib.Path("docs/adr").glob("[0-9]*.md")):
    text = p.read_text()
    title = re.search(r"^# (.+)$", text, re.M).group(1)
    status = re.search(r"^- Status: (.+)$", text, re.M).group(1)
    date = re.search(r"^- Date: (.+)$", text, re.M).group(1)
    rows.append(f"| [{title}]({p.name}) | {status} | {date} |")

pathlib.Path("docs/adr/README.md").write_text(
    "# Architecture Decision Records\n\n"
    "| Decision | Status | Date |\n|---|---|---|\n" + "\n".join(rows) + "\n")
```

Sorting by number gives you chronological order for free. Superseded entries stay in the table, greyed by their status column.

## Two worked examples

Short, so the shape is obvious.

```markdown
# ADR-0003: The policy engine is the only component that mutates permissions

- Status: Accepted
- Date: 2026-08-24
- Deciders: <names>

## Context
Three components produce signals about whether an agent should get more
authority: an LLM coordinator, a statistical trust engine, and a human
approver. If any of them can write to the permission table, no reviewer
can answer "what raised this limit" from the code.

## Decision
The trust engine emits a TrustEvaluation. The coordinator emits a
Recommendation. Neither writes to the database. The policy engine consumes
both plus a human approval token and is the sole writer of permission state.

## Alternatives considered
### Coordinator writes directly when confidence is high
Rejected: makes the LLM part of the trusted computing base. Any prompt
injection in an input field becomes a privilege escalation.

### Trust engine writes, coordinator advises
Rejected: buries the human-approval requirement inside a statistics module
and splits enforcement across two components.

## Consequences
Positive: one file to audit for permission changes; injection cannot escalate.
Negative: an extra hop and a contract to keep in sync; the coordinator cannot
act on time-sensitive signals without a policy round trip.

## Revisit when
Latency of the policy round trip becomes a user-visible problem.
```

```markdown
# ADR-0004: Stub-first integration between lanes

- Status: Accepted
- Date: 2026-08-25
- Deciders: <names>

## Context
Four people own four lanes with a hard deadline. Sequential integration
means everyone downstream idles until upstream lands, and nothing is
demoable until the last week.

## Decision
Every lane ships a stub behind its contract on day one: fixture files for
the trust engine, GOVERNANCE_MODE=stub for the LLM layer, MSW mocks against
the OpenAPI schema for the frontend. Real implementations replace stubs
behind the same interface.

## Alternatives considered
### Integrate when components are ready
Rejected: the critical path becomes serial and integration bugs all surface
in the final week, which is also the presentation week.

### Shared dev database with real components
Rejected: couples every lane's local loop to every other lane's uptime.

## Consequences
Positive: main is demoable from week 1; contract breaks surface immediately.
Negative: stubs need maintaining; a stub that drifts from the real thing
gives false confidence, so contract tests run against both.

## Revisit when
All four lanes are real and the stubs cost more than they save.
```

## CI check

```yaml
- name: shared contract changes require an ADR
  run: |
    if git diff --name-only origin/main... | grep -q '^shared/'; then
      git diff --name-only origin/main... | grep -q '^docs/adr/[0-9]' || {
        echo "shared/ changed without an ADR. See docs/adr/README.md"; exit 1; }
    fi
```

Crude and effective. It does not check that the ADR is any good, but it makes skipping one a deliberate act rather than an oversight.

## Related docs, kept separate

- `context.md` at repo root: what the project is, the lanes, how to run it. Rewritten freely. Answers "what is this".
- `docs/adr/`: immutable decisions. Answers "why is this like this".
- `docs/log/YYYY-MM-DD.md`: what happened, what broke, what is next. Answers "where are we".

Keeping the three separate is what stops the ADR folder turning into a diary, which is the failure mode that kills the practice.
