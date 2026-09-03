import { LedgerEntry } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";

interface LedgerEntryRowProps {
  entry: LedgerEntry;
  // Chain verification stops at the first broken link (ledger.chain.verify_chain
  // returns the first bad index, not every bad index past it) -- so this row's
  // own status is only known for certain up to and including that first break.
  brokenAtIndex: number | null;
}

const DECISION_COLOR: Record<string, string> = {
  allow: "#007a3d",
  block: "var(--violation)",
  genesis: "var(--muted-fg)",
};

function shortHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 8)}…${hash.slice(-4)}` : hash;
}

// UI 2.0 (ADR-0015): "hash links should look like links" -- prev/hash
// render as a chunky mono chain segment with an explicit connector glyph,
// not two quiet grey spans.
export function LedgerEntryRow({ entry, brokenAtIndex }: LedgerEntryRowProps) {
  const verifiedStatus =
    brokenAtIndex === null
      ? "verified"
      : entry.index < brokenAtIndex
        ? "verified"
        : entry.index === brokenAtIndex
          ? "broken-here"
          : "unverified-after-break";

  return (
    <li
      className="nb-mono flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-4 text-base"
      style={{ borderTop: "3px solid var(--ink)" }}
    >
      <span className="w-14 text-lg font-black">#{entry.index}</span>
      <span
        className="w-28 border-2 px-2 py-0.5 text-center text-sm font-black uppercase"
        style={{ borderColor: "var(--ink)", color: DECISION_COLOR[entry.decision] }}
      >
        {entry.decision}
      </span>
      <span className="min-w-[220px] flex-1 font-bold">
        {entry.action ? (
          <>
            {entry.action.action_type} · {paiseToRupees(entry.action.amount_paise)} on {entry.action.order_id}
          </>
        ) : (
          <span style={{ color: "var(--muted-fg)" }}>no action (genesis)</span>
        )}
      </span>
      <span className="flex items-center gap-1 text-sm font-bold" style={{ color: "var(--muted-fg)" }} title={entry.prev_hash}>
        {shortHash(entry.prev_hash)}
      </span>
      <span className="text-xl font-black" aria-hidden>
        ⟶
      </span>
      <span className="text-sm font-bold" title={entry.entry_hash}>
        {shortHash(entry.entry_hash)}
      </span>
      <span
        className="ml-auto border-2 px-2 py-0.5 text-sm font-black"
        style={{
          borderColor: "var(--ink)",
          background: verifiedStatus === "broken-here" ? "var(--violation)" : "transparent",
          color:
            verifiedStatus === "broken-here"
              ? "var(--violation-ink)"
              : verifiedStatus === "unverified-after-break"
                ? "var(--muted-fg)"
                : "#007a3d",
        }}
      >
        {verifiedStatus === "verified" && "✓ SIGNATURE OK"}
        {verifiedStatus === "broken-here" && "✗ BREAK DETECTED HERE"}
        {verifiedStatus === "unverified-after-break" && "— UNVERIFIED (CHAIN ALREADY BROKEN)"}
      </span>
    </li>
  );
}
