"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, PolicyIR, VerificationResult, activateMandate, fetchDemoMandate, parseMandate } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";
import { VerdictBadge } from "@/components/proof/VerdictBadge";
import { useProofState } from "@/lib/proof-state";

// The exact string docs/DEMO.md's 0:25-1:00 beat uses and rehearses --
// confirmed (docs/DEMO.md's pre-record checklist) not to trigger the
// known max_txn_count/window parse flake (docs/LOG.md, Phase 5).
const RECORDING_MANDATE =
  "This agent may spend up to ₹15,000 this month, no single payment above ₹5,000, " +
  "groceries and utilities only, and it can never refund more than it charged.";

// Deliberately vague amount, no number at all -- the parser's own hard
// rule (policy/parse.py's system prompt) is to never invent one.
const AMBIGUOUS_MANDATE = "Keep the agent's spending reasonable and don't let it go overboard.";

// UI 2.0 (ADR-0015): the typed side renders as a black-field mono block --
// visually a "compiled" artifact next to the English prose, so the
// translation the brief asks to make legible at a glance reads as a
// contrast in kind (prose vs. typed object), not just two white cards.
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
    <div className="nb-mono p-6" style={{ background: "var(--trace-bg)", color: "var(--trace-fg)", border: "4px solid var(--trace-fg)", boxShadow: "8px 8px 0 var(--safe)" }}>
      <div className="mb-4 text-lg font-black uppercase tracking-tight" style={{ color: "var(--safe)" }}>
        PolicyIR — what everything downstream reads
      </div>
      <dl className="flex flex-col gap-2 text-base">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-wrap gap-2">
            <dt style={{ color: "var(--trace-muted)" }}>{k}:</dt>
            <dd className="font-bold">{v}</dd>
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
  const { setState: setProofState } = useProofState();

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
      const r = await activateMandate(policy, 8);
      setActivation(r);
      setProofState(r.verdict === "violation" ? "violation" : "safe");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setActivating(false);
    }
  }

  // No surface opens empty: pre-populate with the already-parsed-and-
  // activated recording mandate. Reads a cached result
  // (api/mandate_cache.py) -- no live Azure call on mount, so this can
  // never flake on camera.
  const hasLoadedDemo = useRef(false);
  useEffect(() => {
    if (hasLoadedDemo.current) return;
    hasLoadedDemo.current = true;
    fetchDemoMandate()
      .then((demo) => {
        setText(demo.mandate_text);
        setPolicy(demo.policy);
        setActivation(demo.activation);
        setProofState(demo.activation.verdict === "violation" ? "violation" : "safe");
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="flex w-full flex-col gap-8 px-8 py-10 md:px-14">
      <header>
        <h1 className="nb-heading" style={{ fontSize: "clamp(56px, 8vw, 120px)" }}>
          Mandate
        </h1>
        <p className="mt-4 max-w-3xl text-lg font-bold" style={{ color: "var(--muted-fg)" }}>
          The model only translates English into a typed object — it never decides whether a
          payment is allowed. If it can&apos;t extract every field without guessing, it refuses
          rather than filling the gap. That refusal is shown below, not hidden.
        </p>
      </header>

      <div className="nb-mono flex flex-wrap gap-4 text-sm font-black">
        <button onClick={() => setText(RECORDING_MANDATE)} className="underline underline-offset-4">
          LOAD THE RECORDING MANDATE
        </button>
        <span>·</span>
        <button onClick={() => setText(AMBIGUOUS_MANDATE)} className="underline underline-offset-4">
          LOAD AN AMBIGUOUS EXAMPLE
        </button>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
        <div className="flex flex-col gap-4">
          <div className="text-lg font-black uppercase tracking-tight">English (untrusted input)</div>
          <textarea className="nb-input min-h-[160px] text-xl" value={text} onChange={(e) => setText(e.target.value)} />
          <div>
            <button onClick={handleParse} disabled={parsing} className="nb-btn">
              {parsing ? "PARSING…" : "PARSE MANDATE"}
            </button>
          </div>
          {error && (
            <div className="nb-panel-flat p-4 text-base font-bold" style={{ borderColor: "var(--violation)" }}>
              {error}
            </div>
          )}
          {ambiguousMessage && (
            <div className="nb-panel-flat p-4 text-base font-bold" style={{ borderStyle: "dashed" }}>
              <div className="uppercase">refused — ambiguous, not guessed</div>
              <p className="mt-1">{ambiguousMessage}</p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <div className="text-lg font-black uppercase tracking-tight">Typed PolicyIR (compiled)</div>
          {policy ? (
            <>
              <PolicyView policy={policy} />
              <div>
                <button onClick={handleActivate} disabled={activating} className="nb-btn">
                  {activating ? "PROVING…" : "ACTIVATE (PROVE SERVABLE)"}
                </button>
              </div>
              {activation && (
                <div className="nb-panel flex flex-col gap-3 p-5">
                  <VerdictBadge verdict={activation.verdict} horizon={activation.horizon} />
                  <p className="text-base font-bold">
                    {activation.verdict === "safe"
                      ? "This policy is provably servable: no sequence of guard-admitted actions up to this horizon can breach it."
                      : activation.error_message ?? "Not servable — see the counterexample the solver constructed."}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="nb-panel-flat flex h-full min-h-[200px] items-center justify-center p-8 text-lg font-bold" style={{ borderStyle: "dashed" }}>
              parse a mandate to see the typed policy here
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
