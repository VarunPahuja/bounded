"use client";

import { useEffect, useState } from "react";
import { ApiError, EvalSummary, fetchEvalSummary } from "@/lib/api";

function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

function ComparisonStat({
  label,
  oursLabel,
  judgeLabel,
  favorable,
}: {
  label: string;
  oursLabel: string;
  judgeLabel: string;
  favorable: "ours" | "judge" | "neutral";
}) {
  return (
    <div className="card rounded-lg p-4">
      <div className="text-xs uppercase tracking-wide opacity-85">{label}</div>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] uppercase opacity-75">ours</div>
          <div
            className="font-mono text-2xl font-semibold"
            style={{ color: favorable === "ours" ? "var(--safe-accent)" : "inherit" }}
          >
            {oursLabel}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase opacity-75">judge</div>
          <div
            className="font-mono text-2xl font-semibold"
            style={{ color: favorable === "judge" ? "var(--safe-accent)" : "inherit" }}
          >
            {judgeLabel}
          </div>
        </div>
      </div>
    </div>
  );
}

export function EvidenceSurface() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEvalSummary()
      .then(setSummary)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  if (error) {
    return (
      <section className="mx-auto flex max-w-4xl flex-col gap-4 p-8">
        <h1 className="font-serif text-4xl md:text-5xl">Evidence</h1>
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          docs/EVAL.md is unavailable: {error}. Run <code>python -m eval.runner</code> to produce it.
        </div>
      </section>
    );
  }

  if (!summary) {
    return (
      <section className="mx-auto flex max-w-4xl flex-col gap-4 p-8">
        <h1 className="font-serif text-4xl md:text-5xl">Evidence</h1>
        <p className="text-sm opacity-85">loading the eval report…</p>
      </section>
    );
  }

  const ours = summary.false_positive.find((r) => r.pipeline === "ours");
  const judge = summary.false_positive.find((r) => r.pipeline === "judge");
  const allRow = summary.pass_k.find((r) => r.class_label === "all");

  return (
    <section className="mx-auto flex max-w-6xl flex-col gap-6 p-8">
      <header>
        <h1 className="font-serif text-4xl md:text-5xl">Evidence</h1>
        <p className="mt-1 text-sm opacity-85">
          The head-to-head measurement in docs/EVAL.md, parsed live from the committed file (not
          hand-typed) -- generated {summary.generated_at}, mode {summary.mode}, commit{" "}
          <code className="text-xs">{summary.commit.slice(0, 12)}</code>. Corpus: {summary.n_scenarios}{" "}
          scenarios across {summary.corpus.classes.length} classes, {summary.n_samples} samples each,{" "}
          {fmtPct(summary.corpus.benign_pct)} benign.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <ComparisonStat
          label="unsound-safe verdicts"
          oursLabel={String(summary.unsound_safe_ours)}
          judgeLabel={String(summary.unsound_safe_judge)}
          favorable="ours"
        />
        <ComparisonStat
          label="false-positive rate, benign flows"
          oursLabel={ours ? fmtPct(ours.rate_pct) : "n/a"}
          judgeLabel={judge ? fmtPct(judge.rate_pct) : "n/a"}
          favorable="ours"
        />
        <ComparisonStat
          label="pass^1, all classes"
          oursLabel={allRow ? fmtPct(allRow.ours["1"]) : "n/a"}
          judgeLabel={allRow ? fmtPct(allRow.judge["1"]) : "n/a"}
          favorable="ours"
        />
      </div>

      <div className="card card-soft rounded-md p-3 text-xs">
        <span className="font-semibold">unsound-safe, defined:</span> {summary.unsound_safe_definition}
      </div>

      {ours && judge && (
        <div className="card rounded-lg p-4 text-xs">
          <div className="mb-2 text-sm font-semibold">False positive rate on benign flows (95% CI)</div>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="opacity-75">
                <th className="py-1 pr-4">pipeline</th>
                <th className="py-1 pr-4">fp</th>
                <th className="py-1 pr-4">n</th>
                <th className="py-1 pr-4">rate</th>
                <th className="py-1">95% CI</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {[ours, judge].map((r) => (
                <tr key={r.pipeline} className="border-t" style={{ borderColor: "var(--card-border)" }}>
                  <td className="py-1.5 pr-4">{r.pipeline}</td>
                  <td className="py-1.5 pr-4">{r.fp}</td>
                  <td className="py-1.5 pr-4">{r.n}</td>
                  <td className="py-1.5 pr-4">{fmtPct(r.rate_pct)}</td>
                  <td className="py-1.5">
                    {r.ci_lo.toFixed(1)} - {r.ci_hi.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card rounded-lg p-4 text-xs">
        <div className="mb-2 text-sm font-semibold">
          pass^k (tau-bench definition), macro-averaged per scenario
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="opacity-75">
                <th className="py-1 pr-4">class</th>
                <th className="py-1 pr-3">ours k=1</th>
                <th className="py-1 pr-3">ours k=4</th>
                <th className="py-1 pr-4">ours k=8</th>
                <th className="py-1 pr-3">judge k=1</th>
                <th className="py-1 pr-3">judge k=4</th>
                <th className="py-1">judge k=8</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {summary.pass_k.map((row) => (
                <tr
                  key={row.class_label}
                  className="border-t"
                  style={{
                    borderColor: "var(--card-border)",
                    fontWeight: row.class_label === "all" ? 700 : 400,
                  }}
                >
                  <td className="py-1.5 pr-4">{row.class_label}</td>
                  <td className="py-1.5 pr-3">{fmtPct(row.ours["1"])}</td>
                  <td className="py-1.5 pr-3">{fmtPct(row.ours["4"])}</td>
                  <td className="py-1.5 pr-4">{fmtPct(row.ours["8"])}</td>
                  <td className="py-1.5 pr-3">{fmtPct(row.judge["1"])}</td>
                  <td className="py-1.5 pr-3">{fmtPct(row.judge["4"])}</td>
                  <td className="py-1.5">{fmtPct(row.judge["8"])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card rounded-lg p-4 text-xs">
        <div className="mb-2 text-sm font-semibold">Corpus composition</div>
        <ul className="flex flex-wrap gap-2 font-mono">
          {summary.corpus.classes.map((c) => (
            <li key={c.class_label} className="card card-soft rounded-full px-2.5 py-1">
              {c.class_label}: {c.scenarios} ({fmtPct(c.pct)})
            </li>
          ))}
        </ul>
        <p className="mt-2 opacity-85">
          {summary.corpus.total} scenarios total, {fmtPct(summary.corpus.benign_pct)} benign.
        </p>
      </div>

      <div className="card rounded-lg p-4 text-xs">
        <div className="mb-1 text-sm font-semibold">Median Z3 verification latency</div>
        <p className="font-mono text-lg">
          {summary.median_latency_ms.toFixed(3)} ms{" "}
          <span className="text-xs font-sans opacity-75">(n={summary.median_latency_n} verify_action calls)</span>
        </p>
      </div>

      {/* Carried verbatim from docs/EVAL.md -- the Phase 6b framing
          correction (adversarial_vs_ours' 100% is reproducibility, not
          adversarial robustness) must survive onto the screen exactly, not
          be summarized down to the bare percentage. */}
      <div className="card rounded-lg p-4">
        <div className="mb-2 text-sm font-semibold">adversarial_vs_ours: findings and what the 100% means</div>
        <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-relaxed opacity-90">
          {summary.adversarial_note.replace(/^## adversarial_vs_ours.*\n\n/, "")}
        </pre>
      </div>
    </section>
  );
}
