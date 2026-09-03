import { DashboardShell } from "@/components/DashboardShell";

export default function Home() {
  return (
    <main className="min-h-screen" style={{ background: "var(--safe-bg)", color: "var(--safe-fg)" }}>
      <DashboardShell />
    </main>
  );
}
