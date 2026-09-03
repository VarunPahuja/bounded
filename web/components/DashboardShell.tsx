"use client";

import { useEffect, useMemo, useState } from "react";
import { AttacksSurface } from "@/components/surfaces/AttacksSurface";
import { ProofSurface } from "@/components/surfaces/ProofSurface";
import { LedgerSurface } from "@/components/surfaces/LedgerSurface";
import { MandateSurface } from "@/components/surfaces/MandateSurface";
import { ProofStateBackground } from "@/components/ambient/ProofStateBackground";
import { ProofStateProvider, useProofState } from "@/lib/proof-state";

// Four surfaces as regions in a spatial strip (docs/DESIGN.md: "not a nav
// bar"), moved between by direct keyboard shortcut -- the hard
// requirement is no scroll-hunting during a live recording. Every
// surface stays mounted (not remounted on switch) so in-flight state
// (a running scenario, a parsed policy) survives moving away and back.
type SurfaceId = "attacks" | "proof" | "ledger" | "mandate";

const SURFACES: { id: SurfaceId; label: string; key: string }[] = [
  { id: "attacks", label: "Attacks", key: "1" },
  { id: "proof", label: "Proof", key: "2" },
  { id: "ledger", label: "Ledger", key: "3" },
  { id: "mandate", label: "Mandate", key: "4" },
];

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

  const violation = proofState === "violation";

  return (
    <div className="relative min-h-screen overflow-hidden" data-proof-state={proofState}>
      <ProofStateBackground />

      {/* Minimal floating nav -- labels + direct-jump keys, not a bar. */}
      <div
        className="fixed top-5 left-5 z-20 flex gap-1 rounded-full border px-2 py-1.5 backdrop-blur-sm"
        style={{
          borderColor: violation ? "rgba(95,227,224,0.3)" : "rgba(0,0,0,0.08)",
          background: violation ? "rgba(10,10,12,0.6)" : "rgba(255,255,255,0.6)",
        }}
      >
        {SURFACES.map((s) => (
          <button
            key={s.id}
            onClick={() => setActive(s.id)}
            className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs transition-colors"
            style={{
              background: active === s.id ? (violation ? "var(--violation-accent)" : "var(--safe-accent)") : "transparent",
              color:
                active === s.id
                  ? violation
                    ? "var(--violation-bg)"
                    : "white"
                  : violation
                    ? "var(--violation-fg)"
                    : "var(--safe-fg)",
              opacity: active === s.id ? 1 : 0.55,
            }}
          >
            <span className="font-mono">{s.key}</span>
            {s.label}
          </button>
        ))}
      </div>

      <div
        className="flex h-screen"
        style={{
          width: `${SURFACES.length * 100}vw`,
          transform: `translateX(-${index * 100}vw)`,
          transition: violation ? "transform 200ms ease" : "transform 700ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        {SURFACES.map((s) => (
          <div
            key={s.id}
            className="h-screen w-screen overflow-y-auto pt-16"
            style={{ color: violation ? "var(--violation-fg)" : "var(--safe-fg)" }}
          >
            {s.id === "attacks" && <AttacksSurface />}
            {s.id === "proof" && <ProofSurface />}
            {s.id === "ledger" && <LedgerSurface />}
            {s.id === "mandate" && <MandateSurface />}
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
