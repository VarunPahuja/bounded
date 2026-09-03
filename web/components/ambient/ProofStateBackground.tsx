"use client";

import { useProofState } from "@/lib/proof-state";

// docs/DESIGN.md's two states, one surface: SAFE is weightless -- soft
// drifting lilac/rose blobs on cold white. VIOLATION is rupture -- the
// drift stops, the mist recedes, a rigid grid snaps into a dark field.
// Fixed and behind everything, so it stays visible regardless of which
// of the four surfaces is in view.
export function ProofStateBackground() {
  const { state } = useProofState();
  const violation = state === "violation";

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 transition-colors duration-700"
      style={{ background: violation ? "var(--violation-bg)" : "var(--safe-bg)" }}
    >
      {violation ? (
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(95,227,224,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(95,227,224,0.15) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
      ) : (
        <>
          <div className="drift-blob drift-blob-a" style={{ background: "var(--safe-lilac)" }} />
          <div className="drift-blob drift-blob-b" style={{ background: "var(--safe-rose)" }} />
          <div className="drift-blob drift-blob-c" style={{ background: "var(--safe-lilac)" }} />
        </>
      )}
    </div>
  );
}
