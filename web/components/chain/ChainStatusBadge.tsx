interface ChainStatusBadgeProps {
  brokenAtIndex: number | null;
}

export function ChainStatusBadge({ brokenAtIndex }: ChainStatusBadgeProps) {
  const broken = brokenAtIndex !== null;
  return (
    <span
      className="nb-mono inline-flex items-center gap-2 border-4 px-5 py-2 text-xl font-black"
      style={{
        background: broken ? "var(--violation)" : "var(--safe)",
        color: broken ? "var(--violation-ink)" : "var(--safe-ink)",
        borderColor: "var(--ink)",
        boxShadow: "5px 5px 0 var(--ink)",
      }}
    >
      {broken ? `CHAIN BROKEN AT INDEX ${brokenAtIndex}` : "CHAIN VERIFIES CLEAN"}
    </span>
  );
}
