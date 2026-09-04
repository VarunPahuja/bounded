"use client";

import { useEffect, useMemo, useState } from "react";
import { AttacksSurface } from "@/components/surfaces/AttacksSurface";
import { ProofSurface } from "@/components/surfaces/ProofSurface";
import { LedgerSurface } from "@/components/surfaces/LedgerSurface";
import { MandateSurface } from "@/components/surfaces/MandateSurface";
import { EvidenceSurface } from "@/components/surfaces/EvidenceSurface";
import { StatusStrip } from "@/components/status/StatusStrip";
import { ProofStateProvider, useProofState } from "@/lib/proof-state";

// UI 2.0 (ADR-0015): five surfaces, direct keyboard jump, a hard-edged
// numbered strip instead of a floating pill nav. Every surface stays
// mounted (not remounted on switch) so in-flight state (a running
// scenario, a parsed policy) survives moving away and back -- unchanged
// from the prior build, only the presentation is new.
type SurfaceId = "attacks" | "proof" | "ledger" | "mandate" | "evidence";

const SURFACES: { id: SurfaceId; label: string; key: string }[] = [
  { id: "attacks", label: "Attacks", key: "1" },
  { id: "proof", label: "Proof", key: "2" },
  { id: "ledger", label: "Ledger", key: "3" },
  { id: "mandate", label: "Mandate", key: "4" },
  { id: "evidence", label: "Evidence", key: "5" },
];

const NAV_H = 84;
const STATUS_H = 52;

// Restraint pass (docs/LOG.md, 2026-09-04): the active tab used to be a
// full-height solid accent fill -- a large saturated area for something
// that's chrome, not a verdict. It now stays on the fixed panel pair
// (white/black) like every other tab and signals "active" with a thin
// accent-coloured underline plus a filled key number -- the accent is
// still used for state, just as a small mark instead of a background.
function NavStrip({ active, onSelect }: { active: SurfaceId; onSelect: (id: SurfaceId) => void }) {
  return (
    <div
      className="fixed left-0 right-0 top-0 z-30 flex"
      style={{
        height: NAV_H,
        background: "var(--panel-bg)",
        borderBottom: "3px solid var(--ink)",
      }}
    >
      {SURFACES.map((s, i) => {
        const isActive = s.id === active;
        return (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className="flex flex-1 items-center gap-3 px-5 text-left transition-colors"
            style={{
              borderLeft: i === 0 ? "none" : "2px solid var(--ink)",
              borderBottom: isActive ? "4px solid var(--accent)" : "4px solid transparent",
              background: "var(--panel-bg)",
              color: "var(--panel-fg)",
            }}
          >
            <span
              className="nb-mono flex items-center justify-center"
              style={{
                fontSize: 20,
                fontWeight: 900,
                lineHeight: 1,
                width: 28,
                height: 28,
                background: isActive ? "var(--accent)" : "transparent",
                color: isActive ? "var(--accent-fg)" : "var(--panel-fg)",
              }}
            >
              {s.key}
            </span>
            <span className="text-sm font-extrabold uppercase tracking-tight">{s.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function DashboardInner() {
  const [active, setActive] = useState<SurfaceId>("attacks");
  const { state: proofState } = useProofState();
  const index = useMemo(() => SURFACES.findIndex((s) => s.id === active), [active]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const tag = (document.activeElement?.tagName ?? "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      const match = SURFACES.find((s) => s.key === e.key);
      if (match) setActive(match.id);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div
      className="relative min-h-screen overflow-hidden"
      data-proof-state={proofState}
      style={{ background: "var(--canvas-bg)", color: "var(--canvas-fg)" }}
    >
      <NavStrip active={active} onSelect={setActive} />
      <StatusStrip top={NAV_H} height={STATUS_H} />

      <div
        className="flex"
        style={{
          width: `${SURFACES.length * 100}vw`,
          transform: `translateX(-${index * 100}vw)`,
          transition: "transform 120ms linear",
          minHeight: "100vh",
        }}
      >
        {SURFACES.map((s) => (
          <div key={s.id} className="h-screen w-screen overflow-y-auto" style={{ paddingTop: NAV_H + STATUS_H }}>
            {s.id === "attacks" && <AttacksSurface />}
            {s.id === "proof" && <ProofSurface />}
            {s.id === "ledger" && <LedgerSurface />}
            {s.id === "mandate" && <MandateSurface />}
            {s.id === "evidence" && <EvidenceSurface />}
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardShell() {
  return (
    <ProofStateProvider>
      <DashboardInner />
    </ProofStateProvider>
  );
}
