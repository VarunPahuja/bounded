"use client";

import { useEffect, useState } from "react";
import { ApiError, LedgerEntry, fetchLedgerEntries, fetchLedgerVerify } from "@/lib/api";
import { ChainStatusBadge } from "@/components/chain/ChainStatusBadge";
import { LedgerEntryRow } from "@/components/chain/LedgerEntryRow";
import { TamperControl } from "@/components/chain/TamperControl";
import { useProofState } from "@/lib/proof-state";

export function LedgerSurface() {
  const [entries, setEntries] = useState<LedgerEntry[] | null>(null);
  const [brokenAtIndex, setBrokenAtIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { setState: setProofState } = useProofState();

  async function load() {
    setError(null);
    try {
      const [entryList, verify] = await Promise.all([fetchLedgerEntries(), fetchLedgerVerify()]);
      setEntries(entryList);
      setBrokenAtIndex(verify.broken_at_index);
      // Only the real chain state moves the ambient background -- the
      // tamper control below is a non-destructive preview and must never
      // announce a violation that hasn't actually happened.
      setProofState(verify.broken_at_index !== null ? "violation" : "safe");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="flex w-full flex-col gap-8 px-8 py-10 md:px-14">
      <header>
        <h1 className="nb-heading" style={{ fontSize: "clamp(30px, 4vw, 56px)" }}>
          Ledger
        </h1>
        <p className="mt-3 max-w-3xl text-base font-semibold" style={{ color: "var(--canvas-muted)" }}>
          The hash-chained, Ed25519-signed audit trail every decision in this system is written
          to. Real entries from the real interceptor — the same one Attacks and Proof exercise.
        </p>
      </header>

      {error && (
        <div className="nb-panel-flat p-4 text-base font-bold" style={{ borderColor: "var(--violation)" }}>
          {error}
        </div>
      )}

      {entries && (
        <>
          <div className="flex items-center gap-4">
            <ChainStatusBadge brokenAtIndex={brokenAtIndex} />
            <button onClick={load} className="nb-mono text-sm font-black underline underline-offset-4">
              REFRESH
            </button>
          </div>

          <ul className="nb-panel-flat">
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
