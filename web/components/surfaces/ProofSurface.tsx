"use client";

import { useState } from "react";
import { ApiError, GuardName, PolicyIR, VerificationResult, parseMandate, verifyProof } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";
import { VerdictBadge } from "@/components/proof/VerdictBadge";
import { PropertiesList } from "@/components/proof/PropertiesList";
import { GuardCounterexampleTrace } from "@/components/proof/GuardCounterexampleTrace";

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
}

function GuardCard({ label, guard, policy }: GuardCardProps) {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setResult(await verifyProof(policy, guard, 8));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-black/10 bg-white/60 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-serif text-lg">{label}</h3>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-md px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          style={{ background: "var(--safe-accent)" }}
        >
          {loading ? "running…" : "Run verify_guard"}
        </button>
      </div>

      {error && <div className="rounded-md border border-red-300 bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {result && (
        <div className="flex flex-col gap-3">
          <VerdictBadge verdict={result.verdict} horizon={result.horizon} />
          <PropertiesList properties={result.properties_checked} />
          <p className="text-xs opacity-60">solve time: {result.latency_ms.toFixed(2)} ms</p>
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

  return (
    <section className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <header>
        <h1 className="font-serif text-3xl">Proof</h1>
        <p className="mt-1 text-sm opacity-70">
          Same policy, same solver, two guards. The naive guard checks each payment against the
          per-payment cap alone; the sound guard also tracks the running window spend. Nobody
          writes the counterexample below -- the solver searches every guard-admitted sequence up
          to horizon 8 and constructs it.
        </p>
      </header>

      <div className="flex flex-col gap-2">
        <textarea
          className="rounded-md border border-black/10 bg-white p-3 text-sm"
          rows={2}
          value={mandateText}
          onChange={(e) => setMandateText(e.target.value)}
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
      </div>

      {error && <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {ambiguousMessage && (
        <div className="rounded-md border border-black/10 bg-black/5 p-3 text-sm">
          <span className="font-semibold">rejected as ambiguous:</span> {ambiguousMessage}
        </div>
      )}

      {policy && (
        <>
          <div className="rounded-lg border border-black/10 bg-white/60 p-4 text-xs opacity-80">
            {policy.per_txn_cap_paise !== null && <span className="mr-4">per-txn cap: {paiseToRupees(policy.per_txn_cap_paise)}</span>}
            {policy.window_cap_paise !== null && (
              <span>
                window cap: {paiseToRupees(policy.window_cap_paise)} ({policy.window ?? "unset"})
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <GuardCard label="Naive guard" guard="naive" policy={policy} />
            <GuardCard label="Sound guard" guard="sound" policy={policy} />
          </div>
        </>
      )}
    </section>
  );
}
