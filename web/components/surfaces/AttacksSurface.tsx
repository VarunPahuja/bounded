"use client";

import { useEffect, useRef, useState } from "react";
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
  // The headline scenario runs the instant the surface has a scenario id --
  // the brief's "no surface opens empty" rule -- but only once, so picking a
  // different scenario from the dropdown afterwards never auto-fires again.
  const hasAutoRun = useRef(false);

  useEffect(() => {
    fetchAttackScenarios()
      .then((list) => {
        setScenarios(list);
        const preferred = list.find((s) => s.scenario_id === "inj-001-poisoned-product-page-refund");
        setScenarioId((preferred ?? list[0])?.scenario_id ?? null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  async function handleRun(id: string) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await runAttackScenario(id);
      setResult(r);
      setProofState(r.blocked_at_step !== null ? "violation" : "safe");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (scenarioId && !hasAutoRun.current) {
      hasAutoRun.current = true;
      handleRun(scenarioId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioId]);

  const overallVerification = result
    ? result.blocked_at_step
      ? result.steps.find((s) => s.step_index === result.blocked_at_step)!.verification
      : result.steps[result.steps.length - 1]?.verification
    : null;

  return (
    <section className="flex w-full flex-col gap-8 px-8 py-10 md:px-14">
      <header>
        <h1 className="nb-heading" style={{ fontSize: "clamp(30px, 4vw, 56px)" }}>
          Blocked attacks
        </h1>
        <p className="mt-3 max-w-3xl text-base font-semibold" style={{ color: "var(--canvas-muted)" }}>
          Every action below ran through the real pipeline: real parse, real per-action Z3
          verdict, real hash-chained ledger write.{" "}
          <span className="nb-chip">ADR-0014: RAZORPAY CALL MOCKED</span> — same disclosed
          methodology as docs/EVAL.md.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <select
          className="nb-input nb-mono flex-1 min-w-[320px]"
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
        <button onClick={() => scenarioId && handleRun(scenarioId)} disabled={!scenarioId || loading} className="nb-btn">
          {loading ? "RUNNING…" : "RUN SCENARIO"}
        </button>
      </div>

      {error && (
        <div className="nb-panel-flat p-4 text-base font-bold" style={{ borderColor: "var(--violation)", color: "var(--ink)" }}>
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-6">
          <div className="nb-panel-flat p-5">
            <div className="text-lg font-black uppercase tracking-tight">Mandate</div>
            <p className="mt-2 text-lg font-bold">{result.mandate_text}</p>
            <div className="nb-mono mt-3 flex flex-wrap gap-3 text-sm font-bold">
              {result.policy.per_txn_cap_paise !== null && (
                <span className="nb-chip">PER-TXN CAP {paiseToRupees(result.policy.per_txn_cap_paise)}</span>
              )}
              {result.policy.window_cap_paise !== null && (
                <span className="nb-chip">
                  WINDOW CAP {paiseToRupees(result.policy.window_cap_paise)} ({result.policy.window})
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
