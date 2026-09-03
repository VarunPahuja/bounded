"use client";

import { useEffect, useState } from "react";
import { StatusSummary, fetchStatusSummary } from "@/lib/api";
import { useProofState } from "@/lib/proof-state";

// Always visible, regardless of which surface is focused (task brief Phase
// 7b, item 3) -- a floor of substance under every screenshot and every
// second of video. Every value is a real, pulled number (api/status_summary.py):
// scenario_count counts eval/scenarios/*.json directly, test_count comes
// from a real `pytest --collect-only`, unsound_safe/median_latency_ms are
// parsed from the committed docs/EVAL.md, and chain_verified is the real
// verify_chain result -- never a constant.
export function StatusStrip() {
  const [status, setStatus] = useState<StatusSummary | null>(null);
  const { state: proofState } = useProofState();
  const violation = proofState === "violation";

  useEffect(() => {
    fetchStatusSummary()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const parts: string[] = [];
  if (status) {
    parts.push(`${status.scenario_count} scenarios`);
    if (status.test_count !== null) parts.push(`${status.test_count} tests`);
    if (status.unsound_safe !== null) parts.push(`${status.unsound_safe} unsound-safe`);
    if (status.median_latency_ms !== null) parts.push(`~${status.median_latency_ms.toFixed(0)}ms median proof`);
    parts.push(status.chain_verified ? "chain verified" : "chain BROKEN");
  }

  return (
    <div
      className="fixed top-5 right-5 z-20 rounded-full border px-4 py-1.5 font-mono text-[11px] backdrop-blur-sm"
      style={{
        borderColor: violation ? "rgba(95,227,224,0.3)" : "rgba(0,0,0,0.08)",
        background: violation ? "rgba(10,10,12,0.6)" : "rgba(255,255,255,0.6)",
        color: violation ? "var(--violation-fg)" : "var(--safe-fg)",
      }}
    >
      {status ? parts.join(" · ") : "loading status…"}
    </div>
  );
}
