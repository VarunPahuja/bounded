"use client";

import { useState } from "react";
import { AttacksSurface } from "@/components/surfaces/AttacksSurface";
import { ProofSurface } from "@/components/surfaces/ProofSurface";

// Placeholder nav for steps 2-4 of docs/PHASE7-PLAN.md's build order --
// replaced in step 5 by the spatial, keyboard-driven layout docs/DESIGN.md
// requires. The state shape (which surface is active) carries over as-is.
type SurfaceId = "attacks" | "proof" | "ledger" | "mandate";

const SURFACES: { id: SurfaceId; label: string }[] = [
  { id: "attacks", label: "Attacks" },
  { id: "proof", label: "Proof" },
  { id: "ledger", label: "Ledger" },
  { id: "mandate", label: "Mandate" },
];

export function DashboardShell() {
  const [active, setActive] = useState<SurfaceId>("attacks");

  return (
    <div>
      <nav className="flex gap-2 border-b border-black/10 bg-white/60 px-8 py-3">
        {SURFACES.map((s) => (
          <button
            key={s.id}
            onClick={() => setActive(s.id)}
            className="rounded-full px-3 py-1 text-sm"
            style={
              active === s.id
                ? { background: "var(--safe-accent)", color: "white" }
                : { background: "transparent", color: "var(--safe-fg)", opacity: 0.6 }
            }
          >
            {s.label}
          </button>
        ))}
      </nav>
      {active === "attacks" && <AttacksSurface />}
      {active === "proof" && <ProofSurface />}
      {active === "ledger" && <div className="p-8 text-sm opacity-60">Ledger surface: not built yet (step 3).</div>}
      {active === "mandate" && <div className="p-8 text-sm opacity-60">Mandate surface: not built yet (step 4).</div>}
    </div>
  );
}
