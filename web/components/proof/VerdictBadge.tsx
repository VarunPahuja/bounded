import { Verdict } from "@/lib/api";

// The bound travels with the verdict structurally: there is no prop
// signature that accepts verdict without horizon, so a screen cannot
// compile while dropping it. See docs/PHASE7-PLAN.md's honesty section.
interface VerdictBadgeProps {
  verdict: Verdict;
  horizon: number;
}

const LABEL: Record<Verdict, string> = {
  safe: "SAFE",
  violation: "VIOLATION",
  error: "ERROR",
};

export function VerdictBadge({ verdict, horizon }: VerdictBadgeProps) {
  return (
    <span
      className="inline-flex items-baseline gap-2 rounded-full px-4 py-1.5 font-mono text-sm font-semibold tracking-wide"
      data-verdict={verdict}
      style={{
        background: verdict === "violation" ? "var(--violation-accent)" : "var(--safe-accent)",
        color: verdict === "violation" ? "var(--violation-bg)" : "var(--safe-bg)",
      }}
    >
      {LABEL[verdict]}
      <span className="text-xs font-normal opacity-90">proven to horizon {horizon}</span>
    </span>
  );
}
