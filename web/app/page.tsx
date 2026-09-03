import { AttacksSurface } from "@/components/surfaces/AttacksSurface";

// Step 1 of docs/PHASE7-PLAN.md's build order: the Attacks surface, wired
// end to end. The other three surfaces and the spatial four-surface nav
// (docs/DESIGN.md) land in later steps -- this page intentionally shows
// only Attacks until Proof/Ledger/Mandate exist.
export default function Home() {
  return (
    <main className="min-h-screen" style={{ background: "var(--safe-bg)", color: "var(--safe-fg)" }}>
      <AttacksSurface />
    </main>
  );
}
