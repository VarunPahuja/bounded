"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, GuardName, PolicyIR, VerificationResult, parseMandate, verifyProof } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";
import { VerdictBadge } from "@/components/proof/VerdictBadge";
import { PropertiesList } from "@/components/proof/PropertiesList";
import { GuardCounterexampleTrace } from "@/components/proof/GuardCounterexampleTrace";
import { useProofState } from "@/lib/proof-state";

// Category-free by default so the naive guard's *only* unsoundness is the
// missing cumulative check -- reproduces docs/DEMO.md's 1:00-2:00 window-
// cap composition beat exactly. A mandate with category restrictions is
// still a valid, real thing to try here (naive_capture_guard is blind to
// category too, so it would surface a P4 finding first) -- just a
// different, equally real finding, not this specific narrated one.
const DEFAULT_MANDATE = "Cap every single payment at Rs 5,000, and don't let the month's total go past Rs 15,000.";

interface GuardCardProps {
  label: string;
  guard: GuardName;
  policy: PolicyIR;
  autoRun?: boolean;
}

// UI 2.0 (ADR-0015): the VIOLATION -> SAFE flip is the beat this surface
// narrates -- make the whole panel change, not just a badge. A resolved
// naive guard turns the entire card into a black/cyan violation block; a
// resolved sound guard turns it into a solid blue/white safe block. Two
// panels side by side, opposite colours, is the "dramatic" the brief asks
// for -- not a colour swatch inside an otherwise-identical white card.
function GuardCard({ label, guard, policy, autoRun }: GuardCardProps) {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setState: setProofState } = useProofState();

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await verifyProof(policy, guard, 8);
      setResult(r);
      setProofState(r.verdict === "violation" ? "violation" : "safe");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // The naive guard's solver-constructed counterexample is the surface's
  // headline evidence -- run it the instant a policy exists, no click
  // required. The sound guard stays button-only: the VIOLATION -> SAFE flip
  // is the beat the demo narrates, and narrating a click that already
  // happened before the viewer saw it would flatten that.
  useEffect(() => {
    if (autoRun) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policy]);

  const resolved = result?.verdict === "violation" ? "violation" : result?.verdict === "safe" ? "safe" : null;
  const panelStyle =
    resolved === "violation"
      ? { background: "var(--ink)", color: "var(--bone)", borderColor: "var(--violation)", boxShadow: "8px 8px 0 var(--violation)" }
      : resolved === "safe"
        ? { background: "var(--safe)", color: "var(--safe-ink)", borderColor: "var(--ink)", boxShadow: "8px 8px 0 var(--ink)" }
        : { background: "var(--panel-bg)", color: "var(--panel-fg)", borderColor: "var(--ink)", boxShadow: "8px 8px 0 var(--ink)" };

  return (
    <div className="flex flex-col gap-4 border-4 p-6" style={panelStyle}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-3xl font-black uppercase tracking-tight">{label}</h3>
        <button onClick={run} disabled={loading} className="nb-btn shrink-0">
          {loading ? "RUNNING…" : "RUN VERIFY_GUARD"}
        </button>
      </div>

      {error && (
        <div className="border-2 border-black bg-white p-3 text-sm font-bold text-red-700">{error}</div>
      )}

      {result && (
        <div className="flex flex-col gap-4">
          <VerdictBadge verdict={result.verdict} horizon={result.horizon} />
          <PropertiesList properties={result.properties_checked} />
          <p className="nb-mono text-sm font-bold">solve time: {result.latency_ms.toFixed(2)} ms</p>
          {result.counterexample && <GuardCounterexampleTrace counterexample={result.counterexample} />}
        </div>
      )}
    </div>
  );
}

export function ProofSurface() {
  const [mandateText, setMandateText] = useState(DEFAULT_MANDATE);
  const [policy, setPolicy] = useState<PolicyIR | null>(null);
  const [ambiguousMessage, setAmbiguousMessage] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleParse() {
    setParsing(true);
    setError(null);
    setAmbiguousMessage(null);
    setPolicy(null);
    try {
      const res = await parseMandate(mandateText);
      if (res.status === "ambiguous") {
        setAmbiguousMessage(res.message ?? "mandate rejected as ambiguous");
      } else {
        setPolicy(res.policy);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setParsing(false);
    }
  }

  // No surface opens empty: parse the default mandate the instant this
  // surface mounts, so the naive guard's counterexample below has a
  // policy to run against without a click.
  const hasAutoParsed = useRef(false);
  useEffect(() => {
    if (!hasAutoParsed.current) {
      hasAutoParsed.current = true;
      handleParse();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="flex w-full flex-col gap-8 px-8 py-10 md:px-14">
      <header>
        <h1 className="nb-heading" style={{ fontSize: "clamp(56px, 8vw, 120px)" }}>
          Proof
        </h1>
        <p className="mt-4 max-w-3xl text-lg font-bold" style={{ color: "var(--muted-fg)" }}>
          Same policy, same solver, two guards. The naive guard checks each payment against the
          per-payment cap alone; the sound guard also tracks the running window spend. Nobody
          writes the counterexample below — the solver searches every guard-admitted sequence up
          to horizon 8 and constructs it.
        </p>
      </header>

      <div className="flex flex-col gap-3">
        <textarea
          className="nb-input min-h-[80px] w-full max-w-4xl text-lg"
          rows={2}
          value={mandateText}
          onChange={(e) => setMandateText(e.target.value)}
        />
        <div>
          <button onClick={handleParse} disabled={parsing} className="nb-btn">
            {parsing ? "PARSING…" : "PARSE MANDATE"}
          </button>
        </div>
      </div>

      {error && (
        <div className="nb-panel-flat p-4 text-base font-bold" style={{ borderColor: "var(--violation)" }}>
          {error}
        </div>
      )}
      {ambiguousMessage && (
        <div className="nb-panel-flat p-4 text-base font-bold">
          <span className="uppercase">rejected as ambiguous:</span> {ambiguousMessage}
        </div>
      )}

      {policy && (
        <>
          <div className="nb-mono flex flex-wrap gap-3 text-sm font-bold">
            {policy.per_txn_cap_paise !== null && <span className="nb-chip">PER-TXN CAP {paiseToRupees(policy.per_txn_cap_paise)}</span>}
            {policy.window_cap_paise !== null && (
              <span className="nb-chip">
                WINDOW CAP {paiseToRupees(policy.window_cap_paise)} ({policy.window ?? "unset"})
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <GuardCard label="Naive guard" guard="naive" policy={policy} autoRun />
            <GuardCard label="Sound guard" guard="sound" policy={policy} />
          </div>
        </>
      )}
    </section>
  );
}
