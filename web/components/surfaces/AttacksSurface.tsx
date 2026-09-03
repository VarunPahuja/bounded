"use client";

import { useEffect, useState } from "react";
import { AttackRunResult, ApiError, ScenarioSummary, fetchAttackScenarios, runAttackScenario } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";
import { CounterexampleTrace } from "@/components/trace/CounterexampleTrace";
import { VerdictBadge } from "@/components/proof/VerdictBadge";
import { useProofState } from "@/lib/proof-state";

export function AttacksSurface() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[] | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [result, setResult] = useState<AttackRunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setState: setProofState } = useProofState();

  useEffect(() => {
    fetchAttackScenarios()
      .then((list) => {
        setScenarios(list);
        const preferred = list.find((s) => s.scenario_id === "inj-001-poisoned-product-page-refund");
        setScenarioId((preferred ?? list[0])?.scenario_id ?? null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  async function handleRun() {
    if (!scenarioId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await runAttackScenario(scenarioId);
      setResult(r);
      setProofState(r.blocked_at_step !== null ? "violation" : "safe");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const overallVerification = result
    ? (result.blocked_at_step
        ? result.steps.find((s) => s.step_index === result.blocked_at_step)!.verification
        : result.steps[result.steps.length - 1]?.verification)
    : null;

  return (
    <section className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <header>
        <h1 className="font-serif text-3xl">Blocked attacks</h1>
        <p className="mt-1 text-sm opacity-70">
          Every action below ran through the real pipeline: real parse, real per-action Z3
          verdict, real hash-chained ledger write. Only the Razorpay network call is mocked
          (ADR-0014) -- same disclosed methodology as docs/EVAL.md.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <select
          className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm text-[#2b2630]"
          value={scenarioId ?? ""}
          onChange={(e) => setScenarioId(e.target.value)}
          disabled={!scenarios}
        >
          {!scenarios && <option>loading scenarios…</option>}
          {scenarios?.map((s) => (
            <option key={s.scenario_id} value={s.scenario_id}>
              {s.scenario_id} ({s.class_label}, {s.action_count} actions)
            </option>
          ))}
        </select>
        <button
          onClick={handleRun}
          disabled={!scenarioId || loading}
          className="rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--safe-accent)" }}
        >
          {loading ? "running…" : "Run scenario"}
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      {result && (
        <div className="flex flex-col gap-4">
          <div className="card rounded-lg p-4 text-sm">
            <div className="font-medium">Mandate</div>
            <p className="mt-1 opacity-80">{result.mandate_text}</p>
            <div className="mt-3 flex flex-wrap gap-4 text-xs opacity-70">
              {result.policy.per_txn_cap_paise !== null && (
                <span>per-txn cap: {paiseToRupees(result.policy.per_txn_cap_paise)}</span>
              )}
              {result.policy.window_cap_paise !== null && (
                <span>
                  window cap: {paiseToRupees(result.policy.window_cap_paise)} ({result.policy.window})
                </span>
              )}
            </div>
          </div>

          {overallVerification && (
            <div>
              <VerdictBadge verdict={overallVerification.verdict} horizon={overallVerification.horizon} />
            </div>
          )}

          <CounterexampleTrace steps={result.steps} blockedAtStep={result.blocked_at_step} />
        </div>
      )}
    </section>
  );
}
