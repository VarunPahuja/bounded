import { Verdict } from "@/lib/api";

// The bound travels with the verdict structurally: there is no prop
// signature that accepts verdict without horizon, so a screen cannot
// compile while dropping it. See docs/PHASE7-PLAN.md's honesty section.
//
// UI 2.0 (ADR-0015): fixed --safe/--violation colours, not the ambient
// --accent -- two badges (e.g. naive vs sound guard) must be able to
// disagree with each other regardless of the page's current global mood.
interface VerdictBadgeProps {
  verdict: Verdict;
  horizon: number;
}

const LABEL: Record<Verdict, string> = {
  safe: "SAFE",
  violation: "VIOLATION",
  error: "ERROR",
};

const COLOR: Record<Verdict, { bg: string; fg: string }> = {
  safe: { bg: "var(--safe)", fg: "var(--safe-ink)" },
  violation: { bg: "var(--violation)", fg: "var(--violation-ink)" },
  error: { bg: "#c9c9c9", fg: "#0a0a0a" },
};

export function VerdictBadge({ verdict, horizon }: VerdictBadgeProps) {
  const c = COLOR[verdict];
  return (
    <span
      className="nb-mono inline-flex items-baseline gap-3 border-4 px-5 py-2 text-2xl font-black tracking-tight"
      data-verdict={verdict}
      style={{
        background: c.bg,
        color: c.fg,
        borderColor: "var(--ink)",
        boxShadow: "5px 5px 0 var(--ink)",
      }}
    >
      {LABEL[verdict]}
      <span className="text-sm font-bold">proven to horizon {horizon}</span>
    </span>
  );
}
