"use client";

import { useEffect, useState } from "react";
import { ApiError, EvalSummary, fetchEvalSummary } from "@/lib/api";

function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

// UI 2.0 (ADR-0015): "it should hit like a scoreboard, not a report
// table." Huge mono numbers, OURS vs JUDGE split by a thick vertical
// divider, the winning side filled solid in the safe accent -- the kind
// of block a viewer reads in half a second, not a table they have to
// scan.
function ScoreTile({
  label,
  oursLabel,
  judgeLabel,
  oursWins,
}: {
  label: string;
  oursLabel: string;
  judgeLabel: string;
  oursWins: boolean;
}) {
  return (
    <div className="nb-panel flex flex-col">
      <div className="border-b-4 px-5 py-3 text-sm font-black uppercase tracking-wide" style={{ borderColor: "var(--ink)" }}>
        {label}
      </div>
      <div className="grid grid-cols-2">
        <div
          className="flex flex-col items-center justify-center gap-1 border-r-4 px-2 py-6"
          style={{
            borderColor: "var(--ink)",
            background: oursWins ? "var(--safe)" : "transparent",
            color: oursWins ? "var(--safe-ink)" : "var(--panel-fg)",
          }}
        >
          <span className="text-xs font-black uppercase tracking-widest">Ours</span>
          {/* Fixed px, not a Tailwind text-* step: tuned so the longest
              real value this tile ever renders ("100.0%") never clips
              against the divider at the 1280px video frame -- caught by
              screenshotting this exact surface, not by eyeballing the
              JSX. */}
          <span className="nb-mono font-black leading-none" style={{ fontSize: 34 }}>
            {oursLabel}
          </span>
        </div>
        <div className="flex flex-col items-center justify-center gap-1 px-2 py-6">
          <span className="text-xs font-black uppercase tracking-widest">Judge</span>
          <span className="nb-mono font-black leading-none" style={{ fontSize: 34 }}>
            {judgeLabel}
          </span>
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
      <section className="flex w-full flex-col gap-6 px-8 py-10 md:px-14">
        <h1 className="nb-heading" style={{ fontSize: "clamp(30px, 4vw, 56px)" }}>
          Evidence
        </h1>
        <div className="nb-panel-flat p-4 text-base font-bold" style={{ borderColor: "var(--violation)" }}>
          docs/EVAL.md is unavailable: {error}. Run <code className="nb-mono">python -m eval.runner</code> to produce it.
        </div>
      </section>
    );
  }

  if (!summary) {
    return (
      <section className="flex w-full flex-col gap-6 px-8 py-10 md:px-14">
        <h1 className="nb-heading" style={{ fontSize: "clamp(30px, 4vw, 56px)" }}>
          Evidence
        </h1>
        <p className="nb-mono text-lg font-bold">loading the eval report…</p>
      </section>
    );
  }

  const ours = summary.false_positive.find((r) => r.pipeline === "ours");
  const judge = summary.false_positive.find((r) => r.pipeline === "judge");
  const allRow = summary.pass_k.find((r) => r.class_label === "all");

  return (
    <section className="flex w-full flex-col gap-8 px-8 py-10 md:px-14">
      <header>
        <h1 className="nb-heading" style={{ fontSize: "clamp(30px, 4vw, 56px)" }}>
          Evidence
        </h1>
        <p className="mt-3 max-w-4xl text-base font-semibold" style={{ color: "var(--canvas-muted)" }}>
          The head-to-head measurement in docs/EVAL.md, parsed live from the committed file (not
          hand-typed) — generated {summary.generated_at}, mode {summary.mode}, commit{" "}
          <code className="nb-mono">{summary.commit.slice(0, 12)}</code>. Corpus: {summary.n_scenarios}{" "}
          scenarios across {summary.corpus.classes.length} classes, {summary.n_samples} samples each,{" "}
          {fmtPct(summary.corpus.benign_pct)} benign.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <ScoreTile label="Unsound-safe verdicts" oursLabel={String(summary.unsound_safe_ours)} judgeLabel={String(summary.unsound_safe_judge)} oursWins />
        <ScoreTile
          label="False-positive rate, benign"
          oursLabel={ours ? fmtPct(ours.rate_pct) : "n/a"}
          judgeLabel={judge ? fmtPct(judge.rate_pct) : "n/a"}
          oursWins
        />
        <ScoreTile
          label="pass^1, all classes"
          oursLabel={allRow ? fmtPct(allRow.ours["1"]) : "n/a"}
          judgeLabel={allRow ? fmtPct(allRow.judge["1"]) : "n/a"}
          oursWins
        />
      </div>

      <div className="nb-panel-flat p-4 text-base font-bold">
        <span className="uppercase">unsound-safe, defined:</span> {summary.unsound_safe_definition}
      </div>

      {ours && judge && (
        <div className="nb-panel-flat p-6">
          <div className="mb-4 text-xl font-black uppercase tracking-tight">False positive rate on benign flows (95% CI)</div>
          <table className="nb-mono w-full border-collapse text-left text-base">
            <thead>
              <tr className="text-sm font-black uppercase" style={{ color: "var(--panel-muted)" }}>
                <th className="border-b-2 py-2 pr-4" style={{ borderColor: "var(--ink)" }}>pipeline</th>
                <th className="border-b-2 py-2 pr-4" style={{ borderColor: "var(--ink)" }}>fp</th>
                <th className="border-b-2 py-2 pr-4" style={{ borderColor: "var(--ink)" }}>n</th>
                <th className="border-b-2 py-2 pr-4" style={{ borderColor: "var(--ink)" }}>rate</th>
                <th className="border-b-2 py-2" style={{ borderColor: "var(--ink)" }}>95% CI</th>
              </tr>
            </thead>
            <tbody>
              {[ours, judge].map((r) => (
                <tr key={r.pipeline} className="font-bold">
                  <td className="py-2 pr-4 uppercase">{r.pipeline}</td>
                  <td className="py-2 pr-4">{r.fp}</td>
                  <td className="py-2 pr-4">{r.n}</td>
                  <td className="py-2 pr-4">{fmtPct(r.rate_pct)}</td>
                  <td className="py-2">
                    {r.ci_lo.toFixed(1)} - {r.ci_hi.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="nb-panel-flat p-6">
        <div className="mb-4 text-xl font-black uppercase tracking-tight">pass^k (tau-bench definition), macro-averaged per scenario</div>
        <div className="overflow-x-auto">
          <table className="nb-mono w-full min-w-[720px] border-collapse text-left text-base">
            <thead>
              <tr className="text-sm font-black uppercase" style={{ color: "var(--panel-muted)" }}>
                <th className="border-b-2 py-2 pr-4" style={{ borderColor: "var(--ink)" }}>class</th>
                <th className="border-b-2 py-2 pr-3" style={{ borderColor: "var(--ink)" }}>ours k=1</th>
                <th className="border-b-2 py-2 pr-3" style={{ borderColor: "var(--ink)" }}>ours k=4</th>
                <th className="border-b-2 py-2 pr-4" style={{ borderColor: "var(--ink)" }}>ours k=8</th>
                <th className="border-b-2 py-2 pr-3" style={{ borderColor: "var(--ink)" }}>judge k=1</th>
                <th className="border-b-2 py-2 pr-3" style={{ borderColor: "var(--ink)" }}>judge k=4</th>
                <th className="border-b-2 py-2" style={{ borderColor: "var(--ink)" }}>judge k=8</th>
              </tr>
            </thead>
            <tbody>
              {summary.pass_k.map((row) => (
                <tr key={row.class_label} style={{ fontWeight: row.class_label === "all" ? 900 : 700 }}>
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="nb-panel-flat p-6">
          <div className="mb-3 text-xl font-black uppercase tracking-tight">Corpus composition</div>
          <ul className="nb-mono flex flex-wrap gap-2 text-sm font-bold">
            {summary.corpus.classes.map((c) => (
              <li key={c.class_label} className="nb-chip">
                {c.class_label.toUpperCase()}: {c.scenarios} ({fmtPct(c.pct)})
              </li>
            ))}
          </ul>
          <p className="mt-3 text-base font-bold">
            {summary.corpus.total} scenarios total, {fmtPct(summary.corpus.benign_pct)} benign.
          </p>
        </div>

        <div className="nb-panel-flat p-6">
          <div className="mb-1 text-xl font-black uppercase tracking-tight">Median Z3 verification latency</div>
          <p className="nb-mono text-4xl font-black">
            {summary.median_latency_ms.toFixed(3)} ms{" "}
            <span className="text-sm font-bold" style={{ color: "var(--panel-muted)" }}>
              (n={summary.median_latency_n})
            </span>
          </p>
        </div>
      </div>

      {/* Carried verbatim from docs/EVAL.md -- the Phase 6b framing
          correction (adversarial_vs_ours' 100% is reproducibility, not
          adversarial robustness) must survive onto the screen exactly, not
          be summarized down to the bare percentage. */}
      <div className="nb-panel-flat p-6">
        <div className="mb-3 text-xl font-black uppercase tracking-tight">adversarial_vs_ours: findings and what the 100% means</div>
        <pre className="nb-mono max-h-96 overflow-y-auto whitespace-pre-wrap text-sm font-medium leading-relaxed">
          {summary.adversarial_note.replace(/^## adversarial_vs_ours.*\n\n/, "")}
        </pre>
      </div>
    </section>
  );
}
