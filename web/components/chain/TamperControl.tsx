"use client";

import { useState } from "react";
import { ApiError, LedgerEntry, tamperPreview } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";

interface TamperControlProps {
  entries: LedgerEntry[];
}

// Non-destructive by construction: this only ever calls
// /api/ledger/tamper-preview, which mutates an in-memory copy of the
// loaded entries and re-verifies that copy -- it never writes to the real
// ledger (ledger/store.py's own append-only triggers would reject a real
// UPDATE anyway). What's demonstrated is what WOULD happen if the same
// edit were made directly against the database, bypassing this app.
export function TamperControl({ entries }: TamperControlProps) {
  const tamperable = entries.filter((e) => e.action !== null);
  const [index, setIndex] = useState<number | null>(tamperable[0]?.index ?? null);
  const [newAmount, setNewAmount] = useState("999");
  const [result, setResult] = useState<{ broken_at_index: number | null; error: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handlePreview() {
    if (index === null) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const amountPaise = Math.round(parseFloat(newAmount) * 100);
      setResult(await tamperPreview(index, amountPaise));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card rounded-lg p-4">
      <h3 className="font-serif text-lg">Tamper control</h3>
      <p className="mt-1 text-xs opacity-70">
        Simulates editing one entry&apos;s amount directly in the database, bypassing this
        application entirely. Nothing is written to the real ledger -- this previews, on a copy,
        exactly where <code>verify_chain</code> would detect the edit.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select
          className="rounded-md border border-black/10 bg-white px-2 py-1.5 text-sm text-[#2b2630]"
          value={index ?? ""}
          onChange={(e) => setIndex(Number(e.target.value))}
        >
          {tamperable.map((e) => (
            <option key={e.index} value={e.index}>
              #{e.index} — {e.action!.action_type} {paiseToRupees(e.action!.amount_paise)}
            </option>
          ))}
        </select>
        <span className="text-xs opacity-60">new amount (₹):</span>
        <input
          className="w-24 rounded-md border border-black/10 bg-white px-2 py-1.5 text-sm text-[#2b2630]"
          value={newAmount}
          onChange={(e) => setNewAmount(e.target.value)}
        />
        <button
          onClick={handlePreview}
          disabled={loading || index === null}
          className="rounded-md px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          style={{ background: "var(--violation-accent)", color: "var(--violation-bg)" }}
        >
          {loading ? "checking…" : "Preview tamper"}
        </button>
      </div>

      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
      {result && (
        <p className="mt-3 font-mono text-sm">
          {result.error ? (
            <span className="opacity-70">{result.error}</span>
          ) : result.broken_at_index !== null ? (
            <span style={{ color: "var(--violation-accent)" }}>
              verify_chain detects the tamper at index {result.broken_at_index}
            </span>
          ) : (
            <span className="text-[#5fe38f]">chain still verifies (unexpected -- report this)</span>
          )}
        </p>
      )}
    </div>
  );
}
