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
    <div className="nb-panel-flat p-6">
      <h3 className="text-2xl font-black uppercase tracking-tight">Tamper control</h3>
      <p className="mt-2 text-base font-medium" style={{ color: "var(--panel-muted)" }}>
        Simulates editing one entry&apos;s amount directly in the database, bypassing this
        application entirely. Nothing is written to the real ledger — this previews, on a copy,
        exactly where <code className="nb-mono font-bold">verify_chain</code> would detect the edit.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <select className="nb-input nb-mono" value={index ?? ""} onChange={(e) => setIndex(Number(e.target.value))}>
          {tamperable.map((e) => (
            <option key={e.index} value={e.index}>
              #{e.index} — {e.action!.action_type} {paiseToRupees(e.action!.amount_paise)}
            </option>
          ))}
        </select>
        <span className="nb-mono text-sm font-black">NEW AMOUNT (₹):</span>
        <input className="nb-input nb-mono w-28" value={newAmount} onChange={(e) => setNewAmount(e.target.value)} />
        <button
          onClick={handlePreview}
          disabled={loading || index === null}
          className="nb-btn"
          style={{ background: "var(--violation)", color: "var(--violation-ink)" }}
        >
          {loading ? "CHECKING…" : "PREVIEW TAMPER"}
        </button>
      </div>

      {error && (
        <p className="nb-mono mt-3 border-2 border-black bg-white px-3 py-2 text-sm font-bold text-red-700">{error}</p>
      )}
      {result && (
        <p className="nb-mono mt-4 text-lg font-black">
          {result.error ? (
            <span style={{ color: "var(--panel-muted)" }}>{result.error}</span>
          ) : result.broken_at_index !== null ? (
            <span
              className="inline-block border-2 px-3 py-1"
              style={{ borderColor: "var(--ink)", background: "var(--violation)", color: "var(--violation-ink)" }}
            >
              VERIFY_CHAIN DETECTS THE TAMPER AT INDEX {result.broken_at_index}
            </span>
          ) : (
            <span style={{ color: "var(--admitted-on-light)" }}>CHAIN STILL VERIFIES (unexpected — report this)</span>
          )}
        </p>
      )}
    </div>
  );
}
