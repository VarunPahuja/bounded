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
  allow: "#5fe38f",
  block: "var(--violation-accent)",
  genesis: "#8a8a94",
};

function shortHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 8)}…${hash.slice(-4)}` : hash;
}

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
    <li className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-black/10 px-4 py-3 text-sm">
      <span className="w-10 font-mono text-xs opacity-50">#{entry.index}</span>
      <span
        className="w-20 font-mono text-xs font-semibold uppercase"
        style={{ color: DECISION_COLOR[entry.decision] }}
      >
        {entry.decision}
      </span>
      <span className="min-w-[140px] flex-1">
        {entry.action ? (
          <>
            {entry.action.action_type} · {paiseToRupees(entry.action.amount_paise)} on {entry.action.order_id}
          </>
        ) : (
          <span className="opacity-50">no action (genesis)</span>
        )}
      </span>
      <span className="font-mono text-xs opacity-50" title={entry.prev_hash}>
        prev {shortHash(entry.prev_hash)}
      </span>
      <span className="font-mono text-xs opacity-50" title={entry.entry_hash}>
        hash {shortHash(entry.entry_hash)}
      </span>
      <span
        className="font-mono text-xs font-semibold"
        style={{
          color:
            verifiedStatus === "broken-here"
              ? "var(--violation-accent)"
              : verifiedStatus === "unverified-after-break"
                ? "#b0b0b8"
                : "#5fe38f",
        }}
      >
        {verifiedStatus === "verified" && "✓ signature ok"}
        {verifiedStatus === "broken-here" && "✗ break detected here"}
        {verifiedStatus === "unverified-after-break" && "— unverified (chain already broken)"}
      </span>
    </li>
  );
}
