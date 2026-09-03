"use client";

import { useEffect, useState } from "react";
import { ApiError, LedgerEntry, fetchLedgerEntries, fetchLedgerVerify } from "@/lib/api";
import { ChainStatusBadge } from "@/components/chain/ChainStatusBadge";
import { LedgerEntryRow } from "@/components/chain/LedgerEntryRow";
import { TamperControl } from "@/components/chain/TamperControl";

export function LedgerSurface() {
  const [entries, setEntries] = useState<LedgerEntry[] | null>(null);
  const [brokenAtIndex, setBrokenAtIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [entryList, verify] = await Promise.all([fetchLedgerEntries(), fetchLedgerVerify()]);
      setEntries(entryList);
      setBrokenAtIndex(verify.broken_at_index);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <header>
        <h1 className="font-serif text-3xl">Ledger</h1>
        <p className="mt-1 text-sm opacity-70">
          The hash-chained, Ed25519-signed audit trail every decision in this system is written
          to. Real entries from the real interceptor -- the same one Attacks and Proof exercise.
        </p>
      </header>

      {error && <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      {entries && (
        <>
          <div className="flex items-center gap-3">
            <ChainStatusBadge brokenAtIndex={brokenAtIndex} />
            <button onClick={load} className="text-xs underline opacity-60">
              refresh
            </button>
          </div>

          <ul className="rounded-lg border border-black/10 bg-white/60">
            {entries.map((e) => (
              <LedgerEntryRow key={e.entry_id} entry={e} brokenAtIndex={brokenAtIndex} />
            ))}
          </ul>

          <TamperControl entries={entries} />
        </>
      )}
    </section>
  );
}
