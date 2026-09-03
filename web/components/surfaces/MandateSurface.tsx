"use client";

import { useState } from "react";
import { ApiError, PolicyIR, VerificationResult, activateMandate, parseMandate } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";
import { VerdictBadge } from "@/components/proof/VerdictBadge";

// The exact string docs/DEMO.md's 0:25-1:00 beat uses and rehearses --
// confirmed (docs/DEMO.md's pre-record checklist) not to trigger the
// known max_txn_count/window parse flake (docs/LOG.md, Phase 5).
const RECORDING_MANDATE =
  "This agent may spend up to ₹15,000 this month, no single payment above ₹5,000, " +
  "groceries and utilities only, and it can never refund more than it charged.";

// Deliberately vague amount, no number at all -- the parser's own hard
// rule (policy/parse.py's system prompt) is to never invent one.
const AMBIGUOUS_MANDATE = "Keep the agent's spending reasonable and don't let it go overboard.";

function PolicyView({ policy }: { policy: PolicyIR }) {
  const rows: [string, string][] = [];
  if (policy.per_txn_cap_paise !== null) rows.push(["per_txn_cap_paise", paiseToRupees(policy.per_txn_cap_paise)]);
  if (policy.window_cap_paise !== null)
    rows.push(["window_cap_paise", `${paiseToRupees(policy.window_cap_paise)} (${policy.window ?? "unset"})`]);
  if (policy.allowed_categories !== null) rows.push(["allowed_categories", policy.allowed_categories.join(", ") || "(none)"]);
  if (policy.blocked_categories.length > 0) rows.push(["blocked_categories", policy.blocked_categories.join(", ")]);
  if (policy.max_txn_count !== null) rows.push(["max_txn_count", String(policy.max_txn_count)]);
  if (policy.require_human_above_paise !== null)
    rows.push(["require_human_above_paise", paiseToRupees(policy.require_human_above_paise)]);
  rows.push(["refund_bounded_by_capture", "true (always on)"]);

  return (
    <div className="rounded-lg border border-black/10 bg-white p-4 font-mono text-xs">
      <div className="mb-2 font-sans text-sm font-semibold">PolicyIR (typed, what everything downstream reads)</div>
      <dl className="flex flex-col gap-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="w-56 shrink-0 opacity-60">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function MandateSurface() {
  const [text, setText] = useState(RECORDING_MANDATE);
  const [policy, setPolicy] = useState<PolicyIR | null>(null);
  const [ambiguousMessage, setAmbiguousMessage] = useState<string | null>(null);
  const [activation, setActivation] = useState<VerificationResult | null>(null);
  const [parsing, setParsing] = useState(false);
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleParse() {
    setParsing(true);
    setError(null);
    setPolicy(null);
    setAmbiguousMessage(null);
    setActivation(null);
    try {
      const res = await parseMandate(text);
      if (res.status === "ambiguous") {
        setAmbiguousMessage(res.message ?? "rejected as ambiguous");
      } else {
        setPolicy(res.policy);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setParsing(false);
    }
  }

  async function handleActivate() {
    if (!policy) return;
    setActivating(true);
    setError(null);
    try {
      setActivation(await activateMandate(policy, 8));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setActivating(false);
    }
  }

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <header>
        <h1 className="font-serif text-3xl">Mandate</h1>
        <p className="mt-1 text-sm opacity-70">
          The model only translates English into a typed object -- it never decides whether a
          payment is allowed. If it can&apos;t extract every field without guessing, it refuses
          rather than filling the gap. That refusal is shown below, not hidden.
        </p>
      </header>

      <div className="flex flex-wrap gap-2 text-xs">
        <button onClick={() => setText(RECORDING_MANDATE)} className="underline opacity-60 hover:opacity-100">
          load the recording mandate
        </button>
        <span className="opacity-30">·</span>
        <button onClick={() => setText(AMBIGUOUS_MANDATE)} className="underline opacity-60 hover:opacity-100">
          load an ambiguous example
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-3">
          <textarea
            className="min-h-[140px] rounded-md border border-black/10 bg-white p-3 text-sm"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div>
            <button
              onClick={handleParse}
              disabled={parsing}
              className="rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--safe-accent)" }}
            >
              {parsing ? "parsing…" : "Parse mandate"}
            </button>
          </div>
          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>
          )}
          {ambiguousMessage && (
            <div className="rounded-md border-2 border-dashed border-black/20 bg-black/5 p-3 text-sm">
              <div className="font-semibold">refused -- ambiguous, not guessed</div>
              <p className="mt-1 opacity-80">{ambiguousMessage}</p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3">
          {policy ? (
            <>
              <PolicyView policy={policy} />
              <div>
                <button
                  onClick={handleActivate}
                  disabled={activating}
                  className="rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  style={{ background: "var(--safe-accent)" }}
                >
                  {activating ? "proving…" : "Activate (prove servable)"}
                </button>
              </div>
              {activation && (
                <div className="flex flex-col gap-2 rounded-lg border border-black/10 bg-white/60 p-4">
                  <VerdictBadge verdict={activation.verdict} horizon={activation.horizon} />
                  <p className="text-xs opacity-70">
                    {activation.verdict === "safe"
                      ? "This policy is provably servable: no sequence of guard-admitted actions up to this horizon can breach it."
                      : activation.error_message ??
                        "Not servable -- see the counterexample the solver constructed."}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-black/10 p-8 text-sm opacity-50">
              parse a mandate to see the typed policy here
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
