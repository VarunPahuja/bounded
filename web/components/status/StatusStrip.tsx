"use client";

import { useEffect, useState } from "react";
import { StatusSummary, fetchStatusSummary } from "@/lib/api";

// UI 2.0 (ADR-0015): a hard-edged bar directly under the nav strip, not a
// floating blurred pill -- always visible, on every surface. Every value
// is real (api/status_summary.py); "loading status..." while it resolves
// is a real state too, never a placeholder number.
export function StatusStrip({ top, height }: { top: number; height: number }) {
  const [status, setStatus] = useState<StatusSummary | null>(null);

  useEffect(() => {
    fetchStatusSummary()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const items: string[] = status
    ? [
        `${status.scenario_count} SCENARIOS`,
        status.test_count !== null ? `${status.test_count} TESTS` : null,
        status.unsound_safe !== null ? `${status.unsound_safe} UNSOUND-SAFE` : null,
        status.median_latency_ms !== null ? `~${status.median_latency_ms.toFixed(0)}MS MEDIAN PROOF` : null,
        status.chain_verified ? "CHAIN VERIFIED" : "CHAIN BROKEN",
      ].filter((x): x is string => x !== null)
    : ["LOADING STATUS…"];

  return (
    <div
      className="fixed left-0 right-0 z-20 flex items-center overflow-x-auto"
      style={{
        top,
        height,
        background: "var(--panel-bg)",
        color: "var(--panel-fg)",
        borderBottom: "3px solid var(--ink)",
      }}
    >
      {items.map((item, i) => (
        <span
          key={item}
          className="nb-mono flex h-full shrink-0 items-center px-5 text-sm font-bold tracking-wide"
          style={{
            borderLeft: i === 0 ? "none" : "3px solid var(--ink)",
            color:
              status && item === "CHAIN BROKEN"
                ? "var(--accent)"
                : "var(--panel-fg)",
          }}
        >
          {item}
        </span>
      ))}
    </div>
  );
}
