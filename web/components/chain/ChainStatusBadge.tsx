interface ChainStatusBadgeProps {
  brokenAtIndex: number | null;
}

export function ChainStatusBadge({ brokenAtIndex }: ChainStatusBadgeProps) {
  const broken = brokenAtIndex !== null;
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 font-mono text-sm font-semibold"
      style={{
        background: broken ? "var(--violation-accent)" : "var(--safe-accent)",
        color: broken ? "var(--violation-bg)" : "var(--safe-bg)",
      }}
    >
      {broken ? `CHAIN BROKEN at index ${brokenAtIndex}` : "CHAIN VERIFIES CLEAN"}
    </span>
  );
}
