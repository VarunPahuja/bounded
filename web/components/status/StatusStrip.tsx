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
      {items.map((item, i) => {
        // --violation (electric cyan) measures under 1.5:1 against the
        // white panel background it would sit on as plain text -- almost
        // exactly the "light text on a light form control" bug class,
        // just on a status bar instead of an input. A small solid chip
        // gives the state its accent without asking cyan text to carry
        // its own contrast against white.
        const broken = status && item === "CHAIN BROKEN";
        return (
          <span
            key={item}
            className="nb-mono flex h-full shrink-0 items-center px-5 text-sm font-bold tracking-wide"
            style={{ borderLeft: i === 0 ? "none" : "3px solid var(--ink)" }}
          >
            {broken ? (
              <span className="px-2 py-0.5" style={{ background: "var(--violation)", color: "var(--violation-ink)" }}>
                {item}
              </span>
            ) : (
              item
            )}
          </span>
        );
      })}
    </div>
  );
}
