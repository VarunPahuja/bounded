# ADR-0012: Azure OpenAI (gpt-4.1-mini) replaces the Groq/Gemini plan

- Status: Accepted
- Date: 2026-09-01
- Deciders: Varun P.
- Supersedes: MASTER.md section 2's original LLM layer choice (Groq primary, Gemini fallback)
- Superseded by: -

## Context

MASTER.md section 2 locked Groq (`llama-3.3-70b-versatile`, free tier) as
the primary parser model and Gemini (`gemini-2.5-flash`, free tier) as
fallback, before Phase 5 was reached. Neither was ever tried. There was no
failure, no rate-limit problem, no free-tier issue encountered in practice
— that stack was chosen on paper, in advance, without checking what was
already available.

By the time Phase 5 actually started, an Azure OpenAI endpoint and API key
already existed, provisioned earlier with INR 9,555 in credits, unrelated
to this project. Groq would have meant a signup step. That is the entire
difference between the two options for what this phase needs: an LLM that
turns English/Hinglish text into a JSON object matching a strict schema, a
few hundred tokens per call, ten fixture mandates recorded once and
replayed after. Provider choice here is not load-bearing on anything the
project claims — ADR-0005's rule (the LLM proposes structure, the solver
decides) holds regardless of which model drafts the JSON.

## Decision

Use Azure OpenAI, `gpt-4.1-mini`, via the official `openai` Python SDK's
`AzureOpenAI` client, as the sole provider for `policy/parse.py`. No
fallback provider — one provider, actually exercised end-to-end (including
the live test that hits the real endpoint before Phase 5 closes), instead
of a second one wired into the code and never run for real.

## Alternatives considered

### Groq free tier, as originally planned in MASTER.md
Rejected: not because of anything Groq did or failed to do — it was never
tested — but because it required a signup this project didn't already
have, and the already-provisioned Azure endpoint made that signup pure
overhead for a four-day-remaining build. Zero friction beat ten minutes of
friction on a component whose job is small and whose specific provider
does not affect what the project proves.

### Keep Gemini as a fallback alongside Azure OpenAI
Rejected: a fallback that is never exercised for real is a code path with
no test coverage backing its claim to work, and this project's own
discipline (CLAUDE.md: "green without the network is not proof") argues
against carrying one. One provider, actually run live, is a stronger claim
than two providers where only one has ever been called.

## Consequences

Positive:
- Zero new signup friction; build time went to Phase 5's actual work
  instead of provisioning a second API key.
- One provider means the live test (`tests/policy/test_parse_live.py`)
  gives real coverage of the only path that runs in production, rather
  than splitting confidence across a primary that's tested and a fallback
  that isn't.

Negative / accepted costs:
- Azure OpenAI credits are not literally free, unlike the original
  free-tier plan — corrected in MASTER.md section 2 and section 6's cost
  table. The actual draw is negligible (a few hundred tokens per mandate
  parse, recorded to cassettes once and replayed after), but "zero cost"
  is no longer an accurate claim for this layer.
- No fallback if Azure OpenAI has an outage during the live test or
  during recording — accepted, since this project's core guarantee never
  depends on the parser being available; verify_action's soundness
  argument does not route through policy/parse.py at all
  (test_parse_is_not_in_enforcement_path).

## Revisit when

- A second provider is genuinely needed (e.g., Azure access lapses before
  submission) — at that point, actually exercise it live before relying on
  it, per this ADR's own reasoning.

## Note on how this ADR came to exist

An earlier draft of MASTER.md's correction and this ADR both stated that
"Groq's free tier proved unworkable in practice" as the reason for the
swap. That was false — invented, not observed, and corrected before this
ADR was written. It's recorded here because a plausible-sounding failure
narrative that never happened, sitting in this project's own
documentation, is the exact failure mode the project's central claim is
about: a confident-sounding output that doesn't survive being checked.
The actual reason was smaller and less dramatic than that draft made it
sound, and the smaller reason is the one on record.
